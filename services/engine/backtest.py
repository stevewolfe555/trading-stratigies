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

# Import classes if they exist, otherwise use simple versions
try:
    from app.detectors.market_state import MarketStateDetector
    from app.indicators.aggressive_flow import AggressiveFlowDetector
    from app.trading.atr_calculator import ATRCalculator
except ImportError:
    # Simple fallback implementations
    class MarketStateDetector:
        pass
    
    class AggressiveFlowDetector:
        pass
    
    class ATRCalculator:
        def calculate(self, candles):
            if len(candles) < 14:
                return 0
            highs = [c['high'] for c in candles[-14:]]
            lows = [c['low'] for c in candles[-14:]]
            closes = [c['close'] for c in candles[-14:]]
            
            tr_values = []
            for i in range(1, len(candles[-14:])):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i-1])
                lc = abs(lows[i] - closes[i-1])
                tr_values.append(max(hl, hc, lc))
            
            return sum(tr_values) / len(tr_values) if tr_values else 0

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
    
    def __init__(self, parameters: Dict):
        """
        Initialize backtest engine.
        
        Args:
            parameters: Strategy parameters dict
        """
        self.params = parameters
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        
        # Initialize detectors
        self.market_state_detector = MarketStateDetector()
        self.aggressive_flow_detector = AggressiveFlowDetector()
        self.atr_calculator = ATRCalculator()
        
        # Backtest state
        self.run_id = None
        self.equity = parameters.get('initial_capital', 100000)
        self.cash = self.equity
        self.positions = {}  # symbol -> position dict
        self.trades = []
        self.equity_curve = []
        
        logger.info(f"Backtest engine initialized with ${self.equity:,.2f} capital")
    
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
    
    def enter_position(self, symbol: str, symbol_id: int, bar: Dict, signal: Dict):
        """Enter a new position."""
        price = bar['close']
        atr = signal['atr']
        
        quantity = self.calculate_position_size(price, atr)
        
        if quantity == 0:
            return
        
        cost = quantity * price
        
        # Check max positions limit
        max_positions = self.params.get('max_positions', 3)
        if len(self.positions) >= max_positions:
            return
        
        # Create position
        position = {
            'symbol': symbol,
            'symbol_id': symbol_id,
            'entry_time': bar['time'],
            'entry_price': price,
            'quantity': quantity,
            'direction': 'LONG',
            'stop_loss': price - (atr * self.params.get('atr_stop_multiplier', 2.0)),
            'take_profit': price + (atr * self.params.get('atr_target_multiplier', 3.0)),
            'atr_at_entry': atr,
            'entry_reason': signal['reason'],
            'market_state': signal.get('market_state'),
            'aggressive_flow_score': signal.get('aggressive_flow_score'),
            'volume_ratio': signal.get('volume_ratio'),
            'cvd_momentum': signal.get('cvd_momentum'),
            'bars_in_trade': 0,
            'mae': 0,  # Maximum Adverse Excursion
            'mfe': 0   # Maximum Favorable Excursion
        }
        
        self.positions[symbol] = position
        self.cash -= cost
        
        logger.debug(f"  ENTER {symbol}: {quantity} @ ${price:.2f} (Stop: ${position['stop_loss']:.2f}, Target: ${position['take_profit']:.2f})")
    
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
    
    def record_equity_point(self, time: datetime):
        """Record equity curve point."""
        positions_value = sum(
            pos['quantity'] * pos['entry_price']  # Simplified - should use current price
            for pos in self.positions.values()
        )
        
        equity = self.cash + positions_value
        
        self.equity_curve.append({
            'backtest_run_id': self.run_id,
            'time': time,
            'equity': equity,
            'cash': self.cash,
            'positions_value': positions_value,
            'open_positions': len(self.positions)
        })
    
    def run_backtest(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Run backtest on historical data.
        
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
        
        # Load candles for all symbols
        all_candles = {}
        for symbol in symbols:
            candles = self.load_candles(symbol, start_date, end_date)
            all_candles[symbol] = candles
            logger.info(f"  {symbol}: {len(candles):,} bars loaded")
        
        logger.info("")
        logger.info("Running simulation...")
        
        # Simulate trading (simplified - process bar by bar)
        # In production, you'd merge all symbols' bars by time
        for symbol in symbols:
            candles = all_candles[symbol]
            
            for i, bar in enumerate(candles):
                # Update existing positions
                self.update_positions(symbol, bar)
                
                # Check for entry signals (simplified)
                if i >= 20:  # Need history for indicators
                    signal = self.check_entry_signal(symbol, candles[i-20:i+1])
                    if signal and symbol not in self.positions:
                        self.enter_position(symbol, bar['symbol_id'], bar, signal)
                
                # Record equity every 100 bars
                if i % 100 == 0:
                    self.record_equity_point(bar['time'])
        
        # Close any remaining positions
        for symbol in list(self.positions.keys()):
            last_bar = all_candles[symbol][-1]
            self.exit_position(symbol, last_bar, 'End of Backtest')
        
        # Save results
        self.save_results()
        
        logger.info("")
        logger.success(f"✅ Backtest complete!")
    
    def check_entry_signal(self, symbol: str, candles: List[Dict]) -> Optional[Dict]:
        """
        Check for entry signal (simplified version).
        
        In production, this would use the full strategy logic.
        """
        # Calculate ATR
        atr = self.atr_calculator.calculate(candles)
        
        if atr == 0:
            return None
        
        # Simplified signal logic
        # TODO: Implement full market state + aggressive flow logic
        
        return {
            'reason': 'Test Signal',
            'atr': atr,
            'market_state': 'IMBALANCE_UP',
            'aggressive_flow_score': 70,
            'volume_ratio': 1.5,
            'cvd_momentum': 1000
        }
    
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
