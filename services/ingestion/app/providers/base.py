from typing import List, Dict


class MarketDataProvider:
    def fetch_intraday(self, symbol: str, interval: str = "1min") -> List[Dict]:
        """Return list of candle dicts: {time, open, high, low, close, volume}"""
        raise NotImplementedError
