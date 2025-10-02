"""
Order Monitor

Monitors pending orders and handles:
- Order fills
- Order timeouts
- Price slippage protection
- Partial fills
- Order reconciliation with broker

Critical for live trading safety!
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from .alpaca_client import AlpacaTradingClient


class OrderMonitor:
    """
    Monitors and manages pending orders.
    
    Responsibilities:
    1. Track pending orders
    2. Cancel stale/timed-out orders
    3. Cancel orders if price moved too far (slippage protection)
    4. Update position tracking when orders fill
    5. Handle partial fills
    6. Reconcile order state with broker
    """
    
    def __init__(self, 
                 alpaca_client: AlpacaTradingClient,
                 max_order_age_minutes: int = 5,
                 max_slippage_pct: float = 1.0):
        """
        Initialize order monitor.
        
        Args:
            alpaca_client: Alpaca trading client
            max_order_age_minutes: Cancel orders older than this (default 5 min)
            max_slippage_pct: Cancel if price moved more than this % (default 1%)
        """
        self.client = alpaca_client
        self.max_order_age_minutes = max_order_age_minutes
        self.max_slippage_pct = max_slippage_pct
        
        # Track orders we've placed
        self.tracked_orders: Dict[str, Dict] = {}
        
        logger.info(f"OrderMonitor initialized: max_age={max_order_age_minutes}min, max_slippage={max_slippage_pct}%")
    
    def track_order(self, order: Dict, entry_price: float) -> None:
        """
        Start tracking an order.
        
        Args:
            order: Order dict from Alpaca
            entry_price: Price when order was placed (for slippage check)
        """
        order_id = order['id']
        self.tracked_orders[order_id] = {
            'order': order,
            'entry_price': entry_price,
            'placed_at': datetime.now(),
            'symbol': order['symbol'],
            'side': order['side'],
            'qty': order['qty'],
            'status': order['status']
        }
        
        logger.info(f"📋 Tracking order: {order['side'].upper()} {order['qty']} {order['symbol']} - ID: {order_id}")
    
    def check_orders(self, current_prices: Dict[str, float]) -> Dict[str, List[Dict]]:
        """
        Check all pending orders and take action if needed.
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            Dict with:
                'filled': List of filled orders
                'cancelled': List of cancelled orders
                'pending': List of still-pending orders
        """
        if not self.tracked_orders:
            return {'filled': [], 'cancelled': [], 'pending': []}
        
        # Get current order status from Alpaca
        open_orders = self.client.get_orders(status='open')
        open_order_ids = {order['id'] for order in open_orders}
        
        filled_orders = []
        cancelled_orders = []
        pending_orders = []
        
        # Check each tracked order
        for order_id, tracked_info in list(self.tracked_orders.items()):
            order = tracked_info['order']
            symbol = tracked_info['symbol']
            placed_at = tracked_info['placed_at']
            entry_price = tracked_info['entry_price']
            
            # Check if order is still open
            if order_id not in open_order_ids:
                # Order is no longer open - either filled or cancelled
                filled_orders.append(tracked_info)
                del self.tracked_orders[order_id]
                logger.info(f"✅ Order filled: {symbol} - ID: {order_id}")
                continue
            
            # Order is still pending - check if we should cancel it
            
            # 1. Check age
            age_minutes = (datetime.now() - placed_at).total_seconds() / 60
            if age_minutes > self.max_order_age_minutes:
                logger.warning(f"⏰ Order timeout: {symbol} (age: {age_minutes:.1f}min) - Cancelling")
                if self.client.cancel_order(order_id):
                    cancelled_orders.append({**tracked_info, 'reason': 'timeout'})
                    del self.tracked_orders[order_id]
                continue
            
            # 2. Check price slippage (for limit orders)
            if symbol in current_prices and order['type'] == 'limit':
                current_price = current_prices[symbol]
                price_change_pct = abs(current_price - entry_price) / entry_price * 100
                
                if price_change_pct > self.max_slippage_pct:
                    logger.warning(
                        f"📉 Price slippage: {symbol} moved {price_change_pct:.2f}% "
                        f"(${entry_price:.2f} -> ${current_price:.2f}) - Cancelling"
                    )
                    if self.client.cancel_order(order_id):
                        cancelled_orders.append({**tracked_info, 'reason': 'slippage'})
                        del self.tracked_orders[order_id]
                    continue
            
            # Order is still valid and pending
            pending_orders.append(tracked_info)
        
        # Log summary
        if filled_orders or cancelled_orders:
            logger.info(
                f"📊 Order check: {len(filled_orders)} filled, "
                f"{len(cancelled_orders)} cancelled, {len(pending_orders)} pending"
            )
        
        return {
            'filled': filled_orders,
            'cancelled': cancelled_orders,
            'pending': pending_orders
        }
    
    def reconcile_orders(self) -> Dict[str, int]:
        """
        Reconcile tracked orders with broker state.
        
        Useful for catching orders that filled/cancelled without us noticing.
        
        Returns:
            Dict with counts: {'synced': N, 'removed': N}
        """
        if not self.tracked_orders:
            return {'synced': 0, 'removed': 0}
        
        # Get all orders from Alpaca
        all_orders = self.client.get_orders(status='all')
        broker_order_ids = {order['id']: order for order in all_orders}
        
        synced = 0
        removed = 0
        
        for order_id, tracked_info in list(self.tracked_orders.items()):
            if order_id in broker_order_ids:
                # Update status from broker
                broker_order = broker_order_ids[order_id]
                old_status = tracked_info['status']
                new_status = broker_order['status']
                
                if old_status != new_status:
                    tracked_info['status'] = new_status
                    synced += 1
                    logger.info(f"🔄 Order status synced: {order_id} - {old_status} -> {new_status}")
                    
                    # If filled or cancelled, remove from tracking
                    if new_status in ['filled', 'cancelled', 'expired', 'rejected']:
                        del self.tracked_orders[order_id]
                        removed += 1
            else:
                # Order not found at broker - remove from tracking
                logger.warning(f"⚠️ Order not found at broker: {order_id} - Removing from tracking")
                del self.tracked_orders[order_id]
                removed += 1
        
        if synced > 0 or removed > 0:
            logger.info(f"🔄 Reconciliation: {synced} synced, {removed} removed")
        
        return {'synced': synced, 'removed': removed}
    
    def cancel_all_pending(self) -> int:
        """
        Cancel all pending orders.
        
        Useful for emergency stops or end-of-day cleanup.
        
        Returns:
            Number of orders cancelled
        """
        if not self.tracked_orders:
            return 0
        
        cancelled_count = 0
        
        for order_id, tracked_info in list(self.tracked_orders.items()):
            symbol = tracked_info['symbol']
            if self.client.cancel_order(order_id):
                logger.info(f"❌ Cancelled pending order: {symbol} - ID: {order_id}")
                cancelled_count += 1
                del self.tracked_orders[order_id]
        
        logger.warning(f"🛑 Cancelled {cancelled_count} pending orders")
        return cancelled_count
    
    def get_pending_orders(self) -> List[Dict]:
        """Get list of all pending orders."""
        return list(self.tracked_orders.values())
    
    def get_pending_count(self) -> int:
        """Get count of pending orders."""
        return len(self.tracked_orders)
    
    def get_pending_symbols(self) -> List[str]:
        """Get list of symbols with pending orders."""
        return list(set(info['symbol'] for info in self.tracked_orders.values()))
    
    def has_pending_order(self, symbol: str) -> bool:
        """Check if symbol has a pending order."""
        return any(info['symbol'] == symbol for info in self.tracked_orders.values())
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get status of a tracked order."""
        if order_id in self.tracked_orders:
            return self.tracked_orders[order_id]['status']
        return None
