"""
Auction Market Theory Strategy

ONE SOURCE OF TRUTH for strategy logic.
Used by both live trading and backtesting.

Entry Rules:
- Market state is IMBALANCE (up or down)
- Aggressive flow score > threshold (configurable)
- Direction matches market state

Exit Rules:
- ATR-based stop loss (1.5x ATR)
- ATR-based take profit (3x ATR, 2:1 R:R)
- Or opposite signal

Position Sizing:
- 1% risk per trade (configurable)
- Max positions limit (configurable)
"""

from typing import Optional, Dict, List
from loguru import logger


class AuctionMarketStrategy:
    """
    Auction Market Theory trading strategy.
    
    This class contains the core strategy logic that is shared between:
    - Live trading (services/engine/app/trading/auto_strategy.py)
    - Backtesting (services/engine/backtest.py)
    
    Parameters are configurable per symbol via database or passed in.
    """
    
    def __init__(self, parameters: Optional[Dict] = None):
        """
        Initialize strategy with parameters.
        
        Args:
            parameters: Strategy parameters dict
        """
        self.params = parameters or {}
        
        # Default parameters (can be overridden)
        self.min_aggression_score = self.params.get('min_aggression_score', 70)
        self.atr_stop_multiplier = self.params.get('atr_stop_multiplier', 1.5)
        self.atr_target_multiplier = self.params.get('atr_target_multiplier', 3.0)
        self.risk_per_trade_pct = self.params.get('risk_per_trade_pct', 1.0)
        self.max_positions = self.params.get('max_positions', 3)
    
    def calculate_aggression_score(self, 
                                   buy_pressure: float, 
                                   sell_pressure: float, 
                                   cvd_momentum: int) -> int:
        """
        Calculate aggression score from order flow metrics.
        
        Args:
            buy_pressure: Buy pressure percentage (0-100)
            sell_pressure: Sell pressure percentage (0-100)
            cvd_momentum: CVD momentum (change in cumulative delta)
            
        Returns:
            Aggression score (0-100)
        """
        score = 0
        
        # CVD momentum component (40 points max)
        if abs(cvd_momentum) >= 1000:
            score += 40
        elif abs(cvd_momentum) >= 500:
            score += 20
        
        # Pressure component (40 points max)
        if buy_pressure >= 70 or sell_pressure >= 70:
            score += 40
        elif buy_pressure >= 60 or sell_pressure >= 60:
            score += 20
        
        # Volume ratio component (20 points max)
        if buy_pressure > 0 and sell_pressure > 0:
            ratio = max(buy_pressure / sell_pressure, sell_pressure / buy_pressure)
            if ratio >= 2.0:
                score += 20
            elif ratio >= 1.5:
                score += 10
        
        return min(score, 100)
    
    def determine_flow_direction(self, 
                                 buy_pressure: float, 
                                 sell_pressure: float, 
                                 cvd_momentum: int) -> str:
        """
        Determine flow direction from order flow metrics.
        
        Args:
            buy_pressure: Buy pressure percentage
            sell_pressure: Sell pressure percentage
            cvd_momentum: CVD momentum
            
        Returns:
            'BUY', 'SELL', or 'NEUTRAL'
        """
        # Strong buy signals
        if buy_pressure >= 70 or cvd_momentum > 500:
            return 'BUY'
        
        # Strong sell signals
        if sell_pressure >= 70 or cvd_momentum < -500:
            return 'SELL'
        
        # Neutral
        return 'NEUTRAL'
    
    def evaluate_entry_signal(self,
                              market_state: str,
                              confidence: int,
                              buy_pressure: float,
                              sell_pressure: float,
                              cvd_momentum: int,
                              current_price: float,
                              atr: float,
                              symbol: str = '') -> Optional[Dict]:
        """
        Evaluate if entry conditions are met.
        
        This is the CORE STRATEGY LOGIC used by both live and backtest.
        
        Args:
            market_state: Market state (IMBALANCE_UP, IMBALANCE_DOWN, BALANCE, UNKNOWN)
            confidence: Market state confidence (0-100)
            buy_pressure: Buy pressure percentage (0-100)
            sell_pressure: Sell pressure percentage (0-100)
            cvd_momentum: CVD momentum (change in cumulative delta)
            current_price: Current price
            atr: Average True Range
            symbol: Symbol name (for logging)
            
        Returns:
            Signal dict if entry conditions met, None otherwise
        """
        # Calculate aggression score
        aggression_score = self.calculate_aggression_score(
            buy_pressure, sell_pressure, cvd_momentum
        )
        
        # Determine flow direction
        flow_direction = self.determine_flow_direction(
            buy_pressure, sell_pressure, cvd_momentum
        )
        
        # Log evaluation (if symbol provided)
        if symbol:
            state_emoji = {
                'IMBALANCE_UP': '📈',
                'IMBALANCE_DOWN': '📉',
                'BALANCE': '➖',
                'UNKNOWN': '❓'
            }.get(market_state, '❓')
            
            flow_emoji = {
                'BUY': '🟢',
                'SELL': '🔴',
                'NEUTRAL': '⚪'
            }.get(flow_direction, '⚪')
            
            if aggression_score >= 70:
                agg_status = f"🔥 {aggression_score}"
            elif aggression_score >= 40:
                agg_status = f"⚡ {aggression_score}"
            else:
                agg_status = f"💤 {aggression_score}"
            
            logger.debug(
                f"{symbol:6s} │ {state_emoji} {market_state:14s} │ {agg_status:8s} │ "
                f"{flow_emoji} {flow_direction:7s} │ CVD: {cvd_momentum:+6d}"
            )
        
        # ENTRY CONDITIONS
        
        # 1. Market must be in IMBALANCE
        if market_state not in ['IMBALANCE_UP', 'IMBALANCE_DOWN']:
            return None
        
        # 2. Aggression score must be high enough
        if aggression_score < self.min_aggression_score:
            return None
        
        # 3. Flow direction must match market state
        if market_state == 'IMBALANCE_UP' and flow_direction != 'BUY':
            return None
        
        if market_state == 'IMBALANCE_DOWN' and flow_direction != 'SELL':
            return None
        
        # 4. Must have valid ATR
        if atr <= 0:
            return None
        
        # CONDITIONS MET - Generate signal
        side = 'buy' if market_state == 'IMBALANCE_UP' else 'sell'
        
        # Calculate stop loss and take profit using ATR
        if side == 'buy':
            stop_loss = current_price - (atr * self.atr_stop_multiplier)
            take_profit = current_price + (atr * self.atr_target_multiplier)
        else:
            stop_loss = current_price + (atr * self.atr_stop_multiplier)
            take_profit = current_price - (atr * self.atr_target_multiplier)
        
        return {
            'symbol': symbol,
            'side': side,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr': atr,
            'market_state': market_state,
            'confidence': confidence,
            'aggression_score': aggression_score,
            'flow_direction': flow_direction,
            'buy_pressure': buy_pressure,
            'sell_pressure': sell_pressure,
            'cvd_momentum': cvd_momentum,
            'reason': f"{market_state} + Aggressive {flow_direction} (score: {aggression_score})"
        }
    
    def should_exit_position(self,
                            position_side: str,
                            entry_price: float,
                            current_price: float,
                            stop_loss: float,
                            take_profit: float,
                            market_state: str,
                            flow_direction: str) -> tuple[bool, str]:
        """
        Evaluate if position should be exited.
        
        Args:
            position_side: 'buy' or 'sell'
            entry_price: Entry price
            current_price: Current price
            stop_loss: Stop loss price
            take_profit: Take profit price
            market_state: Current market state
            flow_direction: Current flow direction
            
        Returns:
            (should_exit: bool, reason: str)
        """
        # Check stop loss
        if position_side == 'buy':
            if current_price <= stop_loss:
                return (True, 'Stop Loss')
            if current_price >= take_profit:
                return (True, 'Take Profit')
        else:  # sell
            if current_price >= stop_loss:
                return (True, 'Stop Loss')
            if current_price <= take_profit:
                return (True, 'Take Profit')
        
        # Check for opposite signal
        if position_side == 'buy':
            if market_state == 'IMBALANCE_DOWN' and flow_direction == 'SELL':
                return (True, 'Opposite Signal')
        else:  # sell
            if market_state == 'IMBALANCE_UP' and flow_direction == 'BUY':
                return (True, 'Opposite Signal')
        
        return (False, '')
    
    def calculate_position_size(self,
                               account_equity: float,
                               entry_price: float,
                               stop_loss: float,
                               available_cash: float) -> int:
        """
        Calculate position size based on risk management.
        
        Args:
            account_equity: Total account equity
            entry_price: Entry price
            stop_loss: Stop loss price
            available_cash: Available cash
            
        Returns:
            Position size (number of shares)
        """
        # Calculate risk amount (1% of equity by default)
        risk_amount = account_equity * (self.risk_per_trade_pct / 100)
        
        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss)
        
        if stop_distance == 0:
            return 0
        
        # Calculate quantity based on risk
        quantity = int(risk_amount / stop_distance)
        
        # Check if we have enough cash
        cost = quantity * entry_price
        if cost > available_cash:
            quantity = int(available_cash / entry_price)
        
        return max(0, quantity)
