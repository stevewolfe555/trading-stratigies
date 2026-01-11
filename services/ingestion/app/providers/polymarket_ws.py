"""
Polymarket WebSocket Provider

Real-time YES/NO price streaming via Polymarket CLOB API.
Optimized for ultra-low latency arbitrage detection (<50ms).

Features:
- WebSocket connection to Polymarket CLOB
- Subscribe to order book updates for binary markets
- Calculate spread and precompute arbitrage flags
- Symbol ID caching for speed optimization
- Auto-reconnect on disconnect

Performance targets:
- Message processing: <10ms
- Database insert: <15ms
- Total latency: <50ms from exchange to DB
"""

import asyncio
import json
import websockets
from decimal import Decimal
from typing import Dict, Optional, Set
from datetime import datetime, timezone
from loguru import logger
import psycopg2


class PolymarketWebSocketProvider:
    """
    Polymarket CLOB WebSocket provider for real-time binary option prices.

    Connection: wss://ws-subscriptions-clob.polymarket.com/ws/market
    Authentication: None required for public market data
    Message format: JSON with "book", "price_change", "last_trade_price" events

    API Documentation:
    - Market Channel: wss://ws-subscriptions-clob.polymarket.com/ws/market
    - Subscription: {"assets_ids": ["token_id"], "type": "market"}
    - Events: book (orderbook), price_change (bid/ask), last_trade_price

    Speed optimizations:
    - Symbol ID caching (avoid repeated DB lookups)
    - Precomputed spread and arbitrage flags
    - Async database inserts
    - Non-blocking Redis publish
    """

    def __init__(self, db_conn, config: Dict = None):
        """
        Initialize Polymarket WebSocket provider.

        Args:
            db_conn: PostgreSQL database connection
            config: Optional configuration dict

        Note: No API key required for public market data
        """
        self.conn = db_conn
        self.ws = None
        self.subscribed_assets: Set[str] = set()  # Track subscribed token IDs

        # Configuration
        self.config = config or {}
        self.ws_url = self.config.get('ws_url', 'wss://ws-subscriptions-clob.polymarket.com/ws/market')
        self.spread_threshold = Decimal(self.config.get('spread_threshold', '0.98'))

        # Fee structure (2026): Most markets are fee-free!
        # Fee configuration
        # CLOB (Central Limit Order Book) = NO GAS FEES!
        # Orders matched off-chain, only settlement on-chain
        # Political/sports markets: ZERO trading fees
        # Only 15-minute crypto markets have fees (we don't trade those)
        self.fee_rate = Decimal(self.config.get('fee_rate', '0.00'))
        self.min_position_size = Decimal(self.config.get('min_position_size', '100'))

        # Performance optimization: cache symbol IDs
        self.symbol_cache: Dict[str, int] = {}

        # Market price cache: stores latest prices for each market
        # Key: market_id, Value: {'yes_bid', 'yes_ask', 'no_bid', 'no_ask', 'timestamp'}
        self.market_prices: Dict[str, Dict] = {}

        # Connection state
        self.is_connected = False
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = 60  # Max 60 seconds

        logger.info("Polymarket WebSocket provider initialized")

    async def connect(self) -> bool:
        """
        Connect to Polymarket WebSocket.

        No authentication required for public market data.

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"Connecting to Polymarket WebSocket: {self.ws_url}")

            # No auth headers needed for public market data
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10
            )

            self.is_connected = True
            self.reconnect_delay = 1  # Reset delay on successful connect

            logger.success("Connected to Polymarket WebSocket")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Polymarket: {e}")
            self.is_connected = False
            return False

    async def subscribe_assets(self, asset_ids: list[str]) -> bool:
        """
        Subscribe to order book updates for multiple assets.

        Each binary market has TWO assets (YES and NO tokens).
        Subscribe to both to get complete orderbook data.

        Args:
            asset_ids: List of Polymarket token IDs (e.g., ["123", "456"])

        Returns:
            True if subscribed successfully
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot subscribe")
            return False

        try:
            # Real Polymarket WebSocket subscription format
            subscribe_msg = {
                "assets_ids": asset_ids,
                "type": "market"
            }

            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_assets.update(asset_ids)

            logger.info(f"Subscribed to {len(asset_ids)} assets")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to assets: {e}")
            return False

    async def unsubscribe_assets(self, asset_ids: list[str]) -> bool:
        """
        Unsubscribe from asset updates.

        Args:
            asset_ids: List of Polymarket token IDs

        Returns:
            True if unsubscribed successfully
        """
        if not self.is_connected:
            return False

        try:
            # Note: Unsubscribe format may differ - need to verify
            unsubscribe_msg = {
                "assets_ids": asset_ids,
                "type": "unsubscribe"
            }

            await self.ws.send(json.dumps(unsubscribe_msg))
            for asset_id in asset_ids:
                self.subscribed_assets.discard(asset_id)

            logger.info(f"Unsubscribed from {len(asset_ids)} assets")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe from assets: {e}")
            return False

    async def process_message(self, message):
        """
        Process incoming WebSocket message.

        Speed critical: Target <10ms processing time

        Polymarket sends two message types:

        1. Price change events:
        {
            'market': '0xabc...',
            'event_type': 'price_change',
            'timestamp': '1768064235288',
            'price_changes': [
                {
                    'asset_id': '123...',
                    'price': '0.5',
                    'size': '100',
                    'side': 'BUY',
                    'best_bid': '0.49',
                    'best_ask': '0.51'
                },
                ...
            ]
        }

        2. Orderbook snapshots (arrays):
        [
            {
                'market': '0xabc...',
                'asset_id': '123...',
                'timestamp': '1768064050386',
                'bids': [{'price': '0.5', 'size': '100'}, ...],
                'asks': [{'price': '0.51', 'size': '200'}, ...]
            }
        ]

        Args:
            message: Parsed JSON message from WebSocket (list or dict)
        """
        try:
            # Handle price_change events (most common)
            if isinstance(message, dict) and message.get('event_type') == 'price_change':
                await self._process_price_change(message)
            # Handle orderbook snapshot arrays
            elif isinstance(message, list):
                for update in message:
                    if isinstance(update, dict):
                        await self._process_orderbook_update(update)
            # Handle single orderbook update dict
            elif isinstance(message, dict):
                await self._process_orderbook_update(message)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _process_price_change(self, data: Dict):
        """
        Process price_change event from Polymarket.

        Message format:
        {
            'market': '0x1fbb...',
            'event_type': 'price_change',
            'timestamp': '1768064235288',
            'price_changes': [
                {
                    'asset_id': '113539...',
                    'price': '0.002',
                    'size': '3567.87',
                    'side': 'BUY',
                    'best_bid': '0.003',
                    'best_ask': '0.006'
                },
                ...
            ]
        }
        """
        import time
        start_time = time.perf_counter()

        market_id = data.get('market')
        timestamp_ms = data.get('timestamp')
        price_changes = data.get('price_changes', [])

        if not market_id or not timestamp_ms:
            return

        # Parse timestamp from Unix milliseconds
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp_ms}: {e}")
            return

        # Process each price change
        for change in price_changes:
            asset_id = change.get('asset_id')
            best_bid_str = change.get('best_bid')
            best_ask_str = change.get('best_ask')

            if not asset_id or not best_bid_str or not best_ask_str:
                continue

            # Convert to Decimal
            best_bid = Decimal(str(best_bid_str))
            best_ask = Decimal(str(best_ask_str))
            mid_price = (best_bid + best_ask) / 2

            # Determine if this is YES or NO token
            is_yes_token = await self._is_yes_token(market_id, asset_id)
            if is_yes_token is None:
                continue

            # Get symbol_id
            symbol_id = await self._get_symbol_id(market_id)
            if not symbol_id:
                continue

            # Update market price cache
            if market_id not in self.market_prices:
                self.market_prices[market_id] = {}

            if is_yes_token:
                self.market_prices[market_id]['yes_bid'] = best_bid
                self.market_prices[market_id]['yes_ask'] = best_ask
            else:
                self.market_prices[market_id]['no_bid'] = best_bid
                self.market_prices[market_id]['no_ask'] = best_ask

            self.market_prices[market_id]['timestamp'] = timestamp
            self.market_prices[market_id]['symbol_id'] = symbol_id

            # Check if we have both YES and NO prices
            market_data = self.market_prices[market_id]
            if all(k in market_data for k in ['yes_bid', 'yes_ask', 'no_bid', 'no_ask']):
                detection_time = time.perf_counter()

                # FAST PATH: Check for arbitrage BEFORE database insert (sub-second detection)
                spread = market_data['yes_ask'] + market_data['no_ask']

                # Immediate arbitrage alert (no DB latency)
                if spread < self.spread_threshold:
                    alert_time = time.perf_counter()
                    gross_profit = Decimal('1.00') - spread
                    profit_pct = (gross_profit / spread) * 100

                    # Calculate latencies
                    ws_to_detection_ms = (detection_time - start_time) * 1000
                    ws_to_alert_ms = (alert_time - start_time) * 1000

                    logger.success(
                        f"🚨 INSTANT ARBITRAGE! {market_id[:8]}... | "
                        f"Spread: ${spread:.4f} | Profit: {profit_pct:.2f}% | "
                        f"YES: {market_data['yes_ask']:.3f} NO: {market_data['no_ask']:.3f} | "
                        f"⚡ {ws_to_alert_ms:.2f}ms (detection: {ws_to_detection_ms:.2f}ms)"
                    )

                # Then insert to database (async, non-blocking)
                db_start = time.perf_counter()
                await self._insert_market_price(market_id, market_data)
                db_end = time.perf_counter()

                # Log timing for performance monitoring (only occasionally to avoid log spam)
                if spread < self.spread_threshold:
                    total_ms = (db_end - start_time) * 1000
                    db_ms = (db_end - db_start) * 1000
                    logger.info(f"⏱️  Total: {total_ms:.2f}ms | DB: {db_ms:.2f}ms")

    async def _process_orderbook_update(self, data: Dict):
        """
        Process order book update and insert into database.

        Speed critical: <10ms total

        Actual message format from Polymarket CLOB:
        {
            'market': '0xaf9d0e...',  # Market ID (hex string)
            'asset_id': '4153292...',  # Token ID (YES or NO)
            'timestamp': '1768064050386',  # Unix timestamp in milliseconds
            'bids': [{'price': '0.5', 'size': '100'}, ...],
            'asks': [{'price': '0.51', 'size': '200'}, ...]
        }
        """
        import time
        start_time = time.perf_counter()

        market_id = data.get('market')
        asset_id = data.get('asset_id')
        timestamp_ms = data.get('timestamp')
        bids = data.get('bids', [])
        asks = data.get('asks', [])

        if not market_id or not asset_id or not timestamp_ms:
            return

        # Parse timestamp from Unix milliseconds
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp_ms}: {e}")
            return

        # Extract best bid/ask
        if not bids or not asks:
            return

        best_bid = Decimal(str(bids[0]['price']))
        best_ask = Decimal(str(asks[0]['price']))
        bid_size = Decimal(str(bids[0]['size']))
        ask_size = Decimal(str(asks[0]['size']))
        mid_price = (best_bid + best_ask) / 2

        # Determine if this is YES or NO token
        # Look up in database to see which token this is
        is_yes_token = await self._is_yes_token(market_id, asset_id)
        if is_yes_token is None:
            # Market not in our database
            return

        # Get symbol_id (use cache for speed)
        symbol_id = await self._get_symbol_id(market_id)
        if not symbol_id:
            return

        # Update market price cache
        if market_id not in self.market_prices:
            self.market_prices[market_id] = {}

        if is_yes_token:
            self.market_prices[market_id]['yes_bid'] = best_bid
            self.market_prices[market_id]['yes_ask'] = best_ask
        else:
            self.market_prices[market_id]['no_bid'] = best_bid
            self.market_prices[market_id]['no_ask'] = best_ask

        self.market_prices[market_id]['timestamp'] = timestamp
        self.market_prices[market_id]['symbol_id'] = symbol_id

        # Check if we have both YES and NO prices
        market_data = self.market_prices[market_id]
        if all(k in market_data for k in ['yes_bid', 'yes_ask', 'no_bid', 'no_ask']):
            detection_time = time.perf_counter()

            # FAST PATH: Check for arbitrage BEFORE database insert (sub-second detection)
            spread = market_data['yes_ask'] + market_data['no_ask']

            # Immediate arbitrage alert (no DB latency)
            if spread < self.spread_threshold:
                alert_time = time.perf_counter()
                gross_profit = Decimal('1.00') - spread
                profit_pct = (gross_profit / spread) * 100

                # Calculate latencies
                ws_to_detection_ms = (detection_time - start_time) * 1000
                ws_to_alert_ms = (alert_time - start_time) * 1000

                logger.success(
                    f"🚨 INSTANT ARBITRAGE! {market_id[:8]}... | "
                    f"Spread: ${spread:.4f} | Profit: {profit_pct:.2f}% | "
                    f"YES: {market_data['yes_ask']:.3f} NO: {market_data['no_ask']:.3f} | "
                    f"⚡ {ws_to_alert_ms:.2f}ms (detection: {ws_to_detection_ms:.2f}ms)"
                )

            # Then insert to database (async, non-blocking)
            db_start = time.perf_counter()
            await self._insert_market_price(market_id, market_data)
            db_end = time.perf_counter()

            # Log timing for performance monitoring
            if spread < self.spread_threshold:
                total_ms = (db_end - start_time) * 1000
                db_ms = (db_end - db_start) * 1000
                logger.info(f"⏱️  Total: {total_ms:.2f}ms | DB: {db_ms:.2f}ms")

    async def _get_symbol_id(self, market_id: str) -> Optional[int]:
        """
        Get symbol ID for a market (with caching).

        Speed optimization: Cached lookups are ~100x faster

        Args:
            market_id: Polymarket market ID

        Returns:
            Symbol ID or None
        """
        # Check cache first
        if market_id in self.symbol_cache:
            return self.symbol_cache[market_id]

        # Query database (wrapped for async)
        try:
            def _query():
                cur = self.conn.cursor()
                cur.execute("""
                    SELECT s.id
                    FROM symbols s
                    JOIN binary_markets bm ON s.id = bm.symbol_id
                    WHERE bm.market_id = %s
                """, (market_id,))
                row = cur.fetchone()
                return row[0] if row else None

            symbol_id = await asyncio.to_thread(_query)

            if symbol_id:
                self.symbol_cache[market_id] = symbol_id

            return symbol_id

        except Exception as e:
            logger.error(f"Error looking up symbol ID: {e}")
            return None

    async def _is_yes_token(self, market_id: str, asset_id: str) -> Optional[bool]:
        """
        Determine if asset_id is YES (True) or NO (False) token for a market.

        Args:
            market_id: Polymarket market ID (hex string)
            asset_id: Token ID to check

        Returns:
            True if YES token, False if NO token, None if market not found
        """
        # Check cache first
        cache_key = f"{market_id}:{asset_id}"
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]

        # Query database
        try:
            def _query():
                cur = self.conn.cursor()
                cur.execute("""
                    SELECT yes_token_id, no_token_id
                    FROM binary_markets
                    WHERE market_id = %s
                """, (market_id,))
                row = cur.fetchone()
                return row if row else None

            result = await asyncio.to_thread(_query)

            if not result:
                return None

            yes_token_id, no_token_id = result

            if asset_id == yes_token_id:
                self.symbol_cache[cache_key] = True
                return True
            elif asset_id == no_token_id:
                self.symbol_cache[cache_key] = False
                return False
            else:
                # Asset ID doesn't match either token
                return None

        except Exception as e:
            logger.error(f"Error checking token type: {e}")
            return None

    async def _insert_market_price(self, market_id: str, market_data: Dict):
        """
        Insert combined YES/NO price data into binary_prices table.

        Args:
            market_id: Polymarket market ID
            market_data: Dict with yes_bid, yes_ask, no_bid, no_ask, timestamp, symbol_id
        """
        try:
            timestamp = market_data['timestamp']
            symbol_id = market_data['symbol_id']
            yes_bid = market_data['yes_bid']
            yes_ask = market_data['yes_ask']
            no_bid = market_data['no_bid']
            no_ask = market_data['no_ask']

            # Calculate mid prices
            yes_mid = (yes_bid + yes_ask) / 2
            no_mid = (no_bid + no_ask) / 2

            # Calculate spread (what we'd pay to buy both YES and NO)
            spread = yes_ask + no_ask

            # Check if arbitrage opportunity exists
            is_arbitrage = spread < self.spread_threshold

            # Calculate estimated profit percentage
            # CLOB = NO FEES! Simple calculation: profit = $1.00 - spread
            if spread > 0:
                gross_profit = Decimal('1.00') - spread

                # Apply trading fees (0% for political/sports markets)
                net_profit = gross_profit - (spread * self.fee_rate)
                estimated_profit_pct = (net_profit / spread) * 100
            else:
                estimated_profit_pct = Decimal('0')

            # Insert into database
            def _insert():
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT INTO binary_prices (
                        timestamp, symbol_id,
                        yes_bid, yes_ask, yes_mid, yes_volume,
                        no_bid, no_ask, no_mid, no_volume,
                        spread, arbitrage_opportunity, estimated_profit_pct
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (timestamp, symbol_id) DO UPDATE SET
                        yes_bid = EXCLUDED.yes_bid,
                        yes_ask = EXCLUDED.yes_ask,
                        yes_mid = EXCLUDED.yes_mid,
                        no_bid = EXCLUDED.no_bid,
                        no_ask = EXCLUDED.no_ask,
                        no_mid = EXCLUDED.no_mid,
                        spread = EXCLUDED.spread,
                        arbitrage_opportunity = EXCLUDED.arbitrage_opportunity,
                        estimated_profit_pct = EXCLUDED.estimated_profit_pct
                """, (
                    timestamp, symbol_id,
                    yes_bid, yes_ask, yes_mid, 0,  # volume not available from price_change events
                    no_bid, no_ask, no_mid, 0,
                    spread, is_arbitrage, estimated_profit_pct
                ))
                self.conn.commit()

            await asyncio.to_thread(_insert)

            # Only log arbitrage opportunities (critical for speed)
            if is_arbitrage:
                logger.success(
                    f"🚨 ARBITRAGE! Market {market_id[:8]}... | "
                    f"Spread: ${spread:.4f} | Profit: {estimated_profit_pct:.2f}% | "
                    f"YES Ask: {yes_ask:.3f} + NO Ask: {no_ask:.3f}"
                )

        except Exception as e:
            logger.error(f"Error inserting market price: {e}")
            def _rollback():
                self.conn.rollback()
            await asyncio.to_thread(_rollback)

    async def _insert_price(
        self,
        timestamp: datetime,
        symbol_id: int,
        yes_bid: Decimal,
        yes_ask: Decimal,
        yes_mid: Decimal,
        yes_volume: int,
        no_bid: Decimal,
        no_ask: Decimal,
        no_mid: Decimal,
        no_volume: int,
        spread: Decimal,
        is_arbitrage: bool,
        estimated_profit_pct: Decimal
    ):
        """
        Insert price data into binary_prices table.

        Speed critical: <15ms database write
        """
        try:
            def _insert():
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT INTO binary_prices (
                        timestamp, symbol_id,
                        yes_bid, yes_ask, yes_mid, yes_volume,
                        no_bid, no_ask, no_mid, no_volume,
                        spread, arbitrage_opportunity, estimated_profit_pct
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (timestamp, symbol_id) DO UPDATE SET
                        yes_bid = EXCLUDED.yes_bid,
                        yes_ask = EXCLUDED.yes_ask,
                        yes_mid = EXCLUDED.yes_mid,
                        yes_volume = EXCLUDED.yes_volume,
                        no_bid = EXCLUDED.no_bid,
                        no_ask = EXCLUDED.no_ask,
                        no_mid = EXCLUDED.no_mid,
                        no_volume = EXCLUDED.no_volume,
                        spread = EXCLUDED.spread,
                        arbitrage_opportunity = EXCLUDED.arbitrage_opportunity,
                        estimated_profit_pct = EXCLUDED.estimated_profit_pct
                """, (
                    timestamp, symbol_id,
                    yes_bid, yes_ask, yes_mid, yes_volume,
                    no_bid, no_ask, no_mid, no_volume,
                    spread, is_arbitrage, estimated_profit_pct
                ))
                self.conn.commit()

            await asyncio.to_thread(_insert)

        except Exception as e:
            logger.error(f"Error inserting price: {e}")
            def _rollback():
                self.conn.rollback()
            await asyncio.to_thread(_rollback)

    async def listen(self):
        """
        Main message listening loop.

        Handles:
        - Receiving messages
        - Processing updates
        - Auto-reconnection on disconnect
        """
        while True:
            try:
                if not self.is_connected:
                    await self.connect()

                    # Re-subscribe to all assets after reconnect
                    assets_to_subscribe = list(self.subscribed_assets)
                    self.subscribed_assets.clear()

                    for asset_id in assets_to_subscribe:
                        await self.subscribe_assets([asset_id])

                # Listen for messages
                async for message in self.ws:
                    try:
                        data = json.loads(message)
                        await self.process_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                self.is_connected = False
                await asyncio.sleep(self.reconnect_delay)

                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

            except Exception as e:
                logger.error(f"Unexpected error in listen loop: {e}")
                await asyncio.sleep(5)

    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("Polymarket WebSocket closed")


# TODO: Add main function for testing
async def main():
    """
    Test the Polymarket provider.

    Usage:
        python -m app.providers.polymarket_ws
    """
    import os

    # Load config
    api_key = os.getenv('POLYMARKET_API_KEY', 'test_key')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_name = os.getenv('DB_NAME', 'trading')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', '')

    # Connect to database
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )

    # Create provider
    provider = PolymarketWebSocketProvider(
        api_key=api_key,
        db_conn=conn
    )

    # Connect and listen
    await provider.connect()

    # TODO: Subscribe to test markets
    # await provider.subscribe_market('0x1234abcd...')

    # Start listening
    await provider.listen()


if __name__ == '__main__':
    asyncio.run(main())
