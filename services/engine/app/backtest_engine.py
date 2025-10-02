"""
Main execution logic for backtesting trading strategies.
Coordinates data loading, signal evaluation, position management, and analysis.
"""

from typing import Dict, List, Optional
from datetime import datetime
import json
from loguru import logger
from .backtest_config import BacktestConfig
from .backtest_data import BacktestDataLoader
from .backtest_position import BacktestPortfolio, Position
from .backtest_analysis import BacktestAnalyzer
from app.strategies.auction_market_strategy import AuctionMarketStrategy
class BacktestEngine:
    """
    Main backtest engine that coordinates all components.

    This class brings together:
    - Configuration and database management
    - Data loading and processing
    - Portfolio and position management
    - Strategy evaluation
    - Results analysis and reporting
    """

    def __init__(self, parameters: Optional[Dict] = None):
        """Initialize backtest engine."""
        self.config = BacktestConfig(parameters)
        self.data_loader = BacktestDataLoader(self.config.get_connection())
        self.portfolio = BacktestPortfolio(
            initial_capital=self.config.get_parameter('initial_capital', 100000),
            max_positions=self.config.get_parameter('max_positions', 3)
        )
        self.analyzer = BacktestAnalyzer(
            self.config.get_connection(),
            self.portfolio,
            self.config.params
        )

        # Strategy instance (will be initialized per symbol if needed)
        self.strategy = None

        logger.info("Backtest engine initialized")

    def initialize_strategy(self, symbol_parameters: Dict = None):
        """Initialize strategy with parameters."""
        params = symbol_parameters or self.config.get_strategy_parameters()
        self.strategy = AuctionMarketStrategy(params)

    def check_entry_signal(self, symbol: str, symbol_id: int, current_time: datetime) -> Optional[Dict]:
        """Check for entry signal using strategy logic."""
        if not self.strategy:
            self.initialize_strategy()

        try:
            # Get current price
            with self.config.get_connection().cursor() as cur:
                cur.execute("""
                    SELECT close FROM candles
                    WHERE symbol_id = %s AND time <= %s
                    ORDER BY time DESC
                    LIMIT 1
                """, (symbol_id, current_time))

                row = cur.fetchone()
                if not row:
                    return None

                current_price = float(row[0])

                # Get market state
                state_data = self.data_loader.load_market_state(symbol_id, current_time)
                if not state_data:
                    return None

                # Get order flow
                flow_data = self.data_loader.load_order_flow(symbol_id, current_time)
                if not flow_data:
                    return None

                # Extract flow metrics
                current_flow = flow_data[0]
                buy_pressure = float(current_flow['buy_pressure'])
                sell_pressure = float(current_flow['sell_pressure'])

                # CVD momentum
                if len(flow_data) >= 2:
                    cvd_start = int(flow_data[-1]['cumulative_delta'])
                    cvd_end = int(flow_data[0]['cumulative_delta'])
                    cvd_momentum = cvd_end - cvd_start
                else:
                    cvd_momentum = 0

                # Calculate ATR (simplified)
                atr = self._calculate_atr(symbol_id, current_time)
                if atr <= 0:
                    return None

                # Use strategy to evaluate signal
                signal = self.strategy.evaluate_entry_signal(
                    market_state=state_data['state'],
                    confidence=state_data['confidence'],
                    buy_pressure=buy_pressure,
                    sell_pressure=sell_pressure,
                    cvd_momentum=cvd_momentum,
                    current_price=current_price,
                    atr=atr,
                    symbol=symbol
                )

                return signal

        except Exception as e:
            logger.error(f"Error checking entry signal for {symbol}: {e}")
            return None

    def _calculate_atr(self, symbol_id: int, current_time: datetime) -> float:
        """Calculate ATR for position sizing."""
        try:
            with self.config.get_connection().cursor() as cur:
                cur.execute("""
                    SELECT high, low, close
                    FROM candles
                    WHERE symbol_id = %s AND time <= %s
                    ORDER BY time DESC
                    LIMIT 14
                """, (symbol_id, current_time))

                rows = cur.fetchall()
                if len(rows) < 14:
                    return 0

                # Calculate True Range
                tr_values = []
                for i in range(len(rows) - 1):
                    high = float(rows[i][0])
                    low = float(rows[i][1])
                    prev_close = float(rows[i+1][2])

                    hl = high - low
                    hc = abs(high - prev_close)
                    lc = abs(low - prev_close)
                    tr_values.append(max(hl, hc, lc))

                return sum(tr_values) / len(tr_values) if tr_values else 0

        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0

    def run_backtest(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """Run backtest with proper multi-stock simulation."""
        logger.info(f"🚀 Starting backtest: {start_date.date()} to {end_date.date()}")

        # Create run record
        run_id = self._create_run(symbols, start_date, end_date)

        # Load and merge candles
        all_bars_by_time = self.data_loader.load_and_merge_candles(symbols, start_date, end_date)

        logger.info(f"📈 Processing {len(all_bars_by_time):,} timestamps...")

        # Process all symbols simultaneously
        for timestamp, bars_at_time in all_bars_by_time.items():
            # Update existing positions
            self.portfolio.update_positions(bars_at_time)

            # Check stops and targets
            self.portfolio.check_stops_and_targets(bars_at_time)

            # Check for new entry signals
            available_slots = self.portfolio.get_available_position_slots()
            available_cash = self.portfolio.get_available_cash()

            if available_slots > 0 and available_cash > 0:
                for symbol in list(bars_at_time.keys()):
                    if symbol not in self.portfolio.positions:
                        signal = self.check_entry_signal(symbol, bars_at_time[symbol]['symbol_id'], timestamp)
                        if signal:
                            # Calculate position cost
                            position_cost = self._calculate_position_cost(signal, available_cash)
                            if position_cost > 0:
                                # Create position object
                                position = Position(
                                    symbol=symbol,
                                    symbol_id=bars_at_time[symbol]['symbol_id'],
                                    entry_time=timestamp,
                                    entry_price=signal['entry_price'],
                                    quantity=int(position_cost / signal['entry_price']),
                                    stop_loss=signal['stop_loss'],
                                    take_profit=signal['take_profit'],
                                    direction=signal['side'],
                                    entry_reason=signal['reason'],
                                    market_state=signal.get('market_state', 'UNKNOWN'),
                                    aggression_score=signal.get('aggression_score', 0)
                                )

                                # Enter position
                                if self.portfolio.enter_position(position, position_cost):
                                    available_slots -= 1
                                    available_cash -= position_cost
                                    if available_slots <= 0 or available_cash <= 0:
                                        break

            # Record equity periodically
            if len(all_bars_by_time) > 100 and hash(str(timestamp)) % 100 == 0:
                current_prices = {symbol: bar['close'] for symbol, bar in bars_at_time.items()}
                self.portfolio.record_equity_point(timestamp, current_prices)

        # Close remaining positions
        for symbol in list(self.portfolio.positions.keys()):
            symbol_bars = [bars for bars in all_bars_by_time.values() if symbol in bars]
            if symbol_bars:
                last_bar = symbol_bars[-1][symbol]
                self.portfolio.exit_position(symbol, last_bar['close'], last_bar['time'], 'End of Backtest')

        # Save and analyze results
        self.analyzer.save_results(run_id)
        self.analyzer.print_summary()

        # Save constraint analysis
        self._save_constraint_analysis(run_id)

        logger.success("✅ Backtest complete!")

    def _create_run(self, symbols: List[str], start_date: datetime, end_date: datetime) -> int:
        """Create backtest run record."""
        with self.config.get_connection().cursor() as cur:
            cur.execute("""
                INSERT INTO backtest_runs (
                    name, strategy_name, start_date, end_date, symbols, parameters, status, started_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                f"Backtest {start_date.date()} to {end_date.date()}",
                'auction_market',
                start_date,
                end_date,
                symbols,
                json.dumps(self.config.params),
                'completed',
                datetime.now()
            ))

            run_id = cur.fetchone()[0]
            self.config.get_connection().commit()
            return run_id

    def _save_constraint_analysis(self, run_id: int):
        """Save constraint analysis data to database."""
        total_signals = sum(self.portfolio.signals_generated.values())
        total_blocked = sum(self.portfolio.signals_blocked.values())

        blocked_percentage = 0
        if total_signals + total_blocked > 0:
            blocked_percentage = (total_blocked / (total_signals + total_blocked)) * 100

        # Calculate recommendations
        recommendations = {}
        if total_blocked > 0:
            max_positions_needed = len(self.portfolio.positions) + total_blocked
            recommendations['max_positions_needed'] = max_positions_needed
            recommendations['capital_needed'] = self.portfolio.initial_capital * (max_positions_needed / max(1, len(self.portfolio.positions)))

        constraint_data = {
            'signals_generated': total_signals,
            'signals_blocked': total_blocked,
            'blocked_percentage': blocked_percentage,
            'recommendations': recommendations
        }

        with self.config.get_connection().cursor() as cur:
            cur.execute("""
                UPDATE backtest_runs SET
                    signals_generated = %s,
                    signals_blocked = %s,
                    blocked_percentage = %s,
                    constraint_analysis = %s,
                    completed_at = %s
                WHERE id = %s
            """, (
                total_signals,
                total_blocked,
                blocked_percentage,
                json.dumps(constraint_data),
                datetime.now(),
                run_id
            ))

            self.config.get_connection().commit()

    def _calculate_position_cost(self, signal: Dict, available_cash: float) -> float:
        """Calculate cost of entering position."""
        entry_price = signal['entry_price']
        risk_amount = self.portfolio.initial_capital * (self.config.get_parameter('risk_per_trade_pct', 1.0) / 100)
        stop_loss = signal['stop_loss']

        # Calculate quantity based on risk
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance == 0:
            return 0

        quantity = int(risk_amount / stop_distance)
        cost = quantity * entry_price

        # Check if we have enough cash
        if cost > available_cash:
            max_quantity = int(available_cash / entry_price)
            if max_quantity > 0:
                cost = max_quantity * entry_price
            else:
                return 0

        return cost
