"""
Backtest Order Flow Calculator

Calculates order flow metrics (buy/sell pressure, CVD) from candle data for backtesting.
Estimates order flow from candle patterns since we don't have tick-by-tick data.

This allows backtests to work on any historical period without requiring
pre-calculated order_flow table data.
"""

from typing import List, Dict
from loguru import logger


class BacktestOrderFlowCalculator:
    """
    Calculates order flow metrics from candle data.
    
    Since we don't have tick-by-tick order flow data for historical periods,
    we estimate buy/sell pressure from candle patterns:
    - Green candles (close > open) = more buying
    - Red candles (close < open) = more selling
    - Wick analysis for pressure estimation
    """
    
    def calculate_flow(self, 
                      candles: List[Dict],
                      lookback_buckets: int = 5) -> Dict:
        """
        Calculate order flow metrics from recent candles.
        
        Args:
            candles: List of candle dicts with keys: open, high, low, close, volume
            lookback_buckets: Number of recent candles to analyze (default 5)
            
        Returns:
            {
                'cumulative_delta': int,        # Net buy - sell volume
                'buy_pressure': float (0-100),  # % buying pressure
                'sell_pressure': float (0-100), # % selling pressure
                'cvd_momentum': int             # Change in CVD over period
            }
        """
        if not candles or len(candles) < 2:
            return self._default_flow()
        
        try:
            # Use last N candles
            recent_candles = candles[-lookback_buckets:] if len(candles) > lookback_buckets else candles
            
            # Calculate buy/sell volume for each candle
            buy_volume = 0
            sell_volume = 0
            cvd_history = []
            running_cvd = 0
            
            for candle in recent_candles:
                candle_buy, candle_sell = self._estimate_candle_flow(candle)
                buy_volume += candle_buy
                sell_volume += candle_sell
                
                # Track CVD over time
                running_cvd += (candle_buy - candle_sell)
                cvd_history.append(running_cvd)
            
            # Calculate cumulative delta
            cumulative_delta = buy_volume - sell_volume
            
            # Calculate buy/sell pressure percentages
            total_volume = buy_volume + sell_volume
            if total_volume > 0:
                buy_pressure = (buy_volume / total_volume) * 100
                sell_pressure = (sell_volume / total_volume) * 100
            else:
                buy_pressure = 50.0
                sell_pressure = 50.0
            
            # Calculate CVD momentum (change from start to end)
            cvd_momentum = 0
            if len(cvd_history) >= 2:
                cvd_momentum = cvd_history[-1] - cvd_history[0]
            
            return {
                'cumulative_delta': int(cumulative_delta),
                'buy_pressure': round(buy_pressure, 2),
                'sell_pressure': round(sell_pressure, 2),
                'cvd_momentum': int(cvd_momentum)
            }
            
        except Exception as e:
            logger.error(f"Error calculating order flow: {e}")
            return self._default_flow()
    
    def _estimate_candle_flow(self, candle: Dict) -> tuple[int, int]:
        """
        Estimate buy and sell volume from a single candle.
        
        Uses candle pattern analysis:
        - Close position in range indicates pressure
        - Green candles = more buying
        - Red candles = more selling
        - Wick size indicates rejected prices
        
        Args:
            candle: Dict with open, high, low, close, volume
            
        Returns:
            (buy_volume, sell_volume) tuple
        """
        open_price = float(candle['open'])
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        volume = int(candle['volume'])
        
        # Calculate candle metrics
        body_size = abs(close - open_price)
        total_range = high - low
        
        # Avoid division by zero
        if total_range == 0:
            # No range, split volume 50/50
            return (volume // 2, volume // 2)
        
        # Calculate where close is in the range (0 = low, 1 = high)
        close_position = (close - low) / total_range
        
        # Calculate buy/sell ratio based on close position
        # Close near high = more buying
        # Close near low = more selling
        buy_ratio = close_position
        sell_ratio = 1.0 - close_position
        
        # Adjust for candle color (green vs red)
        if close > open_price:
            # Green candle - increase buy ratio
            buy_ratio = min(1.0, buy_ratio * 1.2)
            sell_ratio = 1.0 - buy_ratio
        elif close < open_price:
            # Red candle - increase sell ratio
            sell_ratio = min(1.0, sell_ratio * 1.2)
            buy_ratio = 1.0 - sell_ratio
        
        # Distribute volume
        buy_volume = int(volume * buy_ratio)
        sell_volume = int(volume * sell_ratio)
        
        return (buy_volume, sell_volume)
    
    def _default_flow(self) -> Dict:
        """Return default flow when calculation fails."""
        return {
            'cumulative_delta': 0,
            'buy_pressure': 50.0,
            'sell_pressure': 50.0,
            'cvd_momentum': 0
        }
