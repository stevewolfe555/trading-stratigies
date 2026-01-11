from __future__ import annotations
import os
import time
import json
from datetime import datetime
import threading
from dateutil import tz
import redis
from loguru import logger
from .config import settings
from .db import get_cursor, upsert_symbol, insert_candle
from .providers.alpha_vantage import AlphaVantageProvider
from .providers.alpaca_ws import AlpacaWebSocketProvider
from .providers.demo import DemoProvider
from .providers.ig_provider import IGProvider, get_epic_for_symbol


def parse_ts(ts_str: str) -> datetime:
    """Parse timestamp string to timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.UTC)
    return dt


def handle_tick(r: redis.Redis, symbol: str, tick: dict):
    """
    Insert a raw tick into DB.
    Called by WebSocket providers for every trade.
    """
    try:
        with get_cursor() as cur:
            symbol_id = upsert_symbol(cur, symbol)
            ts = parse_ts(tick["time"])
            cur.execute(
                """
                INSERT INTO ticks (time, symbol_id, price, size, exchange)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol_id, price) DO NOTHING
                """,
                (ts, symbol_id, tick["price"], tick["size"], tick.get("exchange", ""))
            )
    except Exception as e:
        logger.error("Error handling tick for {}: {}", symbol, e)


def handle_candle(r: redis.Redis, symbol: str, candle: dict):
    """
    Insert a candle into DB and publish to Redis.
    Called by both polling providers and WebSocket providers.
    """
    try:
        with get_cursor() as cur:
            symbol_id = upsert_symbol(cur, symbol)
            ts = parse_ts(candle["time"])
            insert_candle(
                cur,
                symbol_id,
                ts,
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                candle["volume"],
            )
            try:
                r.publish(
                    "ticks:candles",
                    json.dumps({
                        "symbol": symbol,
                        "time": ts.isoformat(),
                        "close": candle["close"],
                    }),
                )
            except Exception as e:
                logger.debug("Redis publish error: {}", e)
    except Exception as e:
        logger.error("Error handling candle for {}: {}", symbol, e)


def run_polling_provider(r: redis.Redis, provider, symbols: list[str]):
    """Run a polling-based provider (Alpha Vantage, Demo) in a loop."""
    while True:
        try:
            for symbol in symbols:
                with get_cursor() as cur:
                    symbol_id = upsert_symbol(cur, symbol)
                    # Check if we need backfill
                    cur.execute("SELECT COUNT(*) FROM candles WHERE symbol_id = %s", (symbol_id,))
                    existing = cur.fetchone()[0] or 0
                    
                    if existing < 20:
                        # Backfill
                        candles = provider.fetch_intraday(symbol)
                        for c in candles[-100:]:
                            handle_candle(r, symbol, c)
                    else:
                        # Fetch latest
                        if hasattr(provider, 'fetch_latest'):
                            candles = provider.fetch_latest(symbol)
                        else:
                            candles = provider.fetch_intraday(symbol)[-5:]
                        for c in candles:
                            handle_candle(r, symbol, c)
            time.sleep(60)
        except Exception as e:
            logger.exception("Polling provider error: {}", e)
            time.sleep(15)


def run_ig_provider(r: redis.Redis, symbols: list[str]):
    """Run IG provider (Level 1) in a loop, emitting ticks for symbols.

    For each configured symbol:
    - Resolve EPIC (via static mapping; fallback to search)
    - Fetch market details (bid/ask/last)
    - Publish as a tick with current time and last price
    """
    api_key = os.getenv("IG_API_KEY")
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    demo = os.getenv("IG_DEMO", "true").lower() == "true"

    if not all([api_key, username, password]):
        logger.error("IG provider selected but credentials are missing (IG_API_KEY, IG_USERNAME, IG_PASSWORD)")
        time.sleep(30)
        return

    ig = IGProvider(api_key, username, password, demo=demo)

    # Try authenticate once up-front
    if not ig.authenticate():
        logger.error("IG authentication failed; retrying in 60s")
        time.sleep(60)
        return

    # Cache symbol->epic mapping to avoid repeated lookups
    symbol_to_epic: dict[str, str] = {}

    def resolve_epic(sym: str) -> str | None:
        if sym in symbol_to_epic:
            return symbol_to_epic[sym]
        epic = get_epic_for_symbol(sym)
        if not epic:
            # Try multiple queries: exact with suffix, without suffix
            queries = [sym, sym.replace('.L', '')]
            for q in queries:
                results = ig.search_markets(q)
                if not results:
                    continue
                # Filter for LSE SHARES where possible
                filtered = []
                for m in results:
                    name = (m.get('name') or '')
                    ep = m.get('epic')
                    itype = (m.get('type') or '').upper()
                    if sym.endswith('.L') and 'SHARE' in itype:
                        filtered.append(m)
                candidates = filtered or results
                # Pick best by name/epic similarity
                qU = q.upper()
                best = None
                for m in candidates:
                    nameU = (m.get('name') or '').upper()
                    ep = m.get('epic')
                    if not ep:
                        continue
                    if sym.endswith('.L') and (nameU.startswith(qU) or qU in nameU):
                        best = m
                        break
                    if ep.upper().startswith('IX.'):
                        best = m if best is None else best
                if not best:
                    best = candidates[0]
                epic = best.get('epic') if best else None
                if epic:
                    break
        if epic:
            symbol_to_epic[sym] = epic
        return epic

    while True:
        try:
            for symbol in symbols:
                epic = resolve_epic(symbol)
                if not epic:
                    logger.warning(f"IG: could not resolve EPIC for {symbol}")
                    continue

                data = ig.get_market_details(epic)
                if not data:
                    # If epic invalid/unavailable, drop from cache to re-resolve next time
                    if sym in symbol_to_epic:
                        try:
                            del symbol_to_epic[sym]
                        except Exception:
                            pass
                    continue

                # Build a synthetic tick from Level 1 data
                last = data.get('last') or data.get('mid') or data.get('bid')
                if last is None:
                    continue

                tick = {
                    "time": datetime.utcnow().replace(tzinfo=tz.UTC).isoformat(),
                    "price": float(last),
                    "size": 0,
                    "exchange": "IG"
                }
                handle_tick(r, symbol, tick)

            time.sleep(5)
        except Exception as e:
            logger.exception("IG provider loop error: {}", e)
            time.sleep(10)

def run():
    logger.info("Starting ingestion service with symbols: {}", settings.symbols)
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    
    # Determine which provider(s) to use from env
    provider_type = os.getenv("PROVIDER", "demo").lower()
    
    if provider_type == "alpaca_ws":
        logger.info("Using Alpaca WebSocket provider")
        provider = AlpacaWebSocketProvider()
        
        def on_tick(tick: dict):
            symbol = tick.get("symbol", "UNKNOWN")
            handle_tick(r, symbol, tick)
        
        def on_candle(candle: dict):
            symbol = candle.get("symbol", "UNKNOWN")
            handle_candle(r, symbol, candle)
        
        provider.connect(list(settings.symbols), on_candle, on_tick)
        # Keep main thread alive
        while True:
            time.sleep(60)
    
    elif provider_type == "alpha_vantage":
        logger.info("Using Alpha Vantage REST provider")
        provider = AlphaVantageProvider(settings.alpha_vantage_api_key)
        run_polling_provider(r, provider, list(settings.symbols))
    
    elif provider_type == "demo":
        logger.info("Using Demo provider (synthetic data)")
        provider = DemoProvider()
        run_polling_provider(r, provider, list(settings.symbols))
    
    elif provider_type == "ig":
        logger.info("Using IG provider (Level 1 ticks)")
        # Filter to symbols that are likely IG-routed (e.g., LSE or indices/forex)
        symbols = [s for s in settings.symbols if s.endswith('.L') or s.startswith('^') or (len(s) == 6 and s.isalpha())]
        if not symbols:
            logger.warning("No IG-compatible symbols configured; using all symbols")
            symbols = list(settings.symbols)
        run_ig_provider(r, symbols)
    
    elif provider_type == "router":
        logger.info("Using Router mode (multi-provider)")
        threads: list[threading.Thread] = []

        # IG worker if IG creds present
        if os.getenv("IG_API_KEY") and os.getenv("IG_USERNAME") and os.getenv("IG_PASSWORD"):
            ig_symbols = [s for s in settings.symbols if s.endswith('.L') or s.startswith('^') or (len(s) == 6 and s.isalpha())]
            if ig_symbols:
                t_ig = threading.Thread(target=run_ig_provider, args=(r, ig_symbols), daemon=True)
                t_ig.start()
                threads.append(t_ig)
                logger.info("Started IG worker for symbols: {}", ig_symbols)
            else:
                logger.warning("Router: no IG symbols configured; skipping IG worker")

        # Alpaca WS worker if Alpaca creds present
        if os.getenv("APCA_API_KEY_ID") and os.getenv("APCA_API_SECRET_KEY"):
            logger.info("Starting Alpaca WebSocket worker")
            provider = AlpacaWebSocketProvider()

            def on_tick_ws(tick: dict):
                symbol = tick.get("symbol", "UNKNOWN")
                handle_tick(r, symbol, tick)

            def on_candle_ws(candle: dict):
                symbol = candle.get("symbol", "UNKNOWN")
                handle_candle(r, symbol, candle)

            # Run WS connect in a thread
            def run_alpaca_ws():
                try:
                    provider.connect(list(settings.symbols), on_candle_ws, on_tick_ws)
                    while True:
                        time.sleep(60)
                except Exception as e:
                    logger.exception("Alpaca WS worker error: {}", e)

            t_alp = threading.Thread(target=run_alpaca_ws, daemon=True)
            t_alp.start()
            threads.append(t_alp)
        else:
            logger.warning("Router: Alpaca credentials not set; skipping Alpaca WS worker")

        # Polymarket worker if enabled
        if os.getenv("POLYMARKET_ENABLED", "false").lower() == "true":
            logger.info("Starting Polymarket WebSocket worker")

            def run_polymarket_ws():
                """Run Polymarket in asyncio event loop within thread."""
                try:
                    import asyncio
                    from app.providers.polymarket_ws import PolymarketWebSocketProvider
                    import psycopg2

                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # Get database connection
                    db_conn = psycopg2.connect(
                        host=settings.postgres_host,
                        database=settings.postgres_db,
                        user=settings.postgres_user,
                        password=settings.postgres_password,
                        port=settings.postgres_port
                    )

                    # Create provider with config from env
                    # CLOB (Central Limit Order Book) = NO GAS FEES!
                    config = {
                        'ws_url': os.getenv('POLYMARKET_WS_URL',
                            'wss://ws-subscriptions-clob.polymarket.com/ws/market'),
                        'spread_threshold': float(os.getenv('POLYMARKET_SPREAD_THRESHOLD', '1.00')),
                        'fee_rate': float(os.getenv('POLYMARKET_FEE_RATE', '0.00')),
                        'min_position_size': float(os.getenv('POLYMARKET_MIN_POSITION_SIZE', '100'))
                    }
                    provider = PolymarketWebSocketProvider(db_conn, config)

                    # Fetch active markets with token IDs
                    cur = db_conn.cursor()
                    cur.execute("""
                        SELECT yes_token_id, no_token_id
                        FROM binary_markets
                        WHERE status = 'active'
                          AND yes_token_id IS NOT NULL
                          AND no_token_id IS NOT NULL
                    """)

                    # Collect all token IDs (both YES and NO)
                    token_ids = []
                    for yes_id, no_id in cur.fetchall():
                        token_ids.append(yes_id)
                        token_ids.append(no_id)

                    if not token_ids:
                        logger.warning("No active markets with token IDs found. Run market_fetcher first!")
                        return

                    logger.info(f"Subscribing to {len(token_ids)} token IDs from {len(token_ids)//2} markets")

                    # Connect, subscribe, and listen
                    async def start():
                        await provider.connect()
                        await provider.subscribe_assets(token_ids)
                        await provider.listen()

                    # Run until cancelled
                    loop.run_until_complete(start())

                except Exception as e:
                    logger.exception("Polymarket WS worker error: {}", e)

            t_poly = threading.Thread(target=run_polymarket_ws, daemon=True)
            t_poly.start()
            threads.append(t_poly)
            logger.info("Polymarket worker started")
        else:
            logger.info("Polymarket disabled (set POLYMARKET_ENABLED=true to enable)")

        if not threads:
            logger.error("Router: no workers started (missing credentials?)")
            time.sleep(60)
            return

        # Keep main thread alive
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Router: shutting down")
    
    else:
        logger.error("Unknown PROVIDER: {}. Use 'alpaca_ws', 'alpha_vantage', or 'demo'", provider_type)
        time.sleep(60)


if __name__ == "__main__":
    run()
