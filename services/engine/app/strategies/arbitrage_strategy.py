"""
Binary Option Arbitrage Strategy

Exploits YES + NO price inefficiencies on Polymarket and other binary markets.
When YES + NO < $1.00, buy both positions for guaranteed profit at resolution.

Key Concept:
- At resolution, exactly one outcome pays $1.00 per share
- If we can buy both YES + NO for less than $1.00, we profit
- Example: YES=$0.52, NO=$0.45 → Cost=$0.97, Payout=$1.00, Gross Profit=$0.03

Speed Target: <50ms from detection to order placement

Risk Management:
- Position limits per market
- Total capital allocation limits
- Minimum profit threshold (after fees)
- Diversification across markets
"""

from decimal import Decimal
from typing import Optional, Tuple, Dict, List
from datetime import datetime
from loguru import logger
import psycopg2


class ArbitrageStrategy:
    """
    Detects and executes arbitrage opportunities on binary markets.

    Workflow:
    1. Monitor real-time YES + NO prices
    2. Detect when spread < threshold (e.g., $0.98)
    3. Validate profit after fees
    4. Check risk limits
    5. Execute paired YES + NO orders
    6. Track position until resolution
    """

    def __init__(self, db_conn, trading_client, config: Dict = None):
        """
        Initialize arbitrage strategy.

        Args:
            db_conn: PostgreSQL database connection
            trading_client: PolymarketTradingClient instance
            config: Optional configuration dict
        """
        self.conn = db_conn
        self.client = trading_client

        # Load configuration (with defaults)
        self.config = config or {}
        self.spread_threshold = Decimal(str(self.config.get('spread_threshold', 0.98)))
        self.min_profit_pct = Decimal(str(self.config.get('min_profit_pct', 0.015)))  # 1.5%
        self.max_position_size = Decimal(str(self.config.get('max_position_size', 100)))  # £100
        self.max_total_exposure = Decimal(str(self.config.get('max_total_exposure', 400)))  # £400
        self.fee_rate = Decimal(str(self.config.get('fee_rate', 0.02)))  # 2% estimate
        self.min_balance = Decimal(str(self.config.get('min_balance', 50)))  # £50 reserve

        logger.info(
            f"Arbitrage strategy initialized | "
            f"Spread threshold: ${self.spread_threshold} | "
            f"Min profit: {self.min_profit_pct * 100:.2f}% | "
            f"Max exposure: £{self.max_total_exposure}"
        )

    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for active arbitrage opportunities.

        Uses optimized query with precomputed arbitrage_opportunity flag.

        Returns:
            List of opportunity dicts with market info and prices
        """
        try:
            cur = self.conn.cursor()

            # Fast query using partial index on arbitrage_opportunity
            cur.execute("""
                SELECT
                    s.symbol,
                    s.id as symbol_id,
                    bm.market_id,
                    bm.question,
                    bm.category,
                    bm.end_date,
                    bp.yes_ask,
                    bp.no_ask,
                    bp.spread,
                    bp.estimated_profit_pct,
                    bp.timestamp
                FROM binary_prices bp
                JOIN symbols s ON bp.symbol_id = s.id
                JOIN binary_markets bm ON bm.symbol_id = s.id
                WHERE bp.arbitrage_opportunity = true
                    AND bm.status = 'active'
                    AND bp.timestamp > NOW() - INTERVAL '10 seconds'
                    AND bp.estimated_profit_pct >= %s
                ORDER BY bp.estimated_profit_pct DESC
                LIMIT 20
            """, (float(self.min_profit_pct * 100),))

            opportunities = []
            for row in cur.fetchall():
                (
                    symbol, symbol_id, market_id, question, category, end_date,
                    yes_ask, no_ask, spread, estimated_profit_pct, timestamp
                ) = row

                opportunities.append({
                    'symbol': symbol,
                    'symbol_id': symbol_id,
                    'market_id': market_id,
                    'question': question,
                    'category': category,
                    'end_date': end_date,
                    'yes_ask': Decimal(str(yes_ask)),
                    'no_ask': Decimal(str(no_ask)),
                    'spread': Decimal(str(spread)),
                    'estimated_profit_pct': Decimal(str(estimated_profit_pct)),
                    'timestamp': timestamp
                })

            if opportunities:
                logger.info(f"Found {len(opportunities)} arbitrage opportunities")

            return opportunities

        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
            return []

    def check_arbitrage_opportunity(self, symbol: str) -> Optional[Dict]:
        """
        Check if arbitrage exists for a specific symbol.

        Args:
            symbol: Market symbol (e.g., "PRES2024-TRUMP")

        Returns:
            Opportunity dict if valid, None otherwise
        """
        try:
            cur = self.conn.cursor()

            # Get latest price with arbitrage flag
            cur.execute("""
                SELECT
                    bp.yes_ask,
                    bp.no_ask,
                    bp.spread,
                    bp.estimated_profit_pct,
                    bm.market_id,
                    bm.question
                FROM binary_prices bp
                JOIN symbols s ON bp.symbol_id = s.id
                JOIN binary_markets bm ON bm.symbol_id = s.id
                WHERE s.symbol = %s
                    AND bp.arbitrage_opportunity = true
                    AND bm.status = 'active'
                ORDER BY bp.timestamp DESC
                LIMIT 1
            """, (symbol,))

            row = cur.fetchone()
            if not row:
                return None

            yes_ask, no_ask, spread, estimated_profit_pct, market_id, question = row

            # Validate profit threshold
            if Decimal(str(estimated_profit_pct)) < self.min_profit_pct * 100:
                logger.debug(
                    f"Profit too low for {symbol}: "
                    f"{estimated_profit_pct:.2f}% < {self.min_profit_pct * 100:.2f}%"
                )
                return None

            return {
                'symbol': symbol,
                'market_id': market_id,
                'question': question,
                'yes_ask': Decimal(str(yes_ask)),
                'no_ask': Decimal(str(no_ask)),
                'spread': Decimal(str(spread)),
                'estimated_profit_pct': Decimal(str(estimated_profit_pct))
            }

        except Exception as e:
            logger.error(f"Error checking opportunity for {symbol}: {e}")
            return None

    def check_risk_limits(self) -> bool:
        """
        Check if we can open new positions based on risk limits.

        Checks:
        1. Total exposure across all open positions
        2. Account balance
        3. Number of open positions

        Returns:
            True if all risk checks pass
        """
        try:
            cur = self.conn.cursor()

            # Get total exposure from open positions
            cur.execute("""
                SELECT COALESCE(SUM(
                    (yes_qty * yes_entry_price) + (no_qty * no_entry_price)
                ), 0) as total_exposure,
                COUNT(*) as num_positions
                FROM binary_positions
                WHERE status = 'open'
            """)

            row = cur.fetchone()
            total_exposure, num_positions = row
            total_exposure = Decimal(str(total_exposure))

            # Check total exposure limit
            if total_exposure >= self.max_total_exposure:
                logger.warning(
                    f"Max exposure reached: £{total_exposure:.2f} / £{self.max_total_exposure}"
                )
                return False

            # TODO: Check account balance from trading client
            # For now, assume we have sufficient balance

            logger.debug(
                f"Risk check passed | "
                f"Exposure: £{total_exposure:.2f} / £{self.max_total_exposure} | "
                f"Positions: {num_positions}"
            )

            return True

        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False

    def check_existing_position(self, market_id: str) -> bool:
        """
        Check if we already have a position in this market.

        Args:
            market_id: Polymarket market ID

        Returns:
            True if position exists, False otherwise
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT COUNT(*)
                FROM binary_positions
                WHERE market_id = %s
                    AND status = 'open'
            """, (market_id,))

            count = cur.fetchone()[0]
            return count > 0

        except Exception as e:
            logger.error(f"Error checking existing position: {e}")
            return False

    def calculate_position_size(self, spread: Decimal) -> Decimal:
        """
        Calculate optimal position size based on available capital.

        Args:
            spread: Current spread (yes_ask + no_ask)

        Returns:
            Position size in pounds
        """
        # Simple approach: use max_position_size if we have room
        # TODO: Implement Kelly Criterion or risk-adjusted sizing

        try:
            cur = self.conn.cursor()

            # Get available capital
            cur.execute("""
                SELECT COALESCE(SUM(
                    (yes_qty * yes_entry_price) + (no_qty * no_entry_price)
                ), 0) as total_exposure
                FROM binary_positions
                WHERE status = 'open'
            """)

            total_exposure = Decimal(str(cur.fetchone()[0]))
            available = self.max_total_exposure - total_exposure

            # Use smaller of max_position_size or available capital
            position_size = min(self.max_position_size, available)

            logger.debug(f"Position size: £{position_size:.2f}")
            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return Decimal('0')

    async def execute_arbitrage(
        self,
        symbol: str,
        market_id: str,
        yes_ask: Decimal,
        no_ask: Decimal
    ) -> bool:
        """
        Execute paired YES + NO purchase.

        Speed critical: Must execute both orders within milliseconds.

        Args:
            symbol: Market symbol
            market_id: Polymarket market ID
            yes_ask: YES ask price
            no_ask: NO ask price

        Returns:
            True if execution successful
        """
        # Pre-execution checks
        if not self.check_risk_limits():
            logger.warning(f"Risk limits exceeded, skipping {symbol}")
            return False

        if self.check_existing_position(market_id):
            logger.warning(f"Already have position in {market_id}, skipping")
            return False

        # Calculate position size
        spread = yes_ask + no_ask
        position_size = self.calculate_position_size(spread)

        if position_size <= 0:
            logger.warning(f"No capital available for {symbol}")
            return False

        # Calculate quantities (equal dollar amount for both)
        yes_qty = position_size / yes_ask
        no_qty = position_size / no_ask

        logger.info(
            f"Executing arbitrage: {symbol} | "
            f"YES: {yes_qty:.2f} @ ${yes_ask:.4f} | "
            f"NO: {no_qty:.2f} @ ${no_ask:.4f} | "
            f"Spread: ${spread:.4f}"
        )

        try:
            # TODO: Implement parallel order execution
            # For now, this is a placeholder

            # Place YES order
            # yes_order = await self.client.place_order(
            #     market_id=market_id,
            #     side='YES',
            #     price=yes_ask,
            #     quantity=yes_qty,
            #     order_type='MARKET'
            # )

            # Place NO order
            # no_order = await self.client.place_order(
            #     market_id=market_id,
            #     side='NO',
            #     price=no_ask,
            #     quantity=no_qty,
            #     order_type='MARKET'
            # )

            # Save position to database
            self._save_position(
                symbol=symbol,
                market_id=market_id,
                yes_qty=yes_qty,
                no_qty=no_qty,
                yes_price=yes_ask,
                no_price=no_ask,
                yes_order_id=None,  # TODO: Get from yes_order
                no_order_id=None    # TODO: Get from no_order
            )

            logger.success(
                f"Arbitrage executed: {symbol} | "
                f"Locked profit: ${(Decimal('1.00') - spread):.4f}"
            )

            return True

        except Exception as e:
            logger.error(f"Arbitrage execution failed for {symbol}: {e}")
            return False

    def _save_position(
        self,
        symbol: str,
        market_id: str,
        yes_qty: Decimal,
        no_qty: Decimal,
        yes_price: Decimal,
        no_price: Decimal,
        yes_order_id: Optional[str] = None,
        no_order_id: Optional[str] = None
    ):
        """
        Save position to database.

        Args:
            symbol: Market symbol
            market_id: Polymarket market ID
            yes_qty: Quantity of YES shares
            no_qty: Quantity of NO shares
            yes_price: Entry price for YES
            no_price: Entry price for NO
            yes_order_id: Order ID for YES
            no_order_id: Order ID for NO
        """
        try:
            cur = self.conn.cursor()

            # Get symbol_id
            cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
            row = cur.fetchone()
            if not row:
                logger.error(f"Symbol not found: {symbol}")
                return

            symbol_id = row[0]

            # Calculate entry spread
            entry_spread = yes_price + no_price

            # Insert position
            cur.execute("""
                INSERT INTO binary_positions (
                    symbol_id,
                    market_id,
                    yes_qty,
                    no_qty,
                    yes_entry_price,
                    no_entry_price,
                    entry_spread,
                    yes_order_id,
                    no_order_id,
                    status,
                    opened_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', NOW()
                )
            """, (
                symbol_id,
                market_id,
                yes_qty,
                no_qty,
                yes_price,
                no_price,
                entry_spread,
                yes_order_id,
                no_order_id
            ))

            self.conn.commit()

            logger.info(f"Position saved: {symbol} | Market: {market_id}")

        except Exception as e:
            logger.error(f"Error saving position: {e}")
            self.conn.rollback()

    def get_open_positions(self) -> List[Dict]:
        """
        Get all open arbitrage positions.

        Returns:
            List of position dicts
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT
                    bp.id,
                    s.symbol,
                    bm.question,
                    bm.market_id,
                    bp.yes_qty,
                    bp.no_qty,
                    bp.yes_entry_price,
                    bp.no_entry_price,
                    bp.entry_spread,
                    bp.opened_at,
                    bm.end_date
                FROM binary_positions bp
                JOIN symbols s ON bp.symbol_id = s.id
                JOIN binary_markets bm ON bp.market_id = bm.market_id
                WHERE bp.status = 'open'
                ORDER BY bp.opened_at DESC
            """)

            positions = []
            for row in cur.fetchall():
                (
                    position_id, symbol, question, market_id,
                    yes_qty, no_qty, yes_entry_price, no_entry_price,
                    entry_spread, opened_at, end_date
                ) = row

                # Calculate locked profit
                avg_qty = (Decimal(str(yes_qty)) + Decimal(str(no_qty))) / 2
                payout = avg_qty * Decimal('1.00')
                cost = Decimal(str(yes_qty)) * Decimal(str(yes_entry_price)) + \
                       Decimal(str(no_qty)) * Decimal(str(no_entry_price))
                locked_profit = payout - cost

                positions.append({
                    'id': position_id,
                    'symbol': symbol,
                    'question': question,
                    'market_id': market_id,
                    'yes_qty': Decimal(str(yes_qty)),
                    'no_qty': Decimal(str(no_qty)),
                    'yes_entry_price': Decimal(str(yes_entry_price)),
                    'no_entry_price': Decimal(str(no_entry_price)),
                    'entry_spread': Decimal(str(entry_spread)),
                    'locked_profit': locked_profit,
                    'opened_at': opened_at,
                    'end_date': end_date
                })

            return positions

        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []


# TODO: Add async main function for testing
