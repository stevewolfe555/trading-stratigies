"""
Average True Range (ATR) Calculator

Calculates volatility-based stop loss and take profit levels.
"""

from typing import Tuple, Optional
from loguru import logger


def calculate_atr(db_conn, symbol_id: int, periods: int = 14) -> Optional[float]:
    """
    Calculate Average True Range for a symbol.
    
    ATR measures average price movement over N periods.
    Used for volatility-based position sizing.
    
    Args:
        db_conn: Database connection
        symbol_id: Symbol ID
        periods: Number of periods (default 14)
        
    Returns:
        ATR value in dollars, or None if insufficient data
    """
    try:
        cur = db_conn.cursor()
        
        # Get last N+1 candles (need N+1 for N true ranges)
        cur.execute(
            """
            SELECT high, low, close, 
                   LAG(close) OVER (ORDER BY time) as prev_close
            FROM candles
            WHERE symbol_id = %s
            ORDER BY time DESC
            LIMIT %s
            """,
            (symbol_id, periods + 1)
        )
        
        rows = cur.fetchall()
        
        if len(rows) < periods:
            return None
        
        # Calculate True Range for each period
        true_ranges = []
        for i in range(len(rows) - 1):  # Skip first row (no prev_close)
            high, low, close, prev_close = rows[i]
            
            if prev_close is None:
                continue
            
            # True Range = max of:
            # 1. High - Low
            # 2. abs(High - Previous Close)
            # 3. abs(Low - Previous Close)
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if not true_ranges:
            return None
        
        # ATR = average of true ranges
        atr = sum(true_ranges) / len(true_ranges)
        
        return atr
        
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return None


def get_atr_based_levels(
    db_conn,
    symbol_id: int,
    current_price: float,
    side: str,
    atr_multiplier_stop: float = 1.5,
    atr_multiplier_target: float = 3.0
) -> Tuple[float, float]:
    """
    Calculate stop loss and take profit based on ATR.
    
    Args:
        db_conn: Database connection
        symbol_id: Symbol ID
        current_price: Current price
        side: 'buy' or 'sell'
        atr_multiplier_stop: ATR multiplier for stop loss (default 1.5)
        atr_multiplier_target: ATR multiplier for take profit (default 3.0)
        
    Returns:
        (stop_loss_price, take_profit_price)
    """
    atr = calculate_atr(db_conn, symbol_id)
    
    if atr is None:
        # Fallback to percentage-based if ATR unavailable
        logger.warning(f"ATR unavailable for symbol {symbol_id}, using fallback percentages")
        if side == 'buy':
            stop_loss = current_price * 0.98  # 2% below
            take_profit = current_price * 1.04  # 4% above
        else:  # sell/short
            stop_loss = current_price * 1.02  # 2% above
            take_profit = current_price * 0.96  # 4% below
        return (stop_loss, take_profit)
    
    # Calculate ATR-based levels
    stop_distance = atr * atr_multiplier_stop
    target_distance = atr * atr_multiplier_target
    
    if side == 'buy':
        stop_loss = current_price - stop_distance
        take_profit = current_price + target_distance
    else:  # sell/short
        stop_loss = current_price + stop_distance
        take_profit = current_price - target_distance
    
    # Log the ATR-based calculation
    atr_pct = (atr / current_price) * 100
    stop_pct = (stop_distance / current_price) * 100
    target_pct = (target_distance / current_price) * 100
    
    logger.info(
        f"ATR-based levels: ATR=${atr:.2f} ({atr_pct:.1f}%), "
        f"Stop={stop_pct:.1f}%, Target={target_pct:.1f}%"
    )
    
    return (stop_loss, take_profit)
