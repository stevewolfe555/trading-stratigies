"""
Technical indicators for trading analysis.
"""

# Import from parent indicators.py for backwards compatibility
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Optional

def sma(values: List[float], period: int) -> Optional[float]:
    """Simple Moving Average"""
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / float(period)
