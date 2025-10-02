from __future__ import annotations
import time
import json
import redis
import psycopg2
import os
import sys
from loguru import logger
from .config import settings
from .db import get_cursor
from .engine import StrategyContext, maybe_emit_signal
from .detectors.market_state import run_market_state_detection
from .alerts.lvn_alerts import run_lvn_alerts
from .indicators.aggressive_flow import run_aggressive_flow_detection
from .trading.auto_strategy import run_auto_trading

# Configure cleaner log format
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<cyan>{extra[module]:12}</cyan> | {message}",
    level="INFO"
)

def run():
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    
    # Check if auto-trading is enabled
    auto_trading_enabled = os.getenv("AUTO_TRADING_ENABLED", "false").lower() == "true"
    
    if auto_trading_enabled:
        logger.info("🤖 Starting engine service with AUTOMATED TRADING enabled")
    else:
        logger.info("Starting engine service (auto-trading disabled)")
    
    # Get database connection for market state detector
    db_conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )
    
    loop_count = 0

    while True:
        try:
            # Run market state detection every 5 seconds (every 5 loops)
            if loop_count % 5 == 0:
                try:
                    run_market_state_detection(db_conn)
                except Exception as e:
                    logger.error(f"Market state detection error: {e}")
            
            # Run LVN alerts every 2 seconds (every 2 loops)
            if loop_count % 2 == 0:
                try:
                    run_lvn_alerts(db_conn)
                except Exception as e:
                    logger.error(f"LVN alert error: {e}")
            
            # Run aggressive flow detection every 1 second (every loop) - CRITICAL
            try:
                run_aggressive_flow_detection(db_conn)
            except Exception as e:
                logger.error(f"Aggressive flow detection error: {e}")
            
            # Run automated trading every 1 second (every loop) if enabled - CRITICAL
            if auto_trading_enabled:
                try:
                    logger.info("🤖 Running automated trading check...")
                    run_auto_trading(db_conn)
                except Exception as e:
                    logger.error(f"Auto trading error: {e}")
            
            loop_count += 1
            
            with get_cursor() as cur:
                # Load active strategies
                cur.execute("SELECT id, name, definition FROM strategies WHERE active = TRUE")
                strategies = cur.fetchall()
                if not strategies:
                    time.sleep(1)  # Ultra-fast loop
                    continue

                # Map symbol strings to ids
                cur.execute("SELECT id, symbol FROM symbols")
                rows = cur.fetchall()
                sym_map = {s: i for i, s in rows}

                for sid, name, definition in strategies:
                    # definition could be returned as a JSON string or a dict
                    if isinstance(definition, str):
                        try:
                            definition = json.loads(definition)
                        except Exception:
                            logger.warning("Invalid strategy JSON for id {}", sid)
                            continue
                    symbol = definition.get("symbol", "AAPL")
                    symbol_id = sym_map.get(symbol)
                    if not symbol_id:
                        continue
                    ctx = StrategyContext(sid, symbol_id, symbol, definition)
                    sig = maybe_emit_signal(cur, ctx)
                    if sig:
                        cur.execute(
                            """
                            INSERT INTO signals(strategy_id, symbol_id, type, details)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (sid, symbol_id, sig["type"], json.dumps(sig["details"])),
                        )
                        payload = {
                            "symbol": symbol,
                            "type": sig["type"],
                            "details": sig["details"],
                        }
                        try:
                            r.publish("signals", json.dumps(msg))
                        except Exception as e:
                            logger.debug("Redis publish error: {}", e)
                        logger.info(f"Signal: {msg}")

            time.sleep(1)  # Check every 1 second for maximum responsiveness
        except Exception as e:
            logger.exception("Engine loop error: {}", e)
            time.sleep(1)
if __name__ == "__main__":
    run()
