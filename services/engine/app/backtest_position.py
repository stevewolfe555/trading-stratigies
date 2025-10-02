"""
Backtest Position Management Module

Handles position tracking, portfolio constraints, and risk management.
Separated for better organization and reusability.
"""

from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class Position:
    """Represents a single trading position."""

    def __init__(self, symbol: str, symbol_id: int, entry_time: datetime,
                 entry_price: float, quantity: int, stop_loss: float,
                 take_profit: float, direction: str, entry_reason: str,
                 market_state: str = 'UNKNOWN', aggression_score: int = 0):
        """Initialize position."""
        self.symbol = symbol
        self.symbol_id = symbol_id
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.direction = direction
        self.entry_reason = entry_reason
        self.market_state = market_state
        self.aggression_score = aggression_score

        # Tracking
        self.bars_in_trade = 0
        self.mae = 0  # Maximum Adverse Excursion
        self.mfe = 0  # Maximum Favorable Excursion

    def update_metrics(self, current_price: float):
        """Update position metrics."""
        self.bars_in_trade += 1

        unrealized_pnl = (current_price - self.entry_price) * self.quantity

        if unrealized_pnl < self.mae:
            self.mae = unrealized_pnl
        if unrealized_pnl > self.mfe:
            self.mfe = unrealized_pnl

    def should_exit(self, current_price: float) -> tuple[bool, str]:
        """Check if position should be exited."""
        if self.direction == 'buy':
            if current_price <= self.stop_loss:
                return True, 'Stop Loss'
            if current_price >= self.take_profit:
                return True, 'Take Profit'
        else:  # sell
            if current_price >= self.stop_loss:
                return True, 'Stop Loss'
            if current_price <= self.take_profit:
                return True, 'Take Profit'

        return False, ''

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Get unrealized P&L."""
        return (current_price - self.entry_price) * self.quantity

    def get_unrealized_pnl_pct(self, current_price: float) -> float:
        """Get unrealized P&L percentage."""
        return ((current_price - self.entry_price) / self.entry_price) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'symbol': self.symbol,
            'symbol_id': self.symbol_id,
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'direction': self.direction,
            'entry_reason': self.entry_reason,
            'market_state': self.market_state,
            'aggression_score': self.aggression_score,
            'bars_in_trade': self.bars_in_trade,
            'mae': self.mae,
            'mfe': self.mfe
        }


class BacktestPortfolio:
    """Manages portfolio of positions with constraints."""

    def __init__(self, initial_capital: float, max_positions: int = 3):
        """Initialize portfolio."""
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_positions = max_positions
        self.positions: Dict[str, Position] = {}
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []

        # Tracking
        self.signals_generated: Dict[str, int] = {}
        self.signals_blocked: Dict[str, int] = {}

    def get_available_position_slots(self) -> int:
        """Get available position slots."""
        return max(0, self.max_positions - len(self.positions))

    def get_available_cash(self) -> float:
        """Get available cash for new positions."""
        return self.cash

    def can_enter_position(self, cost: float) -> bool:
        """Check if we can enter a new position."""
        return (self.get_available_position_slots() > 0 and
                cost <= self.get_available_cash())

    def enter_position(self, position: Position, cost: float) -> bool:
        """Enter a new position."""
        if not self.can_enter_position(cost):
            return False

        if position.symbol in self.positions:
            logger.warning(f"Position already exists for {position.symbol}")
            return False

        self.positions[position.symbol] = position
        self.cash -= cost

        # Track signal
        self.signals_generated[position.symbol] = self.signals_generated.get(position.symbol, 0) + 1

        logger.debug(f"Entered {position.symbol}: {position.quantity} @ ${position.entry_price:.2f}")
        return True

    def exit_position(self, symbol: str, exit_price: float, exit_time: datetime, reason: str) -> Optional[Dict]:
        """Exit an existing position."""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Calculate P&L
        pnl = (exit_price - position.entry_price) * position.quantity
        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100

        # Create trade record
        trade = {
            'symbol_id': position.symbol_id,
            'entry_time': position.entry_time,
            'entry_price': position.entry_price,
            'entry_reason': position.entry_reason,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'exit_reason': reason,
            'direction': position.direction,
            'quantity': position.quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'market_state': position.market_state,
            'aggressive_flow_score': position.aggression_score,
            'bars_in_trade': position.bars_in_trade,
            'duration_minutes': int((exit_time - position.entry_time).total_seconds() / 60),
            'mae': position.mae,
            'mfe': position.mfe
        }

        # Update cash
        self.cash += (exit_price * position.quantity)

        # Remove position
        del self.positions[symbol]
        self.trades.append(trade)

        logger.debug(f"Exited {symbol}: P&L ${pnl:+.2f} ({pnl_pct:+.2f}%) - {reason}")
        return trade

    def update_positions(self, bars_at_time: Dict[str, Dict]):
        """Update all positions with current prices."""
        for symbol, bar in bars_at_time.items():
            if symbol in self.positions:
                self.positions[symbol].update_metrics(bar['close'])

    def check_stops_and_targets(self, bars_at_time: Dict[str, Dict]) -> List[Dict]:
        """Check stops and targets for all positions."""
        exited_trades = []

        for symbol, bar in bars_at_time.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                should_exit, reason = position.should_exit(bar['close'])

                if should_exit:
                    trade = self.exit_position(symbol, bar['close'], bar['time'], reason)
                    if trade:
                        exited_trades.append(trade)

        return exited_trades

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Get total portfolio value."""
        positions_value = sum(
            pos.quantity * current_prices.get(pos.symbol, pos.entry_price)
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    def record_equity_point(self, timestamp: datetime, current_prices: Dict[str, float]):
        """Record equity curve point."""
        positions_value = sum(
            pos.quantity * current_prices.get(pos.symbol, pos.entry_price)
            for pos in self.positions.values()
        )

        equity = self.cash + positions_value

        self.equity_curve.append({
            'time': timestamp,
            'equity': equity,
            'cash': self.cash,
            'positions_value': positions_value,
            'open_positions': len(self.positions)
        })

    def get_summary_stats(self) -> Dict:
        """Get portfolio summary statistics."""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0
            }

        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]

        total_pnl = sum(t['pnl'] for t in self.trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        
        # Calculate Sharpe Ratio
        sharpe_ratio = 0
        if len(self.trades) > 1:
            returns = [t['pnl_pct'] for t in self.trades]
            avg_return = sum(returns) / len(returns)
            
            # Calculate standard deviation
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            
            # Sharpe Ratio (assuming 0% risk-free rate, annualized)
            if std_dev > 0:
                sharpe_ratio = (avg_return / std_dev) * (252 ** 0.5)  # Annualized (252 trading days)

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.trades) * 100 if self.trades else 0,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'avg_win': sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'avg_loss': sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            'largest_win': max((t['pnl'] for t in winning_trades), default=0),
            'largest_loss': min((t['pnl'] for t in losing_trades), default=0),
            'sharpe_ratio': sharpe_ratio
        }
