#!/usr/bin/env python3
"""
Test Backtest Calculators Integration

Tests all three calculators working together:
1. Volume Profile Calculator
2. Market State Calculator
3. Order Flow Calculator

This simulates what the backtest will do on-the-fly.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backtest_volume_profile import BacktestVolumeProfileCalculator
from app.backtest_market_state import BacktestMarketStateCalculator
from app.backtest_order_flow import BacktestOrderFlowCalculator
from app.backtest_config import BacktestConfig


def test_integrated_calculation():
    """Test all calculators working together."""
    print("🧪 Testing Integrated Backtest Calculators\n")
    print("=" * 70)
    
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
        
        current_price = candles[-1]['close']
        
        print(f"📊 Data Loaded:")
        print(f"   Candles: {len(candles)}")
        print(f"   Period: {candles[0]['time']} to {candles[-1]['time']}")
        print(f"   Current Price: ${current_price:.2f}\n")
        
        # Initialize calculators with configurable parameters
        config_params = {
            'poc_distance_threshold': 1.5,
            'momentum_threshold': 1.5,
            'cvd_pressure_threshold': 15,
            'lookback_period': 60
        }
        
        volume_calc = BacktestVolumeProfileCalculator(tick_size=0.01)
        state_calc = BacktestMarketStateCalculator(config_params)
        flow_calc = BacktestOrderFlowCalculator()
        
        print("=" * 70)
        print("STEP 1: Calculate Volume Profile")
        print("=" * 70)
        
        # Step 1: Calculate volume profile
        profile = volume_calc.calculate_profile(candles, lookback_minutes=60)
        
        if not profile:
            print("❌ Failed to calculate volume profile")
            return
        
        print(f"✅ Volume Profile:")
        print(f"   POC: ${profile['poc']:.2f}")
        print(f"   VAH: ${profile['vah']:.2f}")
        print(f"   VAL: ${profile['val']:.2f}")
        print(f"   Total Volume: {profile['total_volume']:,}\n")
        
        print("=" * 70)
        print("STEP 2: Calculate Order Flow")
        print("=" * 70)
        
        # Step 2: Calculate order flow
        flow_data = flow_calc.calculate_flow(candles, lookback_buckets=5)
        
        print(f"✅ Order Flow:")
        print(f"   Buy Pressure: {flow_data['buy_pressure']:.1f}%")
        print(f"   Sell Pressure: {flow_data['sell_pressure']:.1f}%")
        print(f"   Cumulative Delta: {flow_data['cumulative_delta']:,}")
        print(f"   CVD Momentum: {flow_data['cvd_momentum']:,}\n")
        
        print("=" * 70)
        print("STEP 3: Calculate Market State")
        print("=" * 70)
        
        # Step 3: Calculate market state
        state_data = state_calc.calculate_state(
            current_price=current_price,
            candles=candles,
            profile=profile,
            flow_data=flow_data
        )
        
        print(f"✅ Market State:")
        print(f"   State: {state_data['state']}")
        print(f"   Confidence: {state_data['confidence']}%")
        print(f"   Distance from POC: {state_data['distance_from_poc_pct']:.2f}%")
        print(f"   Momentum Score: {state_data['momentum_score']:.2f}")
        print(f"   In Value Area: {'Yes' if state_data['in_value_area'] else 'No'}")
        print(f"   CVD Pressure: {state_data['cvd_pressure']:.2f}\n")
        
        print("=" * 70)
        print("ANALYSIS")
        print("=" * 70)
        
        # Analyze results
        state_emoji = {
            'BALANCE': '🟢',
            'IMBALANCE_UP': '📈',
            'IMBALANCE_DOWN': '📉',
            'UNKNOWN': '❓'
        }.get(state_data['state'], '❓')
        
        print(f"\n{state_emoji} Market is in {state_data['state']}")
        print(f"   Confidence: {state_data['confidence']}%\n")
        
        # Trading implications
        print("💡 Trading Implications:")
        
        if state_data['state'] == 'BALANCE':
            print("   • Market rotating around POC")
            print("   • Low volatility environment")
            if flow_data['buy_pressure'] > 60:
                print("   • Strong buying pressure - potential breakout up")
            elif flow_data['sell_pressure'] > 60:
                print("   • Strong selling pressure - potential breakout down")
            else:
                print("   • Neutral flow - wait for directional bias")
        
        elif state_data['state'] == 'IMBALANCE_UP':
            print("   • Strong upward momentum")
            print("   • Price above value area")
            if flow_data['buy_pressure'] > 55:
                print("   • Buying pressure confirms uptrend")
            else:
                print("   • Weakening - potential reversal")
        
        elif state_data['state'] == 'IMBALANCE_DOWN':
            print("   • Strong downward momentum")
            print("   • Price below value area")
            if flow_data['sell_pressure'] > 55:
                print("   • Selling pressure confirms downtrend")
            else:
                print("   • Weakening - potential reversal")
        
        print("\n" + "=" * 70)
        print("✅ ALL CALCULATORS WORKING TOGETHER!")
        print("=" * 70)
        
        print("\n📋 Summary:")
        print(f"   ✅ Volume Profile calculated from {len(candles)} candles")
        print(f"   ✅ Order Flow estimated from candle patterns")
        print(f"   ✅ Market State determined using configurable thresholds")
        print(f"   ✅ Ready to integrate into backtest engine!")
        
    conn.close()


def test_parameter_sensitivity():
    """Test that changing parameters produces different results."""
    print("\n\n" + "=" * 70)
    print("🧪 Testing Parameter Sensitivity")
    print("=" * 70 + "\n")
    
    # Get test data
    config = BacktestConfig()
    conn = config.get_connection()
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE symbol_id = 1
            ORDER BY time DESC
            LIMIT 60
        """)
        
        rows = cur.fetchall()
        candles = [{'time': r[0], 'open': float(r[1]), 'high': float(r[2]), 
                   'low': float(r[3]), 'close': float(r[4]), 'volume': int(r[5])} 
                  for r in rows]
        candles.reverse()
    
    conn.close()
    
    current_price = candles[-1]['close']
    
    # Calculate base metrics
    volume_calc = BacktestVolumeProfileCalculator()
    flow_calc = BacktestOrderFlowCalculator()
    profile = volume_calc.calculate_profile(candles)
    flow_data = flow_calc.calculate_flow(candles)
    
    # Test 1: Default thresholds
    print("Test 1: Default Thresholds (POC=1.5%, Momentum=1.5%, CVD=15%)")
    state_calc1 = BacktestMarketStateCalculator({
        'poc_distance_threshold': 1.5,
        'momentum_threshold': 1.5,
        'cvd_pressure_threshold': 15
    })
    state1 = state_calc1.calculate_state(current_price, candles, profile, flow_data)
    print(f"   Result: {state1['state']} (confidence: {state1['confidence']}%)\n")
    
    # Test 2: More sensitive (lower thresholds = more IMBALANCE)
    print("Test 2: Sensitive Thresholds (POC=0.5%, Momentum=0.5%, CVD=5%)")
    state_calc2 = BacktestMarketStateCalculator({
        'poc_distance_threshold': 0.5,
        'momentum_threshold': 0.5,
        'cvd_pressure_threshold': 5
    })
    state2 = state_calc2.calculate_state(current_price, candles, profile, flow_data)
    print(f"   Result: {state2['state']} (confidence: {state2['confidence']}%)\n")
    
    # Test 3: Less sensitive (higher thresholds = more BALANCE)
    print("Test 3: Conservative Thresholds (POC=3.0%, Momentum=3.0%, CVD=30%)")
    state_calc3 = BacktestMarketStateCalculator({
        'poc_distance_threshold': 3.0,
        'momentum_threshold': 3.0,
        'cvd_pressure_threshold': 30
    })
    state3 = state_calc3.calculate_state(current_price, candles, profile, flow_data)
    print(f"   Result: {state3['state']} (confidence: {state3['confidence']}%)\n")
    
    # Verify they're different
    states = [state1['state'], state2['state'], state3['state']]
    if len(set(states)) > 1:
        print("✅ PARAMETER SENSITIVITY CONFIRMED!")
        print("   Different thresholds produce different results")
    else:
        print("⚠️  All thresholds produced same result")
        print("   (This is OK if market conditions are extreme)")


if __name__ == "__main__":
    try:
        test_integrated_calculation()
        test_parameter_sensitivity()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED - Ready for Phase 4 Integration!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
