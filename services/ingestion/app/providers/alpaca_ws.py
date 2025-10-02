from __future__ import annotations
import os
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Callable
from loguru import logger
import websocket
import threading


class AlpacaWebSocketProvider:
    """
    Real-time WebSocket provider for Alpaca (IEX feed, free tier).
    Streams trades and aggregates them into 1-minute candles.
    """

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        feed: str = "iex",  # 'iex' (free) or 'sip' (paid)
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.feed = feed
        self.ws_url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        self.ws: websocket.WebSocketApp | None = None
        self.symbols: List[str] = []
        self.on_candle_callback: Callable[[Dict], None] | None = None
        self.on_tick_callback: Callable[[Dict], None] | None = None
        self.running = False
        self.thread: threading.Thread | None = None

        # Candle aggregation state (symbol -> current 1-min bar)
        self.current_bars: Dict[str, Dict] = {}

    def connect(self, symbols: List[str], on_candle: Callable[[Dict], None], on_tick: Callable[[Dict], None] | None = None):
        """
        Connect to Alpaca WebSocket and subscribe to trades for given symbols.
        on_candle(candle_dict) is called when a 1-min bar completes.
        on_tick(tick_dict) is called for every individual trade (optional).
        """
        self.symbols = symbols
        self.on_candle_callback = on_candle
        self.on_tick_callback = on_tick
        self.running = True

        def on_open(ws):
            logger.info("Alpaca WebSocket opened, authenticating...")
            auth_msg = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.secret_key,
            }
            ws.send(json.dumps(auth_msg))

        def on_message(ws, message):
            try:
                data = json.loads(message)
                for msg in data:
                    msg_type = msg.get("T")
                    if msg_type == "success" and msg.get("msg") == "authenticated":
                        logger.info("Alpaca authenticated, subscribing to trades...")
                        sub_msg = {"action": "subscribe", "trades": self.symbols}
                        ws.send(json.dumps(sub_msg))
                    elif msg_type == "subscription":
                        logger.info("Alpaca subscription confirmed: {}", msg)
                    elif msg_type == "t":  # trade
                        self._handle_trade(msg)
            except Exception as e:
                logger.error("Error processing Alpaca message: {}", e)

        def on_error(ws, error):
            logger.error("Alpaca WebSocket error: {}", error)

        def on_close(ws, close_status_code, close_msg):
            logger.warning("Alpaca WebSocket closed: {} {}", close_status_code, close_msg)
            if self.running:
                logger.info("Reconnecting in 5s...")
                time.sleep(5)
                self.connect(self.symbols, self.on_candle_callback)

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()
        logger.info("Alpaca WebSocket thread started for symbols: {}", self.symbols)

    def _handle_trade(self, trade: Dict):
        """
        Aggregate trades into 1-minute OHLCV bars and optionally emit raw ticks.
        trade example: {"T":"t","S":"AAPL","i":123,"x":"V","p":150.25,"s":100,"t":"2025-10-01T12:34:56.789Z","c":["@"],"z":"C"}
        """
        symbol = trade.get("S")
        price = trade.get("p")
        size = trade.get("s", 0)
        timestamp_str = trade.get("t")  # ISO8601
        exchange = trade.get("x", "")

        if not symbol or not price or not timestamp_str:
            return

        # Parse timestamp and round to 1-minute bucket
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        
        # Emit raw tick if callback is set
        if self.on_tick_callback:
            tick = {
                "symbol": symbol,
                "time": dt.isoformat(),
                "price": price,
                "size": size,
                "exchange": exchange
            }
            self.on_tick_callback(tick)
        
        bar_time = dt.replace(second=0, microsecond=0)
        bar_key = bar_time.isoformat()

        if symbol not in self.current_bars:
            self.current_bars[symbol] = {}

        if bar_key not in self.current_bars[symbol]:
            # New bar
            self.current_bars[symbol][bar_key] = {
                "time": bar_time.isoformat(),
                "symbol": symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": size,
            }
        else:
            # Update existing bar
            bar = self.current_bars[symbol][bar_key]
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += size

        # Emit completed bars (older than current minute)
        self._emit_completed_bars(symbol, bar_time)

    def _emit_completed_bars(self, symbol: str, current_bar_time: datetime):
        """Emit any bars that are complete (older than current_bar_time)."""
        if symbol not in self.current_bars:
            return

        completed = []
        for bar_key, bar in list(self.current_bars[symbol].items()):
            bar_dt = datetime.fromisoformat(bar["time"])
            if bar_dt < current_bar_time:
                completed.append(bar)
                del self.current_bars[symbol][bar_key]

        for bar in completed:
            if self.on_candle_callback:
                self.on_candle_callback(bar)

    def stop(self):
        """Stop the WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("Alpaca WebSocket provider stopped")
