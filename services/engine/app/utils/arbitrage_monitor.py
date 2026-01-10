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

        logger.info(
            f"Arbitrage monitor initialized | "
            f"Mode: {mode} | "
            f"Capital: ${capital} | "
            f"Spread threshold: ${spread_threshold} | "
            f"Min profit: {min_profit_pct * 100:.2f}%"
        )

    async def start(self):
        """Start monitoring for arbitrage opportunities."""
        try:
            # Connect to WebSocket
            connected = await self.ws_provider.connect()
            if not connected:
                logger.error("Failed to connect to Polymarket WebSocket")
                return

            # Get active markets from database
            markets = self._get_active_markets()
            if not markets:
                logger.warning("No active markets found in database. Run market_fetcher first.")
                return

            logger.info(f"Monitoring {len(markets)} markets for arbitrage opportunities")

            # Extract token IDs and subscribe
            token_ids = []
            for market in markets:
                # For now, we need to get token IDs from market data
                # TODO: Store token IDs in binary_markets table
                logger.info(f"Market: {market['question'][:60]}...")

            if not token_ids:
                logger.warning("No token IDs found. Need to fetch from Polymarket API.")
                # TODO: Fetch token IDs from Polymarket API
                return

            # Subscribe to all token IDs
            await self.ws_provider.subscribe_assets(token_ids)

            # Start monitoring loop
            await self._monitoring_loop()

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            await self.stop()
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            raise

    async def _monitoring_loop(self):
        """Main monitoring loop - process WebSocket messages."""
        try:
            async for message in self.ws_provider.ws:
                try:
                    import json
                    data = json.loads(message)
                    await self.ws_provider.process_message(data)

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
                ORDER BY bm.end_date ASC
                LIMIT 50
            """)

            markets = []
            for row in cur.fetchall():
                markets.append({
                    'id': row[0],
                    'market_id': row[1],
                    'question': row[2],
                    'category': row[3],
                    'end_date': row[4],
                    'symbol': row[5],
                    'symbol_id': row[6]
                })

            return markets

        except Exception as e:
            logger.error(f"Failed to get active markets: {e}")
            return []

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

    # Start monitoring
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()
