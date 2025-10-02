"""
Backtest Data Loading Module

Handles loading and merging of historical market data for backtesting.
Optimized for performance and proper multi-stock handling.
"""

import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger


class BacktestDataLoader:
    """Handles loading and merging of historical market data."""

    def __init__(self, db_connection):
        """Initialize data loader."""
        self.conn = db_connection
        self._cache = {}  # Simple cache for loaded data

    def load_candles(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Load candle data for a symbol.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of candle dictionaries
        """
        cache_key = f"{symbol}_{start_date}_{end_date}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT time, open, high, low, close, volume, symbol_id
                    FROM candles c
                    JOIN symbols s ON c.symbol_id = s.id
                    WHERE s.symbol = %s AND time >= %s AND time <= %s
                    ORDER BY time
                """, (symbol, start_date, end_date))

                rows = cur.fetchall()
                candles = []

                for row in rows:
                    candles.append({
                        'time': row[0],
                        'open': float(row[1]),
                        'high': float(row[2]),
                        'low': float(row[3]),
                        'close': float(row[4]),
                        'volume': int(row[5]),
                        'symbol_id': row[6],
                        'symbol': symbol
                    })

                self._cache[cache_key] = candles
                logger.debug(f"Loaded {len(candles):,} candles for {symbol}")
                return candles

        except Exception as e:
            logger.error(f"Error loading candles for {symbol}: {e}")
            return []

    def load_market_state(self, symbol_id: int, timestamp: datetime) -> Optional[Dict]:
        """Load market state data for a specific timestamp."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT state, confidence
                    FROM market_state
                    WHERE symbol_id = %s AND time <= %s
                    ORDER BY time DESC
                    LIMIT 1
                """, (symbol_id, timestamp))

                row = cur.fetchone()
                if row:
                    return {
                        'state': row[0],
                        'confidence': int(row[1])
                    }
        except Exception as e:
            logger.error(f"Error loading market state: {e}")

        return None

    def load_order_flow(self, symbol_id: int, timestamp: datetime, lookback: int = 5) -> List[Dict]:
        """Load order flow data for a specific timestamp."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT bucket, cumulative_delta, buy_pressure, sell_pressure
                    FROM order_flow
                    WHERE symbol_id = %s AND bucket <= %s
                    ORDER BY bucket DESC
                    LIMIT %s
                """, (symbol_id, timestamp, lookback))

                rows = cur.fetchall()
                flow_data = []

                for row in rows:
                    flow_data.append({
                        'bucket': row[0],
                        'cumulative_delta': int(row[1]),
                        'buy_pressure': float(row[2]),
                        'sell_pressure': float(row[3])
                    })

                return flow_data

        except Exception as e:
            logger.error(f"Error loading order flow: {e}")
            return []

    def load_and_merge_candles(self, symbols: List[str], start_date: datetime, end_date: datetime) -> Dict[datetime, Dict[str, Dict]]:
        """
        Load candles for all symbols and merge by timestamp for simultaneous processing.

        Returns:
            Dict[datetime, Dict[str, Dict]] - timestamp -> {symbol -> bar_data}
        """
        all_bars_by_time = {}

        for symbol in symbols:
            candles = self.load_candles(symbol, start_date, end_date)

            for bar in candles:
                timestamp = bar['time']
                if timestamp not in all_bars_by_time:
                    all_bars_by_time[timestamp] = {}
                all_bars_by_time[timestamp][symbol] = bar

        logger.info(f"Merged {len(all_bars_by_time):,} timestamps across {len(symbols)} symbols")
        return all_bars_by_time

    def get_symbol_id(self, symbol: str) -> Optional[int]:
        """Get symbol ID from database."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting symbol ID for {symbol}: {e}")
            return None

    def preload_symbol_data(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Preload all required data for better performance.
        This is useful for repeated queries during backtesting.
        """
        logger.info("Preloading symbol data for performance...")

        # Preload all symbol IDs
        self.symbol_ids = {}
        for symbol in symbols:
            symbol_id = self.get_symbol_id(symbol)
            if symbol_id:
                self.symbol_ids[symbol] = symbol_id

        # Could preload market state and order flow data here for even better performance
        logger.info(f"Preloaded data for {len(self.symbol_ids)} symbols")

    def clear_cache(self):
        """Clear internal cache."""
        self._cache.clear()
        logger.debug("Cache cleared")
