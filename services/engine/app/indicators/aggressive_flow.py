"""
Aggressive Flow Indicator

Detects aggressive buying/selling based on:
- Volume spikes (> 2x average)
- Strong CVD momentum
- High buy/sell pressure
- Consecutive aggressive trades
"""

from __future__ import annotations
import psycopg2
from typing import Dict, Optional
from loguru import logger


class AggressiveFlowIndicator:
    """
    Detects aggressive order flow - key confirmation for entries.
    
    In Auction Market Theory, aggressive flow at key levels (LVNs, POC)
    confirms that institutions are stepping in.
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        self.volume_spike_threshold = 2.0  # 2x average volume
        self.high_pressure_threshold = 70  # 70% buy or sell pressure
    
    def detect_aggression(self, symbol_id: int, lookback_minutes: int = 5) -> Dict:
        """
        Detect aggressive order flow in recent period.
        
        Returns:
            {
                'score': 0-100,
                'direction': 'BUY' | 'SELL' | 'NEUTRAL',
                'volume_spike': bool,
                'cvd_momentum': float,
                'buy_pressure': float,
                'sell_pressure': float,
                'message': str
            }
        """
        try:
            # Get recent order flow data
            recent_flow = self._get_recent_order_flow(symbol_id, lookback_minutes)
            if not recent_flow:
                return self._default_state()
            
            # Get average volume for comparison
            avg_volume = self._get_average_volume(symbol_id, 60)
            
            # Calculate metrics
            current_flow = recent_flow[-1]
            current_volume = self._get_recent_volume(symbol_id, 1)
            
            # Volume spike detection
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            volume_spike = volume_ratio >= self.volume_spike_threshold
            
            # CVD momentum (change over lookback period)
            if len(recent_flow) >= 2:
                cvd_start = recent_flow[0]['cvd']
                cvd_end = recent_flow[-1]['cvd']
                cvd_momentum = cvd_end - cvd_start
            else:
                cvd_momentum = 0
            
            # Current pressure
            buy_pressure = current_flow['buy_pressure']
            sell_pressure = current_flow['sell_pressure']
            
            # Calculate aggression score
            score = self._calculate_aggression_score(
                volume_ratio=volume_ratio,
                cvd_momentum=cvd_momentum,
                buy_pressure=buy_pressure,
                sell_pressure=sell_pressure
            )
            
            # Determine direction
            if buy_pressure >= self.high_pressure_threshold:
                direction = 'BUY'
            elif sell_pressure >= self.high_pressure_threshold:
                direction = 'SELL'
            elif cvd_momentum > 1000:
                direction = 'BUY'
            elif cvd_momentum < -1000:
                direction = 'SELL'
            else:
                direction = 'NEUTRAL'
            
            # Generate message
            if score >= 70:
                intensity = "STRONG"
            elif score >= 50:
                intensity = "MODERATE"
            else:
                intensity = "WEAK"
            
            message = f"{intensity} {direction} aggression detected"
            if volume_spike:
                message += f" (Volume: {volume_ratio:.1f}x avg)"
            
            return {
                'score': min(100, int(score)),
                'direction': direction,
                'volume_spike': volume_spike,
                'volume_ratio': round(volume_ratio, 2),
                'cvd_momentum': int(cvd_momentum),
                'buy_pressure': round(buy_pressure, 1),
                'sell_pressure': round(sell_pressure, 1),
                'message': message,
                'is_aggressive': score >= 50
            }
            
        except Exception as e:
            logger.error(f"Error detecting aggressive flow: {e}")
            return self._default_state()
    
    def _get_recent_order_flow(self, symbol_id: int, lookback_minutes: int):
        """Get recent order flow data."""
        cur = self.conn.cursor()
        
        cur.execute("""
            SELECT 
                bucket,
                delta,
                cumulative_delta as cvd,
                buy_pressure,
                sell_pressure
            FROM order_flow
            WHERE symbol_id = %s
                AND bucket > NOW() - INTERVAL '%s minutes'
            ORDER BY bucket ASC
        """, (symbol_id, lookback_minutes))
        
        rows = cur.fetchall()
        
        return [{
            'bucket': row[0],
            'delta': int(row[1]) if row[1] else 0,
            'cvd': int(row[2]) if row[2] else 0,
            'buy_pressure': float(row[3]) if row[3] else 50,
            'sell_pressure': float(row[4]) if row[4] else 50,
        } for row in rows]
    
    def _get_average_volume(self, symbol_id: int, lookback_minutes: int) -> float:
        """Calculate average volume over period."""
        cur = self.conn.cursor()
        
        cur.execute("""
            SELECT AVG(volume)
            FROM candles
            WHERE symbol_id = %s
                AND time > NOW() - INTERVAL '%s minutes'
        """, (symbol_id, lookback_minutes))
        
        row = cur.fetchone()
        return float(row[0]) if row and row[0] else 1.0
    
    def _get_recent_volume(self, symbol_id: int, minutes: int) -> float:
        """Get total volume in recent period."""
        cur = self.conn.cursor()
        
        cur.execute("""
            SELECT SUM(volume)
            FROM candles
            WHERE symbol_id = %s
                AND time > NOW() - INTERVAL '%s minutes'
        """, (symbol_id, minutes))
        
        row = cur.fetchone()
        return float(row[0]) if row and row[0] else 0.0
    
    def _calculate_aggression_score(
        self,
        volume_ratio: float,
        cvd_momentum: float,
        buy_pressure: float,
        sell_pressure: float
    ) -> float:
        """
        Calculate aggression score (0-100).
        
        Factors:
        - Volume spike: +30 points
        - Strong CVD momentum: +40 points
        - High pressure (>70%): +30 points
        """
        score = 0.0
        
        # Volume spike
        if volume_ratio >= 3.0:
            score += 30
        elif volume_ratio >= 2.0:
            score += 20
        elif volume_ratio >= 1.5:
            score += 10
        
        # CVD momentum
        abs_momentum = abs(cvd_momentum)
        if abs_momentum >= 2000:
            score += 40
        elif abs_momentum >= 1000:
            score += 30
        elif abs_momentum >= 500:
            score += 20
        elif abs_momentum >= 100:
            score += 10
        
        # Pressure
        max_pressure = max(buy_pressure, sell_pressure)
        if max_pressure >= 80:
            score += 30
        elif max_pressure >= 70:
            score += 20
        elif max_pressure >= 60:
            score += 10
        
        return score
    
    def _default_state(self) -> Dict:
        """Return default state when no data."""
        return {
            'score': 0,
            'direction': 'NEUTRAL',
            'volume_spike': False,
            'volume_ratio': 1.0,
            'cvd_momentum': 0,
            'buy_pressure': 50.0,
            'sell_pressure': 50.0,
            'message': 'No aggressive flow detected',
            'is_aggressive': False
        }


def run_aggressive_flow_detection(db_conn):
    """
    Main function to run aggressive flow detection for all symbols.
    Called periodically by the engine service.
    """
    indicator = AggressiveFlowIndicator(db_conn)
    
    # Get all active symbols
    cur = db_conn.cursor()
    cur.execute("SELECT id, symbol FROM symbols")
    symbols = cur.fetchall()
    
    for symbol_id, symbol_name in symbols:
        try:
            # Detect aggressive flow
            flow = indicator.detect_aggression(symbol_id)
            
            if flow['is_aggressive']:
                logger.info(
                    f"🔥 AGGRESSIVE FLOW - {symbol_name}: {flow['message']} "
                    f"(Score: {flow['score']}/100, CVD: {flow['cvd_momentum']:+d})"
                )
            
        except Exception as e:
            logger.error(f"Error processing aggressive flow for {symbol_name}: {e}")
            continue
