"""
Polymarket Arbitrage Monitor

Real-time monitoring script for binary options arbitrage opportunities.
Connects to Polymarket WebSocket and scans for profitable spreads.

Modes:
- Paper Trading: Simulate trades and track hypothetical P&L
- Live Trading: Execute real arbitrage trades (requires API credentials)
- Monitor Only: Just log opportunities without trading

Usage:
    # Monitor only (read-only)
    python -m app.utils.arbitrage_monitor --mode monitor

    # Paper trading
    python -m app.utils.arbitrage_monitor --mode paper --capital 500

    # Live trading (requires POLYMARKET_PRIVATE_KEY)
    python -m app.utils.arbitrage_monitor --mode live --capital 400

Performance Targets:
- WebSocket latency: <50ms
- Opportunity detection: <10ms
- Total pipeline: <100ms
"""

import asyncio
import argparse
import os
import sys
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
import psycopg2
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.polymarket_ws import PolymarketWebSocketProvider
from strategies.arbitrage_strategy import ArbitrageStrategy
from trading.polymarket_client import PolymarketTradingClient

load_dotenv()


class ArbitrageMonitor:
    """
    Real-time arbitrage monitor for Polymarket binary options.

    Workflow:
    1. Connect to Polymarket WebSocket
    2. Subscribe to YES/NO token pairs for all tracked markets
    3. Monitor for spread < threshold (e.g., $0.995)
    4. Calculate profit after fees (0% for political/sports!)
    5. Execute or simulate trades based on mode
    6. Track P&L and performance metrics
    """

    def __init__(
        self,
        db_conn,
        mode: str = 'monitor',
        capital: Decimal = Decimal('500'),
        spread_threshold: Decimal = Decimal('0.995'),
        min_profit_pct: Decimal = Decimal('0.005')  # 0.5%
    ):
        """
        Initialize arbitrage monitor.

        Args:
            db_conn: PostgreSQL database connection
            mode: 'monitor', 'paper', or 'live'
            capital: Starting capital for paper/live trading
            spread_threshold: Maximum spread to execute (e.g., 0.995)
            min_profit_pct: Minimum profit percentage required (e.g., 0.005 = 0.5%)
        """
        self.conn = db_conn
        self.mode = mode
        self.capital = capital
        self.spread_threshold = spread_threshold
        self.min_profit_pct = min_profit_pct

        # Initialize WebSocket provider
        self.ws_provider = PolymarketWebSocketProvider(
            db_conn=db_conn,
            config={
                'spread_threshold': str(spread_threshold),
                'fee_rate': '0.00'  # Zero fees for political/sports!
            }
        )

        # Initialize trading client (if live mode)
        self.trading_client = None
        if mode == 'live':
            private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
            if not private_key:
                raise ValueError("POLYMARKET_PRIVATE_KEY required for live trading")
            self.trading_client = PolymarketTradingClient(private_key=private_key)

        # Initialize strategy
        self.strategy = ArbitrageStrategy(
            db_conn=db_conn,
            trading_client=self.trading_client,
            config={
                'spread_threshold': str(spread_threshold),
                'min_profit_pct': str(min_profit_pct),
                'max_position_size': '100',
                'max_total_exposure': str(capital * Decimal('0.8')),  # 80% of capital
                'fee_rate': '0.00'
            }
        )

        # Performance tracking
        self.opportunities_found = 0
        self.trades_executed = 0
        self.paper_pnl = Decimal('0')
        self.start_time = datetime.now()

        # Price tracking for YES/NO tokens
        # Maps token_id -> {price, volume, timestamp, market_id, outcome}
        self.token_prices = {}

        # Token-to-market mapping cache
        # Maps token_id -> {symbol_id, market_id, outcome: 'YES'/'NO'}
        self.token_market_map = {}

        logger.info(
            f"Arbitrage monitor initialized | "
            f"Mode: {mode} | "
            f"Capital: ${capital} | "
            f"Spread threshold: ${spread_threshold} | "
            f"Min profit: {min_profit_pct * 100:.2f}%"
        )

    def _build_token_market_map(self):
        """
        Build mapping from token IDs to markets.

        Queries database for all active markets and creates bidirectional
        mapping: token_id -> {symbol_id, market_id, outcome}
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT
                    bm.yes_token_id,
                    bm.no_token_id,
                    bm.market_id,
                    s.id as symbol_id
                FROM binary_markets bm
                JOIN symbols s ON bm.symbol_id = s.id
                WHERE bm.status = 'active'
                    AND bm.end_date > NOW()
                    AND bm.yes_token_id IS NOT NULL
                    AND bm.no_token_id IS NOT NULL
            """)

            for row in cur.fetchall():
                yes_token_id, no_token_id, market_id, symbol_id = row

                self.token_market_map[yes_token_id] = {
                    'symbol_id': symbol_id,
                    'market_id': market_id,
                    'outcome': 'YES'
                }
                self.token_market_map[no_token_id] = {
                    'symbol_id': symbol_id,
                    'market_id': market_id,
                    'outcome': 'NO'
                }

            logger.info(f"Built token-market mapping for {len(self.token_market_map)} tokens")

        except Exception as e:
            logger.error(f"Failed to build token-market map: {e}")

    async def _process_ws_message(self, message: Dict):
        """
        Process WebSocket message and insert price data.

        Handles Polymarket WebSocket events:
        - "book": Full orderbook snapshot
        - "price_change": Best bid/ask update
        - "last_trade_price": Trade data (ignored for now)

        Args:
            message: Parsed JSON message from WebSocket
        """
        try:
            event_type = message.get('event_type')

            if event_type == 'book':
                await self._process_book_event(message)
            elif event_type == 'price_change':
                await self._process_price_change_event(message)
            elif event_type == 'last_trade_price':
                # Trade data - can be used for volume analysis later
                pass

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def _process_book_event(self, message: Dict):
        """
        Process "book" event - full orderbook snapshot.

        Format:
        {
            "event_type": "book",
            "asset_id": "token_id",
            "timestamp": "2026-01-10T...",
            "bids": [[price, size], ...],
            "asks": [[price, size], ...]
        }
        """
        asset_id = message.get('asset_id')
        if not asset_id or asset_id not in self.token_market_map:
            return

        timestamp_str = message.get('timestamp')
        bids = message.get('bids', [])
        asks = message.get('asks', [])

        if not bids or not asks:
            return

        # Parse prices
        best_bid = Decimal(str(bids[0][0]))
        best_ask = Decimal(str(asks[0][0]))
        volume = int(asks[0][1])  # Volume at best ask

        # Update token price cache
        self.token_prices[asset_id] = {
            'bid': best_bid,
            'ask': best_ask,
            'mid': (best_bid + best_ask) / 2,
            'volume': volume,
            'timestamp': timestamp_str,
            'market_info': self.token_market_map[asset_id]
        }

        # Try to insert price data (if we have both YES and NO)
        await self._try_insert_price_data(asset_id)

    async def _process_price_change_event(self, message: Dict):
        """
        Process "price_change" event - best bid/ask update.

        Format:
        {
            "event_type": "price_change",
            "asset_id": "token_id",
            "timestamp": "2026-01-10T...",
            "best_bid": 0.52,
            "best_ask": 0.53
        }
        """
        asset_id = message.get('asset_id')
        if not asset_id or asset_id not in self.token_market_map:
            return

        timestamp_str = message.get('timestamp')
        best_bid = message.get('best_bid')
        best_ask = message.get('best_ask')

        if best_bid is None or best_ask is None:
            return

        # Update token price cache
        self.token_prices[asset_id] = {
            'bid': Decimal(str(best_bid)),
            'ask': Decimal(str(best_ask)),
            'mid': (Decimal(str(best_bid)) + Decimal(str(best_ask))) / 2,
            'volume': 0,  # Volume not provided in price_change events
            'timestamp': timestamp_str,
            'market_info': self.token_market_map[asset_id]
        }

        # Try to insert price data (if we have both YES and NO)
        await self._try_insert_price_data(asset_id)

    async def _try_insert_price_data(self, trigger_token_id: str):
        """
        Attempt to insert price data for a market if we have both YES and NO prices.

        Args:
            trigger_token_id: Token ID that just received an update
        """
        # Get market info for this token
        market_info = self.token_market_map.get(trigger_token_id)
        if not market_info:
            return

        symbol_id = market_info['symbol_id']
        market_id = market_info['market_id']

        # Find both YES and NO tokens for this market
        yes_token_id = None
        no_token_id = None

        for token_id, info in self.token_market_map.items():
            if info['market_id'] == market_id:
                if info['outcome'] == 'YES':
                    yes_token_id = token_id
                elif info['outcome'] == 'NO':
                    no_token_id = token_id

        if not yes_token_id or not no_token_id:
            return

        # Check if we have prices for both
        yes_price = self.token_prices.get(yes_token_id)
        no_price = self.token_prices.get(no_token_id)

        if not yes_price or not no_price:
            return  # Don't have both prices yet

        # Use the most recent timestamp
        timestamp_str = max(yes_price['timestamp'], no_price['timestamp'])
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

        # Calculate spread and arbitrage opportunity
        yes_ask = yes_price['ask']
        no_ask = no_price['ask']
        spread = yes_ask + no_ask

        is_arbitrage = spread < self.spread_threshold

        # Calculate estimated profit percentage
        if spread > 0:
            gross_profit = Decimal('1.00') - spread
            # Zero fees for political/sports markets!
            fees = Decimal('0')
            net_profit = gross_profit - fees
            estimated_profit_pct = (net_profit / spread) * 100
        else:
            estimated_profit_pct = Decimal('0')

        # Insert into database
        try:
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
                yes_price['bid'], yes_price['ask'], yes_price['mid'], yes_price['volume'],
                no_price['bid'], no_price['ask'], no_price['mid'], no_price['volume'],
                spread, is_arbitrage, estimated_profit_pct
            ))
            self.conn.commit()

            # Log arbitrage opportunities
            if is_arbitrage:
                logger.info(
                    f"💰 ARBITRAGE: {market_id} | "
                    f"Spread: ${spread:.4f} | "
                    f"Profit: {estimated_profit_pct:.2f}%"
                )

        except Exception as e:
            logger.error(f"Error inserting price data: {e}")
            self.conn.rollback()

    async def start(self, enable_early_exit: bool = True):
        """
        Start monitoring for arbitrage opportunities.

        Args:
            enable_early_exit: If True, monitor positions for early exit
        """
        try:
            # Build token-to-market mapping from database
            self._build_token_market_map()

            if not self.token_market_map:
                logger.error("No markets with token IDs found. Run market_fetcher first.")
                return

            # Connect to WebSocket
            connected = await self.ws_provider.connect()
            if not connected:
                logger.error("Failed to connect to Polymarket WebSocket")
                return

            # Get all token IDs to subscribe
            token_ids = list(self.token_market_map.keys())
            logger.info(f"Subscribing to {len(token_ids)} tokens ({len(token_ids) // 2} markets)")

            # Subscribe to all token IDs
            await self.ws_provider.subscribe_assets(token_ids)

            # Run monitoring loop and position monitor in parallel
            await asyncio.gather(
                self._monitoring_loop(),
                self.monitor_positions_for_exit(enable_early_exit)
            )

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            await self.stop()
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            raise

    async def _monitoring_loop(self):
        """Main monitoring loop - process WebSocket messages."""
        try:
            import json

            async for message in self.ws_provider.ws:
                try:
                    data = json.loads(message)

                    # Process message and insert into database
                    await self._process_ws_message(data)

                    # Check for arbitrage opportunities
                    await self._check_opportunities()

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")

    async def _check_opportunities(self):
        """
        Check for arbitrage opportunities and execute/simulate trades.

        This runs after every price update to detect opportunities quickly.
        """
        # Scan for opportunities using strategy
        opportunities = self.strategy.scan_opportunities()

        for opp in opportunities:
            self.opportunities_found += 1

            symbol = opp['symbol']
            spread = opp['spread']
            estimated_profit_pct = opp['estimated_profit_pct']
            question = opp['question']

            logger.info(
                f"💰 ARBITRAGE OPPORTUNITY #{self.opportunities_found} | "
                f"{symbol} | "
                f"Spread: ${spread:.4f} | "
                f"Profit: {estimated_profit_pct:.2f}% | "
                f"{question[:40]}..."
            )

            # Execute based on mode
            if self.mode == 'monitor':
                # Just log, don't trade
                pass

            elif self.mode == 'paper':
                # Simulate trade
                await self._simulate_trade(opp)

            elif self.mode == 'live':
                # Execute real trade
                await self._execute_trade(opp)

    async def _simulate_trade(self, opp: Dict):
        """
        Simulate a paper trade for an arbitrage opportunity.

        Args:
            opp: Opportunity dict from strategy
        """
        symbol = opp['symbol']
        spread = opp['spread']
        yes_ask = opp['yes_ask']
        no_ask = opp['no_ask']

        # Calculate position size (10% of capital per trade)
        position_size = min(Decimal('100'), self.capital * Decimal('0.1'))

        # Calculate profit
        cost = spread * position_size
        payout = Decimal('1.00') * position_size
        profit = payout - cost

        # Update paper P&L
        self.paper_pnl += profit
        self.trades_executed += 1

        logger.success(
            f"📝 PAPER TRADE #{self.trades_executed} | "
            f"{symbol} | "
            f"Size: ${position_size:.2f} | "
            f"Profit: ${profit:.4f} | "
            f"Total P&L: ${self.paper_pnl:.2f}"
        )

    async def _execute_trade(self, opp: Dict):
        """
        Execute a real arbitrage trade.

        Args:
            opp: Opportunity dict from strategy
        """
        if not self.trading_client:
            logger.error("Trading client not initialized")
            return

        symbol = opp['symbol']
        market_id = opp['market_id']
        yes_ask = opp['yes_ask']
        no_ask = opp['no_ask']

        # TODO: Get token IDs for this market
        # yes_token_id = ...
        # no_token_id = ...

        # Calculate position size
        position_size = self.strategy.calculate_position_size(yes_ask + no_ask)

        try:
            # Execute arbitrage via strategy
            success = await self.strategy.execute_arbitrage(
                symbol=symbol,
                market_id=market_id,
                yes_ask=yes_ask,
                no_ask=no_ask
            )

            if success:
                self.trades_executed += 1
                logger.success(f"✅ LIVE TRADE #{self.trades_executed} executed: {symbol}")
            else:
                logger.warning(f"❌ Trade failed: {symbol}")

        except Exception as e:
            logger.error(f"Trade execution error: {e}")

    def _get_active_markets(self) -> List[Dict]:
        """
        Get active markets from database.

        Returns:
            List of market dicts
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT
                    bm.id,
                    bm.market_id,
                    bm.yes_token_id,
                    bm.no_token_id,
                    bm.question,
                    bm.category,
                    bm.end_date,
                    s.symbol,
                    s.id as symbol_id
                FROM binary_markets bm
                JOIN symbols s ON bm.symbol_id = s.id
                WHERE bm.status = 'active'
                    AND bm.end_date > NOW()
                    AND bm.category IN ('politics', 'sports')  -- Zero fees!
                    AND bm.yes_token_id IS NOT NULL
                    AND bm.no_token_id IS NOT NULL
                ORDER BY bm.end_date ASC
                LIMIT 50
            """)

            markets = []
            for row in cur.fetchall():
                markets.append({
                    'id': row[0],
                    'market_id': row[1],
                    'yes_token_id': row[2],
                    'no_token_id': row[3],
                    'question': row[4],
                    'category': row[5],
                    'end_date': row[6],
                    'symbol': row[7],
                    'symbol_id': row[8]
                })

            return markets

        except Exception as e:
            logger.error(f"Failed to get active markets: {e}")
            return []

    async def monitor_positions_for_exit(self, enable_early_exit: bool = True):
        """
        Monitor open positions for early exit opportunities.

        Runs continuously in background, checking every 60 seconds.
        Exits positions when spread normalizes to >= $1.00.

        Args:
            enable_early_exit: If True, automatically exit when profitable
        """
        if not enable_early_exit:
            logger.info("Early exit monitoring disabled")
            return

        logger.info("Starting early exit position monitor (checks every 60s)")
        early_exits = 0
        early_exit_profits = Decimal('0')

        while True:
            try:
                # Get open positions
                positions = self.strategy.get_open_positions()

                for position in positions:
                    # Get current spread (would need to query latest prices)
                    # For now, this is a placeholder - actual implementation
                    # would fetch current YES/NO prices from database
                    current_spread = await self._get_current_spread(
                        position['symbol_id']
                    )

                    if current_spread is None:
                        continue

                    # Check if should exit
                    should_exit, reason = self._should_exit_position(
                        position, current_spread
                    )

                    if should_exit:
                        logger.info(
                            f"🚪 EXIT SIGNAL: {position['symbol']} | "
                            f"Entry: ${position['entry_spread']:.4f} | "
                            f"Current: ${current_spread:.4f} | "
                            f"Reason: {reason}"
                        )

                        # Exit the position
                        success = await self._exit_position(
                            position, current_spread, reason
                        )

                        if success:
                            early_exits += 1
                            profit = current_spread - position['entry_spread']
                            early_exit_profits += profit

                            logger.success(
                                f"✅ EARLY EXIT #{early_exits} | "
                                f"{position['symbol']} | "
                                f"Profit: ${profit:.4f} | "
                                f"Hold time: {self._calc_hold_time(position)} min"
                            )

                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in position monitor: {e}")
                await asyncio.sleep(60)

    async def _get_current_spread(self, symbol_id: int) -> Optional[Decimal]:
        """
        Get current spread for a market.

        Args:
            symbol_id: Symbol ID from database

        Returns:
            Current spread (YES ask + NO ask) or None
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT yes_ask, no_ask, spread
                FROM binary_prices
                WHERE symbol_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol_id,))

            row = cur.fetchone()
            if row:
                return Decimal(str(row[2]))  # spread column
            return None

        except Exception as e:
            logger.error(f"Error getting current spread: {e}")
            return None

    def _should_exit_position(
        self, position: Dict, current_spread: Decimal
    ) -> tuple[bool, str]:
        """
        Determine if position should be exited early.

        Exit criteria:
        1. Spread normalized to >= $1.00 (take guaranteed profit)
        2. Spread > $1.02 (bonus profit opportunity)
        3. Near resolution (< 24 hours) and spread >= $0.99

        Args:
            position: Position dict
            current_spread: Current market spread

        Returns:
            Tuple of (should_exit: bool, reason: str)
        """
        entry_spread = position['entry_spread']

        # Exit if spread normalized or better
        if current_spread >= Decimal('1.00'):
            return True, "Spread normalized to $1.00+"

        # Exit if massive spread widening (bonus profit)
        if current_spread > Decimal('1.02'):
            return True, f"Bonus profit (spread ${current_spread:.4f})"

        # Check time to resolution
        end_date = position.get('end_date')
        if end_date:
            hours_to_resolution = (end_date - datetime.now()).total_seconds() / 3600
            if hours_to_resolution < 24 and current_spread >= Decimal('0.99'):
                return True, "Near resolution, close enough"

        return False, ""

    async def _exit_position(
        self, position: Dict, current_spread: Decimal, reason: str
    ) -> bool:
        """
        Exit a position by selling both YES and NO.

        For paper trading: Simulates the exit
        For live trading: Executes real sell orders

        Args:
            position: Position dict
            current_spread: Current spread
            reason: Exit reason

        Returns:
            True if exit successful
        """
        try:
            if self.mode == 'paper':
                # Simulate exit for paper trading
                profit = current_spread - position['entry_spread']
                self.paper_pnl += profit

                logger.info(
                    f"📝 PAPER EXIT: {position['symbol']} | "
                    f"Profit: ${profit:.4f} | "
                    f"Reason: {reason}"
                )
                return True

            elif self.mode == 'live':
                # TODO: Implement real exit via trading client
                # yes_response = await self.trading_client.place_market_order(
                #     token_id=position['yes_token_id'],
                #     amount=position['yes_qty'],
                #     side="SELL"
                # )
                # no_response = await self.trading_client.place_market_order(
                #     token_id=position['no_token_id'],
                #     amount=position['no_qty'],
                #     side="SELL"
                # )
                logger.warning("Live exit not yet implemented")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to exit position: {e}")
            return False

    def _calc_hold_time(self, position: Dict) -> int:
        """
        Calculate hold time in minutes.

        Args:
            position: Position dict

        Returns:
            Hold time in minutes
        """
        opened_at = position.get('opened_at')
        if opened_at:
            return int((datetime.now() - opened_at).total_seconds() / 60)
        return 0

    async def stop(self):
        """Stop monitoring and cleanup."""
        if self.ws_provider and self.ws_provider.ws:
            await self.ws_provider.close()

        # Print final statistics
        runtime = (datetime.now() - self.start_time).total_seconds()
        logger.info(
            f"\n📊 MONITORING STATISTICS\n"
            f"Runtime: {runtime:.0f}s ({runtime/60:.1f} minutes)\n"
            f"Opportunities found: {self.opportunities_found}\n"
            f"Trades executed: {self.trades_executed}\n"
            f"Paper P&L: ${self.paper_pnl:.2f}\n"
            f"Mode: {self.mode}"
        )

        self.conn.close()


def main():
    """Main entry point for arbitrage monitor."""
    parser = argparse.ArgumentParser(description='Monitor Polymarket for arbitrage opportunities')
    parser.add_argument('--mode', choices=['monitor', 'paper', 'live'], default='monitor',
                       help='Monitoring mode: monitor (log only), paper (simulate), live (execute)')
    parser.add_argument('--capital', type=float, default=500.0,
                       help='Starting capital for paper/live trading')
    parser.add_argument('--spread-threshold', type=float, default=0.995,
                       help='Maximum spread to execute (e.g., 0.995 = buy if YES+NO < $0.995)')
    parser.add_argument('--min-profit', type=float, default=0.005,
                       help='Minimum profit percentage (e.g., 0.005 = 0.5%%)')
    parser.add_argument('--early-exit', action='store_true', default=True,
                       help='Enable early exit when spread normalizes (default: enabled)')
    parser.add_argument('--no-early-exit', action='store_false', dest='early_exit',
                       help='Disable early exit, hold all positions to resolution')

    args = parser.parse_args()

    # Database connection
    db_conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'trading'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )

    # Create monitor
    monitor = ArbitrageMonitor(
        db_conn=db_conn,
        mode=args.mode,
        capital=Decimal(str(args.capital)),
        spread_threshold=Decimal(str(args.spread_threshold)),
        min_profit_pct=Decimal(str(args.min_profit))
    )

    # Log early exit status
    if args.early_exit:
        logger.info("🚀 Early exit enabled - will sell when spread normalizes to $1.00+")
    else:
        logger.info("⏳ Early exit disabled - holding all positions to resolution")

    # Start monitoring
    try:
        asyncio.run(monitor.start(enable_early_exit=args.early_exit))
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()
