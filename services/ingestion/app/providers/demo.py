from __future__ import annotations
import random
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from loguru import logger
from .base import MarketDataProvider


class DemoProvider(MarketDataProvider):
    """
    Demo provider that generates synthetic OHLCV candles.
    Useful for testing without API keys or rate limits.
    """

    def __init__(self, base_price: float = 150.0, volatility: float = 0.02):
        self.base_price = base_price
        self.volatility = volatility
        self.last_close = base_price

    def fetch_intraday(self, symbol: str, interval: str = "1min") -> List[Dict]:
        """
        Generate synthetic 1-minute candles for the last 100 minutes.
        """
        candles: List[Dict] = []
        now = datetime.now(timezone.utc)

        for i in range(100, 0, -1):
            candle_time = now - timedelta(minutes=i)
            open_price = self.last_close
            # Random walk
            change = random.gauss(0, self.volatility)
            close_price = open_price * (1 + change)
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, self.volatility / 2)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, self.volatility / 2)))
            volume = random.randint(1000, 100000)

            candles.append({
                "time": candle_time.isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
            })
            self.last_close = close_price

        logger.info(f"Generated {len(candles)} demo candles for {symbol}")
        return candles

    def fetch_latest(self, symbol: str) -> List[Dict]:
        """
        Generate a single new candle (simulates polling for new data).
        """
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        open_price = self.last_close
        change = random.gauss(0, self.volatility)
        close_price = open_price * (1 + change)
        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, self.volatility / 2)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, self.volatility / 2)))
        volume = random.randint(1000, 100000)

        candle = {
            "time": now.isoformat(),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": volume,
        }
        self.last_close = close_price
        return [candle]
