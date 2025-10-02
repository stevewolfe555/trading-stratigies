"""
LVN (Low Volume Node) Alert System

Monitors price approaching LVNs and generates alerts.
LVNs are key entry points in the Auction Market playbook.
"""

from __future__ import annotations
import psycopg2
from typing import Dict, List, Optional
from loguru import logger


class LVNAlertSystem:
    """
    Detects when price is approaching Low Volume Nodes.
    
    LVNs are gaps in the volume profile where price tends to move quickly.
    They represent potential entry points for pullback trades.
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        self.alert_threshold_pct = 0.5  # Alert when within 0.5% of LVN
    
    def check_lvn_proximity(self, symbol_id: int) -> Optional[Dict]:
        """
        Check if current price is approaching any LVN.
        
        Returns:
            Alert dict if price is near LVN, None otherwise
        """
        try:
            # Get current price
            current_price = self._get_latest_price(symbol_id)
            if not current_price:
                return None
            
            # Get recent LVNs
            lvns = self._get_recent_lvns(symbol_id)
            if not lvns:
                return None
            
            # Check proximity to each LVN
            closest_lvn = None
            min_distance = float('inf')
            
            for lvn in lvns:
                distance_pct = abs(current_price - lvn) / lvn * 100
                
                if distance_pct < min_distance:
                    min_distance = distance_pct
                    closest_lvn = lvn
            
            # Generate alert if within threshold
            if min_distance <= self.alert_threshold_pct:
                direction = 'UP' if current_price < closest_lvn else 'DOWN'
                
                return {
                    'alert': True,
                    'lvn_price': closest_lvn,
                    'current_price': current_price,
                    'distance_pct': round(min_distance, 2),
                    'distance_dollars': round(abs(current_price - closest_lvn), 2),
                    'direction': direction,
                    'message': f"Price approaching LVN at ${closest_lvn:.2f} ({min_distance:.2f}% away)"
                }
            
            # Return closest LVN info even if not alerting
            return {
                'alert': False,
                'lvn_price': closest_lvn,
                'current_price': current_price,
                'distance_pct': round(min_distance, 2),
                'distance_dollars': round(abs(current_price - closest_lvn), 2),
                'direction': 'UP' if current_price < closest_lvn else 'DOWN',
                'message': f"Nearest LVN at ${closest_lvn:.2f} ({min_distance:.2f}% away)"
            }
            
        except Exception as e:
            logger.error(f"Error checking LVN proximity: {e}")
            return None
    
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
    
    def _get_recent_lvns(self, symbol_id: int, limit: int = 10) -> List[float]:
        """
        Get recent LVNs from profile metrics.
        
        Args:
            symbol_id: Symbol to get LVNs for
            limit: Number of recent buckets to check
            
        Returns:
            List of LVN prices
        """
        cur = self.conn.cursor()
        
        # Get recent profile metrics with LVNs
        cur.execute("""
            SELECT lvns
            FROM profile_metrics 
            WHERE symbol_id = %s 
                AND lvns IS NOT NULL
                AND lvns::text != '[]'
            ORDER BY bucket DESC 
            LIMIT %s
        """, (symbol_id, limit))
        
        rows = cur.fetchall()
        
        # Collect all LVNs from recent buckets
        all_lvns = []
        for row in rows:
            if row[0]:
                import json
                lvns = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if isinstance(lvns, list):
                    all_lvns.extend([float(lvn) for lvn in lvns if lvn])
        
        # Remove duplicates and sort
        unique_lvns = sorted(list(set(all_lvns)))
        
        return unique_lvns
    
    def get_all_lvns_with_distances(self, symbol_id: int) -> List[Dict]:
        """
        Get all LVNs with their distances from current price.
        Useful for displaying on dashboard.
        
        Returns:
            List of dicts with lvn_price, distance_pct, direction
        """
        try:
            current_price = self._get_latest_price(symbol_id)
            if not current_price:
                return []
            
            lvns = self._get_recent_lvns(symbol_id)
            if not lvns:
                return []
            
            result = []
            for lvn in lvns:
                distance_pct = abs(current_price - lvn) / lvn * 100
                direction = 'ABOVE' if current_price > lvn else 'BELOW'
                
                result.append({
                    'lvn_price': round(lvn, 2),
                    'distance_pct': round(distance_pct, 2),
                    'distance_dollars': round(abs(current_price - lvn), 2),
                    'direction': direction,
                    'is_near': distance_pct <= self.alert_threshold_pct
                })
            
            # Sort by distance (closest first)
            result.sort(key=lambda x: x['distance_pct'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting LVNs with distances: {e}")
            return []


def run_lvn_alerts(db_conn):
    """
    Main function to run LVN alert checks for all symbols.
    Called periodically by the engine service.
    """
    alert_system = LVNAlertSystem(db_conn)
    
    # Get all active symbols
    cur = db_conn.cursor()
    cur.execute("SELECT id, symbol FROM symbols")
    symbols = cur.fetchall()
    
    for symbol_id, symbol_name in symbols:
        try:
            # Check for LVN proximity
            alert = alert_system.check_lvn_proximity(symbol_id)
            
            if alert and alert['alert']:
                logger.info(
                    f"🔔 LVN ALERT - {symbol_name}: {alert['message']} "
                    f"(${alert['distance_dollars']:.2f} away, moving {alert['direction']})"
                )
                
                # Could publish to Redis for real-time notifications
                # r.publish('lvn_alerts', json.dumps(alert))
            
        except Exception as e:
            logger.error(f"Error processing LVN alerts for {symbol_name}: {e}")
            continue
