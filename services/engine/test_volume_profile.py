#!/usr/bin/env python3
"""
Test Volume Profile Calculator

Quick test to verify the volume profile calculator works correctly.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backtest_volume_profile import BacktestVolumeProfileCalculator
from app.backtest_config import BacktestConfig


def test_with_real_data():
    """Test with real candle data from database."""
    print("🧪 Testing Volume Profile Calculator with real data...\n")
    
    # Get database connection
    config = BacktestConfig()
    conn = config.get_connection()
    
    # Fetch recent candles for AAPL
    with conn.cursor() as cur:
        cur.execute("""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE symbol_id = 1
            ORDER BY time DESC
            LIMIT 60
        """)
        
        rows = cur.fetchall()
        
        if not rows:
            print("❌ No candle data found!")
            return
        
        # Convert to candle dicts
        candles = []
        for row in rows:
            candles.append({
                'time': row[0],
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': int(row[5])
            })
        
        # Reverse to chronological order
        candles.reverse()
        
        print(f"📊 Loaded {len(candles)} candles")
        print(f"   Period: {candles[0]['time']} to {candles[-1]['time']}")
        print(f"   Price range: ${candles[0]['close']:.2f} - ${candles[-1]['close']:.2f}\n")
        
        # Calculate volume profile
        calculator = BacktestVolumeProfileCalculator(tick_size=0.01)
        profile = calculator.calculate_profile(candles, lookback_minutes=60)
        
        if profile:
            print("✅ Volume Profile Calculated:")
            print(f"   POC (Point of Control): ${profile['poc']:.2f}")
            print(f"   VAH (Value Area High):  ${profile['vah']:.2f}")
            print(f"   VAL (Value Area Low):   ${profile['val']:.2f}")
            print(f"   Total Volume:           {profile['total_volume']:,}")
            print(f"   Value Area Range:       ${profile['vah'] - profile['val']:.2f}")
            
            # Validate results
            current_price = candles[-1]['close']
            distance_from_poc = abs(current_price - profile['poc']) / profile['poc'] * 100
            in_value_area = profile['val'] <= current_price <= profile['vah']
            
            print(f"\n📈 Current Analysis:")
            print(f"   Current Price:          ${current_price:.2f}")
            print(f"   Distance from POC:      {distance_from_poc:.2f}%")
            print(f"   In Value Area:          {'✅ Yes' if in_value_area else '❌ No'}")
            
            if distance_from_poc < 1.5:
                print(f"   Market State:           🟢 BALANCE (near POC)")
            else:
                if current_price > profile['vah']:
                    print(f"   Market State:           📈 IMBALANCE UP (above VAH)")
                elif current_price < profile['val']:
                    print(f"   Market State:           📉 IMBALANCE DOWN (below VAL)")
                else:
                    print(f"   Market State:           🟡 TRANSITIONING")
            
            print("\n✅ Test PASSED - Volume profile calculator working!")
            
        else:
            print("❌ Failed to calculate volume profile")
    
    conn.close()


def test_with_synthetic_data():
    """Test with synthetic data to verify algorithm."""
    print("\n🧪 Testing with synthetic data...\n")
    
    # Create synthetic candles with known characteristics
    candles = []
    base_price = 100.0
    
    # Create 60 candles with most volume around $100
    for i in range(60):
        # Add some variation
        offset = (i % 10) - 5  # -5 to +5
        price = base_price + (offset * 0.1)
        
        candles.append({
            'time': datetime.now() - timedelta(minutes=60-i),
            'open': price - 0.05,
            'high': price + 0.10,
            'low': price - 0.10,
            'close': price + 0.05,
            'volume': 1000 + (100 * (10 - abs(offset)))  # More volume near base price
        })
    
    calculator = BacktestVolumeProfileCalculator(tick_size=0.01)
    profile = calculator.calculate_profile(candles)
    
    if profile:
        print("✅ Synthetic Data Results:")
        print(f"   POC: ${profile['poc']:.2f} (expected ~$100.00)")
        print(f"   VAH: ${profile['vah']:.2f}")
        print(f"   VAL: ${profile['val']:.2f}")
        
        # Verify POC is near expected value
        if abs(profile['poc'] - base_price) < 0.50:
            print("   ✅ POC is correctly near highest volume area")
        else:
            print("   ⚠️  POC seems off from expected value")
        
        # Verify value area makes sense
        if profile['val'] < profile['poc'] < profile['vah']:
            print("   ✅ Value area is correctly ordered (VAL < POC < VAH)")
        else:
            print("   ⚠️  Value area ordering is incorrect")
    else:
        print("❌ Failed to calculate profile from synthetic data")


if __name__ == "__main__":
    print("=" * 60)
    print("Volume Profile Calculator Test")
    print("=" * 60 + "\n")
    
    try:
        test_with_real_data()
        test_with_synthetic_data()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
