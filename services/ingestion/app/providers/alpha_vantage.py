from __future__ import annotations
import os
import time
from typing import List, Dict
import requests
from loguru import logger
from .base import MarketDataProvider


class AlphaVantageProvider(MarketDataProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"

    def fetch_intraday(self, symbol: str, interval: str = "1min") -> List[Dict]:
        if not self.api_key:
            logger.warning("Alpha Vantage API key not set; skipping fetch")
            return []
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "apikey": self.api_key,
            "outputsize": "compact",
            "datatype": "json",
        }
        r = requests.get(self.base_url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        key = next((k for k in data.keys() if "Time Series" in k), None)
        if not key:
            if "Note" in data:
                logger.warning("Alpha Vantage throttle note: {}", data.get("Note"))
                return []
            logger.warning("Unexpected AV response keys: {}", list(data.keys()))
            return []
        series = data[key]
        candles: List[Dict] = []
        for ts, v in series.items():
            candles.append(
                {
                    "time": ts,
                    "open": float(v["1. open"]),
                    "high": float(v["2. high"]),
                    "low": float(v["3. low"]),
                    "close": float(v["4. close"]),
                    "volume": int(float(v["5. volume"])),
                }
            )
        candles.sort(key=lambda x: x["time"])  # oldest first
        return candles
