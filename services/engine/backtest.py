#!/usr/bin/env python3
"""
Backtesting Engine for Auction Market Strategy

Tests strategy on historical data and stores results in database.

Usage:
    python backtest.py --symbols AAPL,MSFT --start 2024-01-01 --end 2024-12-31
    python backtest.py --all-symbols --years 1
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_batch
import json
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import shared strategy class
from app.strategies.auction_market_strategy import AuctionMarketStrategy

# Configure logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'trading'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}


class BacktestEngine:
    """
    Backtesting engine for Auction Market strategy.
    
    Features:
    - Market state detection (BALANCE/IMBALANCE)
    - Aggressive flow analysis
    - ATR-based stops and targets
    - Position sizing and risk management
    - Detailed trade tracking
    - Performance metrics calculation
    """
    
    def __init__(self, parameters: Optional[Dict] = None):
        """
        Initialize backtest engine.

        Args:
            parameters: Strategy parameters dict
        """
        self.params = parameters or {}
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        
        # Initialize shared strategy
        self.strategy = AuctionMarketStrategy(parameters)

        # Backtest state
        self.run_id = None
        self.equity = parameters.get('initial_capital', 100000)
        self.cash = self.equity
        self.positions = {}  # symbol -> position dict
        self.trades = []
        self.equity_curve = []

        # Performance tracking
        self.signals_generated = {}  # symbol -> count of signals
        self.signals_blocked = {}    # symbol -> count blocked by constraints
        self.constraint_analysis = {}  # Analysis of what limits were hit

        # Test modes
        self.test_mode = parameters.get('test_mode', 'portfolio')  # 'portfolio', 'individual', 'unlimited'
        self.enable_position_limits = parameters.get('enable_position_limits', True)
        self.enable_cash_limits = parameters.get('enable_cash_limits', True)

        logger.info(f"Backtest engine initialized with ${self.equity:,.2f} capital")
        logger.info(f"Test mode: {self.test_mode}")
    
    def create_run(self, name: str, symbols: List[str], start_date: datetime, end_date: datetime) -> int:
        """Create backtest run record."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO backtest_runs (
                    name, strategy_name, start_date, end_date, symbols, parameters, status, started_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                name,
                'Auction Market',
                start_date,
                end_date,
                symbols,
                json.dumps(self.params),
                'running',
                datetime.now()
            ))
            
            self.run_id = cur.fetchone()[0]
            self.conn.commit()
            
            logger.info(f"Created backtest run #{self.run_id}: {name}")
            return self.run_id
    
    def load_candles(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Load historical candles for symbol."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    c.time,
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.volume,
                    s.id as symbol_id
                FROM candles c
                JOIN symbols s ON c.symbol_id = s.id
                WHERE s.symbol = %s
                    AND c.time >= %s
                    AND c.time <= %s
                ORDER BY c.time ASC
            """, (symbol, start_date, end_date))
            
            candles = []
            for row in cur.fetchall():
                candles.append({
                    'time': row[0],
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': int(row[5]),
                    'symbol_id': row[6]
                })
            
            return candles
    
    def calculate_position_size(self, price: float, atr: float) -> int:
        """
        Calculate position size based on risk management.

        Risk per trade = 1% of equity
        Stop loss = 2 * ATR
        """
        risk_per_trade_pct = self.params.get('risk_per_trade_pct', 1.0)
        atr_stop_multiplier = self.params.get('atr_stop_multiplier', 2.0)

        risk_amount = self.equity * (risk_per_trade_pct / 100)
        stop_distance = atr * atr_stop_multiplier

        if stop_distance == 0:
            return 0

        quantity = int(risk_amount / stop_distance)

        # Check if we have enough cash
        cost = quantity * price
        if cost > self.cash:
            quantity = int(self.cash / price)

        return max(0, quantity)
    
    def enter_position(self, symbol: str, symbol_id: int, bar: Dict, signal: Dict, position_cost: float = None):
        """Enter a new position."""
        if symbol in self.positions:
            return

        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']

        # Calculate quantity
        if position_cost is None:
            # Use risk-based sizing
            risk_amount = self.equity * (self.params.get('risk_per_trade_pct', 1.0) / 100)
            stop_distance = abs(entry_price - stop_loss)
            if stop_distance == 0:
                return

            quantity = int(risk_amount / stop_distance)
            cost = quantity * entry_price
        else:
            # Use provided cost
            quantity = int(position_cost / entry_price)
            cost = position_cost

        if quantity == 0 or cost > self.cash:
            return

        # Create position
        position = {
            'symbol_id': symbol_id,
            'entry_time': bar['time'],
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'direction': 'buy' if signal['side'] == 'buy' else 'sell',
            'entry_reason': signal['reason'],
            'atr_at_entry': signal.get('atr', 0),
            'market_state': signal.get('market_state', 'UNKNOWN'),
            'aggressive_flow_score': signal.get('aggression_score', 0),
            'volume_ratio': signal.get('volume_ratio', 0),
            'cvd_momentum': signal.get('cvd_momentum', 0),
            'bars_in_trade': 0,
            'mae': 0,  # Maximum Adverse Excursion
            'mfe': 0   # Maximum favorable Excursion
        }

        self.positions[symbol] = position
        self.cash -= cost

        logger.debug(f"  ENTER {symbol}: {quantity} @ ${entry_price:.2f} (Stop: ${stop_loss:.2f}, Target: ${take_profit:.2f})")
    
    def exit_position(self, symbol: str, bar: Dict, reason: str):
        """Exit an existing position."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        exit_price = bar['close']
        
        # Calculate P&L
        pnl = (exit_price - position['entry_price']) * position['quantity']
        pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
        
        # Create trade record
        trade = {
            'backtest_run_id': self.run_id,
            'symbol_id': position['symbol_id'],
            'entry_time': position['entry_time'],
            'entry_price': position['entry_price'],
            'entry_reason': position['entry_reason'],
            'exit_time': bar['time'],
            'exit_price': exit_price,
            'exit_reason': reason,
            'direction': position['direction'],
            'quantity': position['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'stop_loss': position['stop_loss'],
            'take_profit': position['take_profit'],
            'atr_at_entry': position['atr_at_entry'],
            'market_state': position['market_state'],
            'aggressive_flow_score': position['aggressive_flow_score'],
            'volume_ratio': position['volume_ratio'],
            'cvd_momentum': position['cvd_momentum'],
            'bars_in_trade': position['bars_in_trade'],
            'duration_minutes': int((bar['time'] - position['entry_time']).total_seconds() / 60),
            'mae': position['mae'],
            'mfe': position['mfe']
        }
        
        self.trades.append(trade)
        self.cash += (exit_price * position['quantity'])
        
        logger.debug(f"  EXIT {symbol}: {position['quantity']} @ ${exit_price:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}")
        
        del self.positions[symbol]
    
    def update_positions(self, symbol: str, bar: Dict):
        """Update position metrics and check stops/targets."""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        price = bar['close']
        
        # Update bars in trade
        position['bars_in_trade'] += 1
        
        # Update MAE/MFE
        unrealized_pnl = (price - position['entry_price']) * position['quantity']
        if unrealized_pnl < position['mae']:
            position['mae'] = unrealized_pnl
        if unrealized_pnl > position['mfe']:
            position['mfe'] = unrealized_pnl
        
        # Check stop loss
        if price <= position['stop_loss']:
            self.exit_position(symbol, bar, 'Stop Loss')
            return
        
        # Check take profit
        if price >= position['take_profit']:
            self.exit_position(symbol, bar, 'Take Profit')
            return
    
    def get_available_position_slots(self) -> int:
        """Get available position slots."""
        if not self.enable_position_limits:
            return 999  # Unlimited

        max_positions = self.params.get('max_positions', 3)
        return max(0, max_positions - len(self.positions))

    def get_available_cash(self) -> float:
        """Get available cash for new positions."""
        if not self.enable_cash_limits:
            return 999999999  # Unlimited

        return self.cash

    def calculate_position_cost(self, signal: Dict, available_cash: float) -> float:
        """Calculate cost of entering position, considering constraints."""
        entry_price = signal['entry_price']
        risk_amount = self.equity * (self.params.get('risk_per_trade_pct', 1.0) / 100)
        stop_loss = signal['stop_loss']

        # Calculate quantity based on risk
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance == 0:
            return 0

        quantity = int(risk_amount / stop_distance)
        cost = quantity * entry_price

        # Check if we have enough cash
        if cost > available_cash:
            # Scale down to available cash
            max_quantity = int(available_cash / entry_price)
            if max_quantity > 0:
                cost = max_quantity * entry_price
            else:
                return 0

        return cost

    def load_and_merge_candles(self, symbols: List[str], start_date: datetime, end_date: datetime) -> Dict[datetime, Dict[str, Dict]]:
        """
        Load candles for all symbols and merge by timestamp.

        Returns:
            Dict[datetime, Dict[str, Dict]] - timestamp -> {symbol -> bar_data}
        """
        all_bars_by_time = {}

        for symbol in symbols:
            # Initialize tracking
            self.signals_generated[symbol] = 0
            self.signals_blocked[symbol] = 0

            candles = self.load_candles(symbol, start_date, end_date)

            for bar in candles:
                timestamp = bar['time']
                if timestamp not in all_bars_by_time:
                    all_bars_by_time[timestamp] = {}
                all_bars_by_time[timestamp][symbol] = bar

        return all_bars_by_time

    def run_individual_stock_test(self, symbol: str, start_date: datetime, end_date: datetime):
        """
        Run individual stock test for parameter optimization.

        Args:
            symbol: Single symbol to test
            start_date: Start date
            end_date: End date
        """
        logger.info(f"🔬 Running individual test for {symbol}")

        # Create separate run for this symbol
        name = f"Individual Test - {symbol} ({start_date.date()} to {end_date.date()})"
        self.create_run(name, [symbol], start_date, end_date)

        # Load candles
        candles = self.load_candles(symbol, start_date, end_date)
        logger.info(f"  {symbol}: {len(candles):,} bars loaded")

        # Process each bar
        for i, bar in enumerate(candles):
            if i >= 20:  # Need history for indicators
                self.update_positions(symbol, bar)
                signal = self.check_entry_signal(symbol, bar['symbol_id'], bar['time'])
                if signal:
                    self.signals_generated[symbol] = self.signals_generated.get(symbol, 0) + 1
                    self.enter_position(symbol, bar['symbol_id'], bar, signal)

            # Record equity periodically
            if i % 100 == 0:
                self.record_equity_point(bar['time'])

        # Close position
        if symbol in self.positions:
            self.exit_position(symbol, candles[-1], 'End of Test')

        # Log individual results
        trades_for_symbol = [t for t in self.trades if t['symbol_id'] == bar['symbol_id']]
        if trades_for_symbol:
            winning_trades = [t for t in trades_for_symbol if t['pnl'] > 0]
            total_pnl = sum(t['pnl'] for t in trades_for_symbol)

            logger.info(f"  📊 {symbol} Results:")
            logger.info(f"    Trades: {len(trades_for_symbol)}")
            logger.info(f"    Win Rate: {len(winning_trades)/len(trades_for_symbol)*100:.1f}%")
            logger.info(f"    Total P&L: ${total_pnl:.2f}")
            logger.info(f"    Signals Generated: {self.signals_generated.get(symbol, 0)}")
        else:
            logger.info(f"  📊 {symbol}: No trades")

    def run_unlimited_test(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Run test without position or cash limits to see theoretical maximum.

        Args:
            symbols: List of symbols to test
            start_date: Start date
            end_date: End date
        """
        logger.info("🚀 Running unlimited test (no position/cash limits)")

        # Temporarily disable limits
        original_position_limits = self.enable_position_limits
        original_cash_limits = self.enable_cash_limits
        self.enable_position_limits = False
        self.enable_cash_limits = False

        try:
            # Run normal backtest
            all_bars_by_time = self.load_and_merge_candles(symbols, start_date, end_date)

            for timestamp, bars_at_time in all_bars_by_time.items():
                # Update positions
                for symbol, bar in bars_at_time.items():
                    self.update_positions(symbol, bar)

                # Check signals for all symbols
                for symbol in bars_at_time.keys():
                    if symbol not in self.positions:
                        signal = self.check_entry_signal(symbol, bars_at_time[symbol]['symbol_id'], timestamp)
                        if signal:
                            self.signals_generated[symbol] = self.signals_generated.get(symbol, 0) + 1
                            # Unlimited cash/positions - always enter
                            position_cost = self.calculate_position_cost(signal, 999999999)
                            if position_cost > 0:
                                self.enter_position(symbol, bars_at_time[symbol]['symbol_id'],
                                                  bars_at_time[symbol], signal, position_cost)

            # Close all positions
            for symbol in list(self.positions.keys()):
                symbol_bars = [bars for bars in all_bars_by_time.values() if symbol in bars]
                if symbol_bars:
                    last_bar = symbol_bars[-1][symbol]
                    self.exit_position(symbol, last_bar, 'End of Test')

        finally:
            # Restore limits
            self.enable_position_limits = original_position_limits
            self.enable_cash_limits = original_cash_limits

        # Analyze constraints
        self.analyze_constraints()
    
    def run_backtest(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Run backtest on historical data with proper multi-stock simulation.

        Args:
            symbols: List of symbols to trade
            start_date: Start date
            end_date: End date
        """
        logger.info(f"🚀 Starting backtest: {start_date.date()} to {end_date.date()}")
        logger.info(f"📊 Symbols: {', '.join(symbols)}")
        logger.info(f"💰 Initial capital: ${self.equity:,.2f}")
        logger.info("")

        # Create run
        name = f"Backtest {start_date.date()} to {end_date.date()}"
        self.create_run(name, symbols, start_date, end_date)

        # Load and merge candles by timestamp for proper simultaneous processing
        all_bars_by_time = self.load_and_merge_candles(symbols, start_date, end_date)

        logger.info(f"📈 Total timestamps to process: {len(all_bars_by_time):,}")

        logger.info("")
        logger.info("Running simulation...")

        # Process all symbols simultaneously by timestamp
        for timestamp, bars_at_time in all_bars_by_time.items():
            # Update existing positions for all symbols
            for symbol, bar in bars_at_time.items():
                self.update_positions(symbol, bar)

            # Check for entry signals for all symbols at this timestamp
            available_slots = self.get_available_position_slots()
            available_cash = self.get_available_cash()

            if available_slots > 0 and available_cash > 0:
                # Sort symbols by signal priority (you could add custom logic here)
                symbols_to_check = list(bars_at_time.keys())

                for symbol in symbols_to_check:
                    if symbol not in self.positions:  # Don't check symbols we already have positions in
                        signal = self.check_entry_signal(symbol, bars_at_time[symbol]['symbol_id'], timestamp)
                        if signal:
                            # Check if we can enter this position
                            position_cost = self.calculate_position_cost(signal, available_cash)
                            if position_cost > 0:
                                self.enter_position(symbol, bars_at_time[symbol]['symbol_id'],
                                                  bars_at_time[symbol], signal, position_cost)
                                available_slots -= 1
                                available_cash -= position_cost
                                if available_slots <= 0 or available_cash <= 0:
                                    break  # No more capacity

            # Record equity periodically (simplified for now)
            if len(all_bars_by_time) > 100 and hash(str(timestamp)) % 100 == 0:
                pass  # TODO: Implement equity recording

        # Close any remaining positions
        for symbol in list(self.positions.keys()):
            # Find the last bar for this symbol
            symbol_bars = [bars for bars in all_bars_by_time.values() if symbol in bars]
            if symbol_bars:
                last_bar = symbol_bars[-1][symbol]
                self.exit_position(symbol, last_bar, 'End of Test')

        # Analyze constraints
        self.analyze_constraints()

        # Save results
        self.save_results()
        logger.info("")
        logger.success(f"✅ Backtest complete!")

    def analyze_constraints(self):
        """Analyze what constraints limited performance."""
        logger.info("")
        logger.info("🔍 Constraint Analysis:")

        total_signals = sum(self.signals_generated.values())
        total_blocked = sum(self.signals_blocked.values())

        if total_signals > 0:
            blocked_pct = (total_blocked / (total_signals + total_blocked)) * 100
            logger.info(f"  Signals Generated: {total_signals}")
            logger.info(f"  Signals Blocked: {total_blocked} ({blocked_pct:.1f}%)")

        # Analyze by symbol
        for symbol in self.signals_generated.keys():
            generated = self.signals_generated[symbol]
            blocked = self.signals_blocked.get(symbol, 0)
            if generated > 0 or blocked > 0:
                logger.info(f"  {symbol}: {generated} signals, {blocked} blocked")

        # Recommend limits if needed
        if total_blocked > 0:
            max_positions_needed = len(self.positions) + total_blocked
            logger.info(f"  💡 To capture all signals, you'd need:")
            logger.info(f"     Max Positions: {max_positions_needed} (currently {self.params.get('max_positions', 3)})")
            logger.info(f"     Initial Capital: ${self.equity * (max_positions_needed / max(1, len(self.positions))):,.0f}")

    def run_individual_stock_test(self, symbol: str, start_date: datetime, end_date: datetime):
        """
        Run individual stock test for parameter optimization.

        Args:
            symbol: Single symbol to test
            start_date: Start date
            end_date: End date
        """
        logger.info(f"🔬 Running individual test for {symbol}")

        # Create separate run for this symbol
        name = f"Individual Test - {symbol} ({start_date.date()} to {end_date.date()})"
        self.create_run(name, [symbol], start_date, end_date)

        # Load candles
        candles = self.load_candles(symbol, start_date, end_date)
        logger.info(f"  {symbol}: {len(candles):,} bars loaded")

        # Process each bar
        for i, bar in enumerate(candles):
            if i >= 20:  # Need history for indicators
                self.update_positions(symbol, bar)
                signal = self.check_entry_signal(symbol, bar['symbol_id'], bar['time'])
                if signal:
                    self.signals_generated[symbol] = self.signals_generated.get(symbol, 0) + 1
                    self.enter_position(symbol, bar['symbol_id'], bar, signal)

            # Record equity periodically
            if i % 100 == 0:
                self.record_equity_point(bar['time'])

        # Close position
        if symbol in self.positions:
            self.exit_position(symbol, candles[-1], 'End of Test')

        # Log individual results
        trades_for_symbol = [t for t in self.trades if t['symbol_id'] == bar['symbol_id']]
        if trades_for_symbol:
            winning_trades = [t for t in trades_for_symbol if t['pnl'] > 0]
            total_pnl = sum(t['pnl'] for t in trades_for_symbol)

            logger.info(f"  📊 {symbol} Results:")
            logger.info(f"    Trades: {len(trades_for_symbol)}")
            logger.info(f"    Win Rate: {len(winning_trades)/len(trades_for_symbol)*100:.1f}%")
            logger.info(f"    Total P&L: ${total_pnl:.2f}")
            logger.info(f"    Signals Generated: {self.signals_generated.get(symbol, 0)}")
        else:
            logger.info(f"  📊 {symbol}: No trades")

    def run_unlimited_test(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Run test without position or cash limits to see theoretical maximum.

        Args:
            symbols: List of symbols to test
            start_date: Start date
            end_date: End date
        """
        logger.info("🚀 Running unlimited test (no position/cash limits)")

        # Temporarily disable limits
        original_position_limits = self.enable_position_limits
        original_cash_limits = self.enable_cash_limits
        self.enable_position_limits = False
        self.enable_cash_limits = False

        try:
            # Run normal backtest
            all_bars_by_time = self.load_and_merge_candles(symbols, start_date, end_date)

            for timestamp, bars_at_time in all_bars_by_time.items():
                # Update positions
                for symbol, bar in bars_at_time.items():
                    self.update_positions(symbol, bar)

                # Check signals for all symbols
                for symbol in bars_at_time.keys():
                    if symbol not in self.positions:
                        signal = self.check_entry_signal(symbol, bars_at_time[symbol]['symbol_id'], timestamp)
                        if signal:
                            self.signals_generated[symbol] = self.signals_generated.get(symbol, 0) + 1
                            # Unlimited cash/positions - always enter
                            position_cost = self.calculate_position_cost(signal, 999999999)
                            if position_cost > 0:
                                self.enter_position(symbol, bars_at_time[symbol]['symbol_id'],
                                                  bars_at_time[symbol], signal, position_cost)

            # Close all positions
            for symbol in list(self.positions.keys()):
                symbol_bars = [bars for bars in all_bars_by_time.values() if symbol in bars]
                if symbol_bars:
                    last_bar = symbol_bars[-1][symbol]
                    self.exit_position(symbol, last_bar, 'End of Test')

        finally:
            # Restore limits
            self.enable_position_limits = original_position_limits
            self.enable_cash_limits = original_cash_limits

        # Analyze constraints
        self.analyze_constraints()

    def run_individual_tests(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Run individual tests for each symbol for parameter optimization.

        Args:
            symbols: List of symbols to test individually
            start_date: Start date
            end_date: End date
        """
        logger.info("🔬 Running individual tests for parameter optimization")
        logger.info("")

        for symbol in symbols:
            # Reset state for each symbol
            self.positions = {}
            self.trades = []
            self.equity_curve = []
            self.signals_generated = {symbol: 0}
            self.signals_blocked = {symbol: 0}

            # Run individual test
            self.run_individual_stock_test(symbol, start_date, end_date)

            logger.info("")  # Spacing between symbols
    
    def check_entry_signal(self, symbol: str, symbol_id: int, current_time: datetime) -> Optional[Dict]:
        """
        Check for entry signal using REAL strategy logic and historical data.
        
        Loads market_state, order_flow data from database and uses shared strategy.
        
        Args:
            symbol: Symbol name
            symbol_id: Symbol ID
            current_time: Current bar time
            
        Returns:
            Signal dict if entry conditions met, None otherwise
        """
        try:
            # Get current price
            with self.conn.cursor() as cur:
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
                
                # Get market state at this time
                cur.execute("""
                    SELECT state, confidence 
                    FROM market_state 
                    WHERE symbol_id = %s AND time <= %s
                    ORDER BY time DESC 
                    LIMIT 1
                """, (symbol_id, current_time))
                
                state_row = cur.fetchone()
                if not state_row:
                    return None
                
                market_state = state_row[0]
                confidence = int(state_row[1])
                
                # Get order flow at this time
                cur.execute("""
                    SELECT cumulative_delta, buy_pressure, sell_pressure
                    FROM order_flow 
                    WHERE symbol_id = %s AND bucket <= %s
                    ORDER BY bucket DESC 
                    LIMIT 5
                """, (symbol_id, current_time))
                
                flow_rows = cur.fetchall()
                if not flow_rows:
                    return None
                
                # Extract flow metrics
                current_flow = flow_rows[0]
                buy_pressure = float(current_flow[1])
                sell_pressure = float(current_flow[2])
                
                # CVD momentum
                if len(flow_rows) >= 2:
                    cvd_start = int(flow_rows[-1][0])
                    cvd_end = int(flow_rows[0][0])
                    cvd_momentum = cvd_end - cvd_start
                else:
                    cvd_momentum = 0
                
                # Calculate ATR (simple 14-period)
                cur.execute("""
                    SELECT high, low, close
                    FROM candles 
                    WHERE symbol_id = %s AND time <= %s
                    ORDER BY time DESC 
                    LIMIT 14
                """, (symbol_id, current_time))
                
                atr_rows = cur.fetchall()
                if len(atr_rows) < 14:
                    return None
                
                # Calculate ATR
                tr_values = []
                for i in range(len(atr_rows) - 1):
                    high = float(atr_rows[i][0])
                    low = float(atr_rows[i][1])
                    prev_close = float(atr_rows[i+1][2])
                    
                    hl = high - low
                    hc = abs(high - prev_close)
                    lc = abs(low - prev_close)
                    tr_values.append(max(hl, hc, lc))
                
                atr = sum(tr_values) / len(tr_values) if tr_values else 0
                
                if atr == 0:
                    return None
                
                # Use shared strategy to evaluate entry signal
                signal = self.strategy.evaluate_entry_signal(
                    market_state=market_state,
                    confidence=confidence,
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
    
    def save_results(self):
        """Save backtest results to database."""
        logger.info("Saving results...")
        
        # Save trades
        if self.trades:
            with self.conn.cursor() as cur:
                execute_batch(cur, """
                    INSERT INTO backtest_trades (
                        backtest_run_id, symbol_id, entry_time, entry_price, entry_reason,
                        exit_time, exit_price, exit_reason, direction, quantity,
                        pnl, pnl_pct, stop_loss, take_profit, atr_at_entry,
                        market_state, aggressive_flow_score, volume_ratio, cvd_momentum,
                        bars_in_trade, duration_minutes, mae, mfe
                    ) VALUES (
                        %(backtest_run_id)s, %(symbol_id)s, %(entry_time)s, %(entry_price)s, %(entry_reason)s,
                        %(exit_time)s, %(exit_price)s, %(exit_reason)s, %(direction)s, %(quantity)s,
                        %(pnl)s, %(pnl_pct)s, %(stop_loss)s, %(take_profit)s, %(atr_at_entry)s,
                        %(market_state)s, %(aggressive_flow_score)s, %(volume_ratio)s, %(cvd_momentum)s,
                        %(bars_in_trade)s, %(duration_minutes)s, %(mae)s, %(mfe)s
                    )
                """, self.trades)
        
        # Save equity curve
        if self.equity_curve:
            with self.conn.cursor() as cur:
                execute_batch(cur, """
                    INSERT INTO backtest_equity_curve (
                        backtest_run_id, time, equity, cash, positions_value, open_positions
                    ) VALUES (
                        %(backtest_run_id)s, %(time)s, %(equity)s, %(cash)s, %(positions_value)s, %(open_positions)s
                    )
                """, self.equity_curve)
        
        # Calculate and update run metrics
        self.calculate_metrics()
        
        self.conn.commit()
        logger.success(f"  Saved {len(self.trades)} trades and {len(self.equity_curve)} equity points")
    
    def calculate_metrics(self):
        """Calculate performance metrics and update run."""
        if not self.trades:
            return
        
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['pnl'] > 0)
        losing_trades = sum(1 for t in self.trades if t['pnl'] < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        total_pnl_pct = (total_pnl / self.params['initial_capital']) * 100
        
        wins = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in self.trades if t['pnl'] < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        # Update run
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE backtest_runs SET
                    total_trades = %s,
                    winning_trades = %s,
                    losing_trades = %s,
                    win_rate = %s,
                    total_pnl = %s,
                    total_pnl_pct = %s,
                    avg_win = %s,
                    avg_loss = %s,
                    largest_win = %s,
                    largest_loss = %s,
                    status = 'completed',
                    completed_at = %s
                WHERE id = %s
            """, (
                total_trades, winning_trades, losing_trades, win_rate,
                total_pnl, total_pnl_pct,
                avg_win, avg_loss, largest_win, largest_loss,
                datetime.now(), self.run_id
            ))
        
        logger.info("")
        logger.info("📊 Performance Metrics:")
        logger.info(f"  Total Trades: {total_trades}")
        logger.info(f"  Win Rate: {win_rate:.1f}% ({winning_trades}W / {losing_trades}L)")
        logger.info(f"  Total P&L: ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        logger.info(f"  Avg Win: ${avg_win:,.2f}")
        logger.info(f"  Avg Loss: ${avg_loss:,.2f}")
        logger.info(f"  Largest Win: ${largest_win:,.2f}")
        logger.info(f"  Largest Loss: ${largest_loss:,.2f}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Backtest Auction Market strategy')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols')
    parser.add_argument('--all-symbols', action='store_true', help='Use all available symbols')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--years', type=float, help='Years of history (from today)')
    
    args = parser.parse_args()
    
    # Determine symbols
    if args.all_symbols:
        # Get from database
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SELECT symbol FROM symbols ORDER BY symbol")
            symbols = [row[0] for row in cur.fetchall()]
        conn.close()
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
    else:
        logger.error("Please specify --symbols or --all-symbols")
        sys.exit(1)
    
    # Determine date range
    if args.years:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(args.years * 365))
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        logger.error("Please specify --years or --start and --end")
        sys.exit(1)
    
    # Strategy parameters
    parameters = {
        'initial_capital': 100000,
        'risk_per_trade_pct': 1.0,
        'max_positions': 3,
        'atr_stop_multiplier': 2.0,
        'atr_target_multiplier': 3.0,
        'aggression_threshold': 50
    }
    
    # Run backtest
    engine = BacktestEngine(parameters)
    
    try:
        engine.run_backtest(symbols, start_date, end_date)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        engine.close()


if __name__ == '__main__':
    main()
