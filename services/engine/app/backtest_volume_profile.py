"""
Backtest Volume Profile Calculator

Calculates volume profile metrics (POC, VAH, VAL) from candle data for backtesting.
This allows backtests to work on any historical period without requiring pre-calculated data.

Based on Auction Market Theory:
- POC (Point of Control): Price level with highest volume
- VAH (Value Area High): Top of 70% volume area
- VAL (Value Area Low): Bottom of 70% volume area
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger


class BacktestVolumeProfileCalculator:
    """
    Calculates volume profile from candle data.
    
    This replicates the volume profile calculation that would normally
    come from the profile_metrics table, but does it on-the-fly from
    raw candle data.
    """
    
    def __init__(self, tick_size: float = 0.01):
        """
        Initialize calculator.
        
        Args:
            tick_size: Price increment for bucketing (default 0.01 = 1 cent)
        """
        self.tick_size = tick_size
    
    def calculate_profile(self, 
                         candles: List[Dict],
                         lookback_minutes: int = 60) -> Optional[Dict]:
        """
        Calculate volume profile from recent candles.
        
        Args:
            candles: List of candle dicts with keys: time, open, high, low, close, volume
            lookback_minutes: How many minutes of data to use (default 60)
            
        Returns:
            {
                'poc': float,           # Point of Control (highest volume price)
                'vah': float,           # Value Area High (top of 70% volume)
                'val': float,           # Value Area Low (bottom of 70% volume)
                'total_volume': int     # Total volume in period
            }
            or None if insufficient data
        """
        if not candles or len(candles) < 10:
            return None
        
        try:
            # Filter to lookback period
            if len(candles) > lookback_minutes:
                candles = candles[-lookback_minutes:]
            
            # Create price levels (buckets)
            price_levels = self._create_price_levels(candles)
            
            if not price_levels:
                return None
            
            # Find POC (highest volume level)
            poc_level = max(price_levels.items(), key=lambda x: x[1])
            poc = poc_level[0]
            
            # Calculate total volume
            total_volume = sum(price_levels.values())
            
            if total_volume == 0:
                return None
            
            # Calculate value area (70% of volume around POC)
            vah, val = self._calculate_value_area(price_levels, poc, total_volume)
            
            return {
                'poc': float(poc),
                'vah': float(vah),
                'val': float(val),
                'total_volume': int(total_volume)
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return None
    
    def _create_price_levels(self, candles: List[Dict]) -> Dict[float, int]:
        """
        Create price level buckets with volume distribution.
        
        For each candle, distribute volume across the price range (high to low)
        using the tick size to create buckets.
        
        Args:
            candles: List of candle dicts
            
        Returns:
            Dict mapping price level to volume at that level
        """
        price_levels = {}
        
        for candle in candles:
            high = float(candle['high'])
            low = float(candle['low'])
            volume = int(candle['volume'])
            close = float(candle['close'])
            open_price = float(candle['open'])
            
            # Calculate price range
            price_range = high - low
            
            if price_range == 0:
                # No range, put all volume at close price
                price_level = self._round_to_tick(close)
                price_levels[price_level] = price_levels.get(price_level, 0) + volume
                continue
            
            # Distribute volume across price levels
            # Weight towards close price (where most trading happened)
            current_price = low
            levels_in_range = []
            
            while current_price <= high:
                price_level = self._round_to_tick(current_price)
                levels_in_range.append(price_level)
                current_price += self.tick_size
            
            if not levels_in_range:
                continue
            
            # Simple distribution: more volume near close
            # Calculate distance from close for each level
            for price_level in levels_in_range:
                # Weight by inverse distance from close
                distance = abs(price_level - close)
                weight = 1.0 / (1.0 + distance)
                
                # Distribute volume proportionally
                level_volume = int(volume * weight / len(levels_in_range))
                price_levels[price_level] = price_levels.get(price_level, 0) + level_volume
        
        return price_levels
    
    def _calculate_value_area(self, 
                              price_levels: Dict[float, int],
                              poc: float,
                              total_volume: int) -> tuple[float, float]:
        """
        Calculate Value Area High (VAH) and Value Area Low (VAL).
        
        Value area contains 70% of the total volume, centered around POC.
        
        Args:
            price_levels: Dict of price -> volume
            poc: Point of Control price
            total_volume: Total volume across all levels
            
        Returns:
            (vah, val) tuple
        """
        target_volume = total_volume * 0.70
        
        # Sort price levels
        sorted_levels = sorted(price_levels.keys())
        
        # Find POC index
        poc_idx = sorted_levels.index(poc) if poc in sorted_levels else len(sorted_levels) // 2
        
        # Expand from POC until we have 70% of volume
        accumulated_volume = price_levels[poc]
        lower_idx = poc_idx
        upper_idx = poc_idx
        
        while accumulated_volume < target_volume:
            # Check if we can expand
            can_expand_up = upper_idx < len(sorted_levels) - 1
            can_expand_down = lower_idx > 0
            
            if not can_expand_up and not can_expand_down:
                break
            
            # Decide which direction to expand (choose side with more volume)
            expand_up = False
            
            if can_expand_up and can_expand_down:
                vol_above = price_levels.get(sorted_levels[upper_idx + 1], 0)
                vol_below = price_levels.get(sorted_levels[lower_idx - 1], 0)
                expand_up = vol_above >= vol_below
            elif can_expand_up:
                expand_up = True
            
            # Expand
            if expand_up:
                upper_idx += 1
                accumulated_volume += price_levels.get(sorted_levels[upper_idx], 0)
            else:
                lower_idx -= 1
                accumulated_volume += price_levels.get(sorted_levels[lower_idx], 0)
        
        vah = sorted_levels[upper_idx]
        val = sorted_levels[lower_idx]
        
        return vah, val
    
    def _round_to_tick(self, price: float) -> float:
        """
        Round price to nearest tick size.
        
        Args:
            price: Raw price
            
        Returns:
            Price rounded to tick size
        """
        return round(price / self.tick_size) * self.tick_size
