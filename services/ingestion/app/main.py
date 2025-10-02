from __future__ import annotations
import os
import time
import json
from datetime import datetime
from dateutil import tz
import redis
from loguru import logger
from .config import settings
from .db import get_cursor, upsert_symbol, insert_candle
from .providers.alpha_vantage import AlphaVantageProvider
from .providers.alpaca_ws import AlpacaWebSocketProvider
from .providers.demo import DemoProvider


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
    
    else:
        logger.error("Unknown PROVIDER: {}. Use 'alpaca_ws', 'alpha_vantage', or 'demo'", provider_type)
        time.sleep(60)


if __name__ == "__main__":
    run()
