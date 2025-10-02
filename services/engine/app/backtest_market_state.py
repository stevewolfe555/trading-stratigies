"""
Backtest Market State Calculator

Calculates market state (BALANCE/IMBALANCE) from candle data for backtesting.
Uses configurable thresholds from Expert Mode to determine state.

This replicates the logic from detectors/market_state.py but works on-the-fly
from candle data instead of requiring pre-calculated database records.
"""

from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger


class BacktestMarketStateCalculator:
    """
    Calculates market state using configurable thresholds.
    
    Mirrors the logic in detectors/market_state.py but operates on
    candle data directly, allowing backtests to work on any historical period.
    """
    
    def __init__(self, config_params: Optional[Dict] = None):
        """
        Initialize with configurable thresholds.
        
        Args:
            config_params: Dict with optional keys:
                - poc_distance_threshold: % from POC for BALANCE (default 1.5)
                - momentum_threshold: % move for IMBALANCE (default 1.5)
                - cvd_pressure_threshold: CVD % for IMBALANCE (default 15)
                - lookback_period: Minutes to analyze (default 60)
        """
        params = config_params or {}
        
        # Configurable thresholds (from Expert Mode)
        self.poc_distance_threshold = params.get('poc_distance_threshold', 1.5)
        self.momentum_threshold = params.get('momentum_threshold', 1.5)
        self.cvd_pressure_threshold = params.get('cvd_pressure_threshold', 15)
        self.lookback_period = params.get('lookback_period', 60)
        
        logger.debug(f"Market State Calculator initialized with thresholds: "
                    f"POC={self.poc_distance_threshold}%, "
                    f"Momentum={self.momentum_threshold}%, "
                    f"CVD={self.cvd_pressure_threshold}%")
    
    def calculate_state(self,
                       current_price: float,
                       candles: List[Dict],
                       profile: Dict,
                       flow_data: Dict) -> Dict:
        """
        Calculate market state from current data.
        
        Args:
            current_price: Current price
            candles: Recent candles for momentum calculation
            profile: Volume profile dict with poc, vah, val
            flow_data: Order flow dict with buy_pressure, sell_pressure, cvd_momentum
            
        Returns:
            {
                'state': 'BALANCE' | 'IMBALANCE_UP' | 'IMBALANCE_DOWN',
                'confidence': int (0-100),
                'distance_from_poc_pct': float,
                'momentum_score': float,
                'in_value_area': bool,
                'cvd_pressure': float
            }
        """
        try:
            # Extract profile metrics
            poc = profile['poc']
            vah = profile['vah']
            val = profile['val']
            
            # Calculate distance from POC
            distance_from_poc = abs(current_price - poc) / poc * 100
            
            # Check if in value area
            in_value_area = val <= current_price <= vah
            
            # Calculate momentum
            momentum = self._calculate_momentum(candles)
            
            # Get CVD pressure
            cvd_pressure = flow_data.get('buy_pressure', 50) - flow_data.get('sell_pressure', 50)
            
            # Determine state based on rules (mirrors live detector)
            state, confidence = self._determine_state(
                distance_from_poc=distance_from_poc,
                in_value_area=in_value_area,
                current_price=current_price,
                vah=vah,
                val=val,
                momentum=momentum,
                cvd_pressure=cvd_pressure
            )
            
            return {
                'state': state,
                'confidence': confidence,
                'distance_from_poc_pct': round(distance_from_poc, 2),
                'momentum_score': round(momentum, 2),
                'in_value_area': in_value_area,
                'cvd_pressure': round(cvd_pressure, 2),
                'poc': poc,
                'vah': vah,
                'val': val
            }
            
        except Exception as e:
            logger.error(f"Error calculating market state: {e}")
            return self._default_state()
    
    def _calculate_momentum(self, candles: List[Dict]) -> float:
        """
        Calculate directional momentum from candles.
        
        Returns:
            Momentum score (positive = up, negative = down)
            Range: -100 to +100
        """
        if len(candles) < 2:
            return 0.0
        
        # Get price change over lookback period
        first_price = candles[0]['close']
        last_price = candles[-1]['close']
        
        # Calculate percentage change
        price_change_pct = (last_price - first_price) / first_price * 100
        
        # Count consecutive candles in same direction
        consecutive_up = 0
        consecutive_down = 0
        max_consecutive_up = 0
        max_consecutive_down = 0
        
        for i in range(1, len(candles)):
            if candles[i]['close'] > candles[i-1]['close']:
                consecutive_up += 1
                consecutive_down = 0
                max_consecutive_up = max(max_consecutive_up, consecutive_up)
            elif candles[i]['close'] < candles[i-1]['close']:
                consecutive_down += 1
                consecutive_up = 0
                max_consecutive_down = max(max_consecutive_down, consecutive_down)
            else:
                consecutive_up = 0
                consecutive_down = 0
        
        # Calculate momentum score
        # Factors: price change %, consecutive candles
        momentum = price_change_pct * 10  # Scale price change
        
        if max_consecutive_up >= 3:
            momentum += 20
        if max_consecutive_down >= 3:
            momentum -= 20
        
        # Clamp to -100 to +100
        return max(-100, min(100, momentum))
    
    def _determine_state(self,
                        distance_from_poc: float,
                        in_value_area: bool,
                        current_price: float,
                        vah: float,
                        val: float,
                        momentum: float,
                        cvd_pressure: float) -> tuple[str, int]:
        """
        Determine market state based on all factors.
        
        Uses configurable thresholds from __init__.
        Mirrors logic from detectors/market_state.py
        
        Returns:
            (state, confidence) tuple
        """
        confidence = 0
        state = 'BALANCE'  # Default
        
        # Rule 1: Distance from POC (adjusted for realistic price movement)
        if distance_from_poc < self.poc_distance_threshold:
            # Close to POC = likely balance
            state = 'BALANCE'
            confidence += 40
        elif distance_from_poc < self.poc_distance_threshold * 1.67:  # 2.5% if threshold is 1.5%
            # Moderate distance = transitioning
            confidence += 20
        else:
            # Far from POC = likely imbalance
            confidence += 30
        
        # Rule 2: Value Area position
        if in_value_area:
            # Inside value area = balance
            if distance_from_poc < self.poc_distance_threshold * 1.33:  # 2.0% if threshold is 1.5%
                state = 'BALANCE'
                confidence += 30
        else:
            # Outside value area = imbalance
            if current_price > vah:
                state = 'IMBALANCE_UP'
                confidence += 30
            elif current_price < val:
                state = 'IMBALANCE_DOWN'
                confidence += 30
        
        # Rule 3: Momentum (realistic thresholds for 60-min moves)
        if abs(momentum) > self.momentum_threshold:
            # Strong momentum (>1.5% move in 60 min) = imbalance
            if momentum > 0:
                state = 'IMBALANCE_UP'
            else:
                state = 'IMBALANCE_DOWN'
            confidence += 20
        elif abs(momentum) < self.momentum_threshold * 0.33:  # 0.5% if threshold is 1.5%
            # Weak momentum (<0.5% move) = balance
            state = 'BALANCE'
            confidence += 10
        
        # Rule 4: CVD Pressure (adjusted for realistic order flow)
        if abs(cvd_pressure) > self.cvd_pressure_threshold:
            # Strong CVD (>15% imbalance) = directional bias
            if cvd_pressure > 0:
                state = 'IMBALANCE_UP'
            else:
                state = 'IMBALANCE_DOWN'
            confidence += 10
        
        # Clamp confidence to 0-100
        confidence = min(100, max(0, confidence))
        
        return state, confidence
    
    def _default_state(self) -> Dict:
        """Return default state when calculation fails."""
        return {
            'state': 'UNKNOWN',
            'confidence': 0,
            'distance_from_poc_pct': 0,
            'momentum_score': 0,
            'in_value_area': False,
            'cvd_pressure': 0,
            'poc': None,
            'vah': None,
            'val': None
        }
