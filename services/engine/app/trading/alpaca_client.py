"""
Alpaca Trading Client

Handles order execution, position management, and account info
for Alpaca paper trading account.
"""

from __future__ import annotations
import os
import requests
from typing import Dict, Optional, List
from loguru import logger


class AlpacaTradingClient:
    """
    Client for Alpaca Trading API (Paper Trading).
    
    Supports:
    - Market/Limit orders
    - Position management
    - Account information
    - Order status tracking
    """
    
    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        
        # Use paper trading URL
        if paper:
            self.base_url = "https://paper-api.alpaca.markets"
        else:
            self.base_url = "https://api.alpaca.markets"
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }
    
    def get_account(self) -> Optional[Dict]:
        """Get account information."""
        try:
            response = requests.get(
                f"{self.base_url}/v2/account",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            response = requests.get(
                f"{self.base_url}/v2/positions",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get positions: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for specific symbol."""
        try:
            response = requests.get(
                f"{self.base_url}/v2/positions/{symbol}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None  # No position
            else:
                logger.error(f"Failed to get position for {symbol}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    def place_market_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        time_in_force: str = "day"
    ) -> Optional[Dict]:
        """
        Place a market order.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Number of shares
            side: 'buy' or 'sell'
            time_in_force: 'day', 'gtc', 'ioc', 'fok'
            
        Returns:
            Order dict if successful, None otherwise
        """
        try:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "market",
                "time_in_force": time_in_force
            }
            
            response = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=order_data
            )
            
            if response.status_code in [200, 201]:
                order = response.json()
                logger.info(f"✅ Market order placed: {side.upper()} {qty} {symbol} - Order ID: {order['id']}")
                return order
            else:
                logger.error(f"Failed to place order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None
    
    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        limit_price: float,
        time_in_force: str = "day"
    ) -> Optional[Dict]:
        """
        Place a limit order.
        
        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            limit_price: Limit price
            time_in_force: 'day', 'gtc', 'ioc', 'fok'
            
        Returns:
            Order dict if successful, None otherwise
        """
        try:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "limit",
                "limit_price": str(limit_price),
                "time_in_force": time_in_force
            }
            
            response = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=order_data
            )
            
            if response.status_code in [200, 201]:
                order = response.json()
                logger.info(f"✅ Limit order placed: {side.upper()} {qty} {symbol} @ ${limit_price} - Order ID: {order['id']}")
                return order
            else:
                logger.error(f"Failed to place limit order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None
    
    def place_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        take_profit_price: float,
        stop_loss_price: float
    ) -> Optional[Dict]:
        """
        Place a bracket order (entry + take-profit + stop-loss).
        
        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            take_profit_price: Take profit limit price
            stop_loss_price: Stop loss price
            
        Returns:
            Order dict if successful, None otherwise
        """
        try:
            # Round prices to 2 decimals for stocks >= $1.00 (Alpaca requirement)
            # Stocks under $1 can use 4 decimals, but we'll use 2 for simplicity
            take_profit_rounded = round(take_profit_price, 2)
            stop_loss_rounded = round(stop_loss_price, 2)
            
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "market",
                "time_in_force": "day",
                "order_class": "bracket",
                "take_profit": {
                    "limit_price": str(take_profit_rounded)
                },
                "stop_loss": {
                    "stop_price": str(stop_loss_rounded)
                }
            }
            
            response = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=order_data
            )
            
            if response.status_code in [200, 201]:
                order = response.json()
                logger.info(
                    f"✅ Bracket order placed: {side.upper()} {qty} {symbol} "
                    f"(TP: ${take_profit_price}, SL: ${stop_loss_price}) - Order ID: {order['id']}"
                )
                return order
            else:
                logger.error(f"Failed to place bracket order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            response = requests.delete(
                f"{self.base_url}/v2/orders/{order_id}",
                headers=self.headers
            )
            
            if response.status_code == 204:
                logger.info(f"✅ Order cancelled: {order_id}")
                return True
            else:
                logger.error(f"Failed to cancel order {order_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def close_position(self, symbol: str) -> bool:
        """Close a position (market order)."""
        try:
            response = requests.delete(
                f"{self.base_url}/v2/positions/{symbol}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Position closed: {symbol}")
                return True
            else:
                logger.error(f"Failed to close position {symbol}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")
            return False
    
    def get_orders(self, status: str = "open") -> List[Dict]:
        """
        Get orders.
        
        Args:
            status: 'open', 'closed', 'all'
            
        Returns:
            List of order dicts
        """
        try:
            response = requests.get(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                params={"status": status}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get orders: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def get_buying_power(self) -> float:
        """Get available buying power."""
        account = self.get_account()
        if account:
            return float(account.get('buying_power', 0))
        return 0.0
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        account = self.get_account()
        if account:
            return float(account.get('portfolio_value', 0))
        return 0.0
