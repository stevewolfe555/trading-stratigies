"""
Position Manager

Manages trading positions, risk limits, and position sizing.
"""

from __future__ import annotations
import psycopg2
from typing import Dict, Optional
from loguru import logger
from .alpaca_client import AlpacaTradingClient


class PositionManager:
    """
    Manages trading positions with risk controls.
    
    Features:
    - Position sizing based on account balance
    - Max position limits
    - Daily loss limits
    - Position tracking in database
    """
    
    def __init__(self, db_conn, alpaca_client: AlpacaTradingClient):
        self.conn = db_conn
        self.client = alpaca_client
        
        # Risk parameters (configurable via environment variables)
        import os
        self.max_positions = int(os.getenv("MAX_POSITIONS", "1"))
        self.risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT", "1.0"))
        self.max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
        self.min_account_balance = float(os.getenv("MIN_ACCOUNT_BALANCE", "1000"))
    
    def can_open_position(self, symbol: str) -> tuple[bool, str]:
        """
        Check if we can open a new position.
        
        Returns:
            (can_trade, reason)
        """
        # Check account balance
        account = self.client.get_account()
        if not account:
            return False, "Cannot get account info"
        
        portfolio_value = float(account.get('portfolio_value', 0))
        if portfolio_value < self.min_account_balance:
            return False, f"Account balance too low: ${portfolio_value:.2f}"
        
        # Check if account is blocked
        if account.get('account_blocked', False):
            return False, "Account is blocked"
        
        if account.get('trading_blocked', False):
            return False, "Trading is blocked"
        
        # Check max positions
        positions = self.client.get_positions()
        if len(positions) >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"
        
        # Check if already have position in this symbol
        existing_position = self.client.get_position(symbol)
        if existing_position:
            return False, f"Already have position in {symbol}"
        
        # Check daily loss limit
        equity = float(account.get('equity', portfolio_value))
        last_equity = float(account.get('last_equity', equity))
        daily_pnl_pct = ((equity - last_equity) / last_equity * 100) if last_equity > 0 else 0
        
        if daily_pnl_pct < -self.max_daily_loss_pct:
            return False, f"Daily loss limit reached: {daily_pnl_pct:.2f}%"
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float
    ) -> int:
        """
        Calculate position size based on risk per trade.
        
        Args:
            symbol: Stock symbol
            entry_price: Entry price
            stop_loss_price: Stop loss price
            
        Returns:
            Number of shares to buy
        """
        try:
            # Get account info
            portfolio_value = self.client.get_portfolio_value()
            if portfolio_value == 0:
                return 0
            
            # Calculate risk amount (1% of portfolio)
            risk_amount = portfolio_value * (self.risk_per_trade_pct / 100)
            
            # Calculate risk per share
            risk_per_share = abs(entry_price - stop_loss_price)
            if risk_per_share == 0:
                risk_per_share = entry_price * 0.02  # Default 2% stop
            
            # Calculate shares
            shares = int(risk_amount / risk_per_share)
            
            # Make sure we can afford it
            buying_power = self.client.get_buying_power()
            max_shares_by_buying_power = int(buying_power / entry_price)
            
            shares = min(shares, max_shares_by_buying_power)
            
            # Minimum 1 share
            shares = max(1, shares)
            
            logger.info(
                f"Position size for {symbol}: {shares} shares "
                f"(Risk: ${risk_amount:.2f}, Entry: ${entry_price:.2f}, SL: ${stop_loss_price:.2f})"
            )
            
            return shares
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def log_trade(
        self,
        symbol: str,
        action: str,
        qty: int,
        price: float,
        order_id: str = None,
        reason: str = None
    ):
        """Log trade to database."""
        try:
            cur = self.conn.cursor()
            
            # Get symbol_id
            cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
            row = cur.fetchone()
            if not row:
                # Create symbol if doesn't exist
                cur.execute("INSERT INTO symbols (symbol) VALUES (%s) RETURNING id", (symbol,))
                symbol_id = cur.fetchone()[0]
            else:
                symbol_id = row[0]
            
            # Log to signals table (reusing for trades)
            cur.execute("""
                INSERT INTO signals (time, strategy_id, symbol_id, type, details)
                VALUES (NOW(), 1, %s, %s, %s)
            """, (
                symbol_id,
                action,
                f'{{"qty": {qty}, "price": {price}, "order_id": "{order_id}", "reason": "{reason}"}}'
            ))
            
            self.conn.commit()
            logger.info(f"Trade logged: {action} {qty} {symbol} @ ${price:.2f}")
            
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            self.conn.rollback()
    
    def get_account_summary(self) -> Dict:
        """Get account summary for display."""
        try:
            account = self.client.get_account()
            if not account:
                return {}
            
            positions = self.client.get_positions()
            
            return {
                'portfolio_value': float(account.get('portfolio_value', 0)),
                'buying_power': float(account.get('buying_power', 0)),
                'cash': float(account.get('cash', 0)),
                'equity': float(account.get('equity', 0)),
                'num_positions': len(positions),
                'positions': [
                    {
                        'symbol': p['symbol'],
                        'qty': int(p['qty']),
                        'avg_entry_price': float(p['avg_entry_price']),
                        'current_price': float(p['current_price']),
                        'unrealized_pl': float(p['unrealized_pl']),
                        'unrealized_plpc': float(p['unrealized_plpc']) * 100
                    }
                    for p in positions
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {}
