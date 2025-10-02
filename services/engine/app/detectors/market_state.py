"""
Market State Detector - Determines if market is in Balance or Imbalance.

Based on Auction Market Theory:
- BALANCE: Price rotating around POC, low volatility, most trading activity
- IMBALANCE_UP: Strong upward momentum, breaking above value area
- IMBALANCE_DOWN: Strong downward momentum, breaking below value area
"""

from __future__ import annotations
import psycopg2
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from loguru import logger


class MarketStateDetector:
    """
    Detects market state using:
    1. Distance from POC (Point of Control)
    2. Position relative to Value Area (VAH/VAL)
    3. Directional momentum
    4. CVD (Cumulative Volume Delta) pressure
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        
    def detect_state(self, symbol_id: int, lookback_minutes: int = 60) -> Dict:
        """
        Detect current market state for a symbol.
        
        Args:
            symbol_id: Database ID of the symbol
            lookback_minutes: How far back to analyze (default 60 min)
            
        Returns:
            {
                'state': 'BALANCE' | 'IMBALANCE_UP' | 'IMBALANCE_DOWN',
                'confidence': 0-100,
                'poc': float,
                'current_price': float,
                'distance_from_poc_pct': float,
                'momentum_score': float,
                'in_value_area': bool
            }
        """
        try:
            # Get current price
            current_price = self._get_latest_price(symbol_id)
            if not current_price:
                return self._default_state()
            
            # Get volume profile metrics (POC, VAH, VAL)
            profile = self._get_latest_profile_metrics(symbol_id)
            if not profile:
                return self._default_state()
            
            poc = profile['poc']
            vah = profile['vah']
            val = profile['val']
            
            # Calculate distance from POC
            distance_from_poc = abs(current_price - poc) / poc * 100
            
            # Check if in value area
            in_value_area = val <= current_price <= vah
            
            # Calculate momentum (directional strength)
            momentum = self._calculate_momentum(symbol_id, lookback_minutes)
            
            # Get CVD pressure
            cvd_pressure = self._get_cvd_pressure(symbol_id)
            
            # Determine state based on rules
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
                'poc': poc,
                'vah': vah,
                'val': val,
                'current_price': current_price,
                'distance_from_poc_pct': round(distance_from_poc, 2),
                'momentum_score': round(momentum, 2),
                'in_value_area': in_value_area,
                'cvd_pressure': cvd_pressure
            }
            
        except Exception as e:
            logger.error(f"Error detecting market state: {e}")
            return self._default_state()
    
    def _get_latest_price(self, symbol_id: int) -> Optional[float]:
        """Get the most recent close price."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT close 
            FROM candles 
            WHERE symbol_id = %s 
            ORDER BY time DESC 
            LIMIT 1
        """, (symbol_id,))
        
        row = cur.fetchone()
        return float(row[0]) if row else None
    
    def _get_latest_profile_metrics(self, symbol_id: int) -> Optional[Dict]:
        """Get the most recent volume profile metrics."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT poc, vah, val, total_volume
            FROM profile_metrics 
            WHERE symbol_id = %s 
            ORDER BY bucket DESC 
            LIMIT 1
        """, (symbol_id,))
        
        row = cur.fetchone()
        if not row:
            return None
            
        return {
            'poc': float(row[0]) if row[0] else None,
            'vah': float(row[1]) if row[1] else None,
            'val': float(row[2]) if row[2] else None,
            'total_volume': int(row[3]) if row[3] else 0
        }
    
    def _calculate_momentum(self, symbol_id: int, lookback_minutes: int) -> float:
        """
        Calculate directional momentum.
        
        Returns:
            Positive = upward momentum
            Negative = downward momentum
            Range: -100 to +100
        """
        cur = self.conn.cursor()
        
        # Get recent candles
        cur.execute("""
            SELECT close, time
            FROM candles 
            WHERE symbol_id = %s 
                AND time > NOW() - INTERVAL '%s minutes'
            ORDER BY time ASC
        """, (symbol_id, lookback_minutes))
        
        rows = cur.fetchall()
        if len(rows) < 2:
            return 0.0
        
        prices = [float(row[0]) for row in rows]
        
        # Calculate momentum metrics
        first_price = prices[0]
        last_price = prices[-1]
        price_change_pct = (last_price - first_price) / first_price * 100
        
        # Count consecutive candles in same direction
        consecutive_up = 0
        consecutive_down = 0
        max_consecutive_up = 0
        max_consecutive_down = 0
        
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                consecutive_up += 1
                consecutive_down = 0
                max_consecutive_up = max(max_consecutive_up, consecutive_up)
            elif prices[i] < prices[i-1]:
                consecutive_down += 1
                consecutive_up = 0
                max_consecutive_down = max(max_consecutive_down, consecutive_down)
        
        # Calculate momentum score
        # Factors: price change %, consecutive candles
        momentum = price_change_pct * 10  # Scale price change
        
        if max_consecutive_up >= 3:
            momentum += 20
        if max_consecutive_down >= 3:
            momentum -= 20
        
        # Clamp to -100 to +100
        return max(-100, min(100, momentum))
    
    def _get_cvd_pressure(self, symbol_id: int) -> float:
        """
        Get recent CVD (Cumulative Volume Delta) pressure.
        
        Returns:
            Positive = buying pressure
            Negative = selling pressure
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT cumulative_delta, buy_pressure, sell_pressure
            FROM order_flow 
            WHERE symbol_id = %s 
            ORDER BY bucket DESC 
            LIMIT 1
        """, (symbol_id,))
        
        row = cur.fetchone()
        if not row:
            return 0.0
        
        cvd = int(row[0]) if row[0] else 0
        buy_pressure = float(row[1]) if row[1] else 50
        sell_pressure = float(row[2]) if row[2] else 50
        
        # Normalize CVD to -100 to +100 range
        # Positive CVD = buying pressure
        pressure = (buy_pressure - sell_pressure)
        
        return pressure
    
    def _determine_state(
        self, 
        distance_from_poc: float,
        in_value_area: bool,
        current_price: float,
        vah: float,
        val: float,
        momentum: float,
        cvd_pressure: float
    ) -> tuple[str, int]:
        """
        Determine market state based on all factors.
        
        Returns:
            (state, confidence)
        """
        confidence = 0
        
        # Rule 1: Distance from POC
        if distance_from_poc < 0.5:
            # Very close to POC = likely balance
            state = 'BALANCE'
            confidence += 40
        elif distance_from_poc < 1.0:
            # Somewhat close = possible balance
            confidence += 20
        else:
            # Far from POC = likely imbalance
            confidence += 30
        
        # Rule 2: Value Area position
        if in_value_area:
            # Inside value area = balance
            if distance_from_poc < 1.0:
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
        
        # Rule 3: Momentum
        if abs(momentum) > 50:
            # Strong momentum = imbalance
            if momentum > 0:
                state = 'IMBALANCE_UP'
            else:
                state = 'IMBALANCE_DOWN'
            confidence += 20
        elif abs(momentum) < 20:
            # Weak momentum = balance
            state = 'BALANCE'
            confidence += 10
        
        # Rule 4: CVD Pressure
        if abs(cvd_pressure) > 30:
            # Strong CVD = imbalance
            if cvd_pressure > 0:
                state = 'IMBALANCE_UP'
            else:
                state = 'IMBALANCE_DOWN'
            confidence += 10
        
        # Default to BALANCE if no clear signal
        if 'state' not in locals():
            state = 'BALANCE'
            confidence = 50
        
        # Clamp confidence to 0-100
        confidence = max(0, min(100, confidence))
        
        return state, confidence
    
    def _default_state(self) -> Dict:
        """Return default state when data is unavailable."""
        return {
            'state': 'UNKNOWN',
            'confidence': 0,
            'poc': None,
            'vah': None,
            'val': None,
            'current_price': None,
            'distance_from_poc_pct': 0,
            'momentum_score': 0,
            'in_value_area': False,
            'cvd_pressure': 0
        }
    
    def save_state(self, symbol_id: int, state_data: Dict) -> None:
        """Save market state to database."""
        try:
            cur = self.conn.cursor()
            
            # Insert into market_state table
            cur.execute("""
                INSERT INTO market_state (
                    time, symbol_id, state, 
                    balance_high, balance_low, poc, confidence
                )
                VALUES (NOW(), %s, %s, %s, %s, %s, %s)
            """, (
                symbol_id,
                state_data['state'],
                state_data.get('vah'),
                state_data.get('val'),
                state_data.get('poc'),
                state_data['confidence']
            ))
            
            self.conn.commit()
            logger.info(f"Saved market state: {state_data['state']} (confidence: {state_data['confidence']}%)")
            
        except Exception as e:
            logger.error(f"Error saving market state: {e}")
            self.conn.rollback()


def run_market_state_detection(db_conn):
    """
    Main function to run market state detection for all symbols.
    Called periodically by the engine service.
    """
    detector = MarketStateDetector(db_conn)
    
    # Get all active symbols
    cur = db_conn.cursor()
    cur.execute("SELECT id, symbol FROM symbols")
    symbols = cur.fetchall()
    
    for symbol_id, symbol_name in symbols:
        try:
            logger.info(f"Detecting market state for {symbol_name}...")
            
            # Detect state
            state_data = detector.detect_state(symbol_id)
            
            # Save to database
            detector.save_state(symbol_id, state_data)
            
            logger.info(
                f"{symbol_name}: {state_data['state']} "
                f"(confidence: {state_data['confidence']}%, "
                f"POC distance: {state_data['distance_from_poc_pct']}%, "
                f"momentum: {state_data['momentum_score']})"
            )
            
        except Exception as e:
            logger.error(f"Error processing {symbol_name}: {e}")
            continue
