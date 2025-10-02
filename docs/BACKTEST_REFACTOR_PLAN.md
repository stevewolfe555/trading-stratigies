# Backtest Engine Refactor - On-the-Fly Calculation Plan

## Problem Statement

**Current Issue:**
The backtest engine relies on pre-calculated `market_state` and `order_flow` data from the database, which only exists for periods when the live engine was running (~25 hours of data). This causes:

1. ❌ Same results regardless of config changes
2. ❌ Can't backtest historical periods (only last 1-2 days)
3. ❌ Expert mode parameters have no effect
4. ❌ Results don't match what live trading would do

**Root Cause:**
```python
# Current broken approach:
state_data = self.data_loader.load_market_state(symbol_id, current_time)
# ↑ Returns None for historical data!
```

## Solution Architecture

### High-Level Flow

```
CURRENT (BROKEN):
┌─────────┐     ┌──────────────┐     ┌──────────┐
│ Candles │────▶│ Read DB      │────▶│ Strategy │
│  Data   │     │ market_state │     │ Evaluate │
└─────────┘     └──────────────┘     └──────────┘
                      ↑ Only 25 hours!

PROPOSED (FIXED):
┌─────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ Candles │────▶│ Calculate    │────▶│ Calculate    │────▶│ Strategy │
│  Data   │     │ Volume       │     │ Market State │     │ Evaluate │
└─────────┘     │ Profile      │     │ & Flow       │     └──────────┘
                └──────────────┘     └──────────────┘
                  (POC/VAH/VAL)       (BALANCE/IMBALANCE)
```

## Implementation Steps

### Phase 1: Volume Profile Calculator (NEW)

**File:** `services/engine/app/backtest_volume_profile.py`

**Purpose:** Calculate POC, VAH, VAL from candle data

**Key Methods:**
```python
class BacktestVolumeProfileCalculator:
    def calculate_profile(self, candles: List[Dict], lookback_minutes: int = 60) -> Dict:
        """
        Calculate volume profile from recent candles.
        
        Returns:
            {
                'poc': float,      # Point of Control
                'vah': float,      # Value Area High
                'val': float,      # Value Area Low
                'total_volume': int
            }
        """
```

**Algorithm:**
1. Get last N minutes of candles
2. Create price levels (buckets)
3. Sum volume at each price level
4. Find POC (highest volume level)
5. Calculate value area (70% of volume around POC)
6. Return VAH (top) and VAL (bottom) of value area

---

### Phase 2: Market State Calculator (NEW)

**File:** `services/engine/app/backtest_market_state.py`

**Purpose:** Calculate market state using same logic as live detector

**Key Methods:**
```python
class BacktestMarketStateCalculator:
    def __init__(self, config_params: Dict):
        # Use configurable thresholds from Expert Mode
        self.poc_distance_threshold = config_params.get('poc_distance_threshold', 1.5)
        self.momentum_threshold = config_params.get('momentum_threshold', 1.5)
        self.cvd_pressure_threshold = config_params.get('cvd_pressure_threshold', 15)
        self.lookback_period = config_params.get('lookback_period', 60)
    
    def calculate_state(self, 
                       current_price: float,
                       candles: List[Dict],
                       profile: Dict,
                       flow_data: Dict) -> Dict:
        """
        Calculate market state from current data.
        
        Returns:
            {
                'state': 'BALANCE' | 'IMBALANCE_UP' | 'IMBALANCE_DOWN',
                'confidence': int (0-100),
                'distance_from_poc_pct': float,
                'momentum_score': float
            }
        """
```

**Logic (mirrors live detector):**
1. Calculate distance from POC
2. Check if in value area
3. Calculate momentum (price change over lookback period)
4. Get CVD pressure from flow data
5. Apply rules with configurable thresholds:
   - POC distance < threshold → BALANCE
   - Momentum > threshold → IMBALANCE
   - CVD pressure > threshold → IMBALANCE
6. Return state with confidence

---

### Phase 3: Order Flow Calculator (NEW)

**File:** `services/engine/app/backtest_order_flow.py`

**Purpose:** Calculate order flow metrics from candle data

**Key Methods:**
```python
class BacktestOrderFlowCalculator:
    def calculate_flow(self, candles: List[Dict], lookback_buckets: int = 5) -> Dict:
        """
        Calculate order flow metrics from candles.
        
        Returns:
            {
                'cumulative_delta': int,
                'buy_pressure': float (0-100),
                'sell_pressure': float (0-100),
                'cvd_momentum': int
            }
        """
```

**Algorithm:**
1. For each candle, estimate buy/sell volume:
   - If close > open: More buying (green candle)
   - If close < open: More selling (red candle)
   - Ratio based on (close - low) / (high - low)
2. Calculate cumulative delta (buy volume - sell volume)
3. Calculate buy/sell pressure percentages
4. Calculate CVD momentum (change over last N buckets)

---

### Phase 4: Integrate into Backtest Engine

**File:** `services/engine/app/backtest_engine.py`

**Changes:**

#### 4.1: Add Calculators to __init__
```python
def __init__(self, parameters: Optional[Dict] = None):
    self.config = BacktestConfig(parameters)
    self.data_loader = BacktestDataLoader(self.config.get_connection())
    self.portfolio = BacktestPortfolio(...)
    self.analyzer = BacktestAnalyzer(...)
    
    # NEW: Add calculators
    self.volume_profile_calc = BacktestVolumeProfileCalculator()
    self.market_state_calc = BacktestMarketStateCalculator(parameters)
    self.order_flow_calc = BacktestOrderFlowCalculator()
```

#### 4.2: Modify check_entry_signal
```python
def check_entry_signal(self, symbol: str, symbol_id: int, current_time: datetime) -> Optional[Dict]:
    """Check for entry signal using strategy logic."""
    
    # Get current price
    current_price = self._get_current_price(symbol_id, current_time)
    
    # Get recent candles for calculations
    recent_candles = self._get_recent_candles(symbol_id, current_time, lookback_minutes=60)
    
    # CALCULATE (don't read from DB):
    
    # 1. Volume Profile
    profile = self.volume_profile_calc.calculate_profile(recent_candles)
    
    # 2. Order Flow
    flow_data = self.order_flow_calc.calculate_flow(recent_candles)
    
    # 3. Market State (using configurable thresholds)
    state_data = self.market_state_calc.calculate_state(
        current_price=current_price,
        candles=recent_candles,
        profile=profile,
        flow_data=flow_data
    )
    
    # 4. Calculate ATR
    atr = self._calculate_atr(recent_candles)
    
    # 5. Evaluate strategy
    signal = self.strategy.evaluate_entry_signal(
        market_state=state_data['state'],
        confidence=state_data['confidence'],
        buy_pressure=flow_data['buy_pressure'],
        sell_pressure=flow_data['sell_pressure'],
        cvd_momentum=flow_data['cvd_momentum'],
        current_price=current_price,
        atr=atr,
        symbol=symbol
    )
    
    return signal
```

---

### Phase 5: Remove Database Dependencies

**Changes:**
1. Remove `load_market_state()` from `backtest_data.py`
2. Remove `load_order_flow()` from `backtest_data.py`
3. Keep `load_candles()` - still needed

**Result:** Backtest only depends on candle data (which we have for all historical periods)

---

## Configuration Flow

### Expert Mode Parameters → Backtest

```
UI (Expert Mode)
  ↓
Livewire Component (Backtesting.php)
  ↓
BacktestService.php
  ↓
backtest.py (CLI args)
  ↓
BacktestConfig (parameters dict)
  ↓
BacktestMarketStateCalculator (uses thresholds)
  ↓
Market State Calculation (with user's settings)
```

**Parameters that now work:**
- `poc_distance_threshold` → Affects BALANCE vs IMBALANCE detection
- `momentum_threshold` → Affects momentum-based state changes
- `cvd_pressure_threshold` → Affects flow-based state changes
- `lookback_period` → Affects calculation window
- `allow_balance_trades` → Enables trading during BALANCE

---

## Benefits

### ✅ Immediate Benefits:
1. **Works for any historical period** - Only needs candle data
2. **Respects configuration** - Uses your actual parameters
3. **Consistent with live** - Same calculation logic
4. **Expert mode works** - Thresholds actually affect results
5. **More trades** - Can detect BALANCE periods with high aggression

### ✅ Testing Benefits:
1. **Compare configurations** - See real differences
2. **Optimize parameters** - Find best thresholds
3. **Validate strategy** - True historical performance
4. **Reproducible** - Same inputs = same outputs

---

## Data Requirements

### Before (BROKEN):
- ✅ Candle data (we have years)
- ❌ Market state data (only 25 hours)
- ❌ Order flow data (only 25 hours)
- ❌ Volume profile data (only 25 hours)

### After (FIXED):
- ✅ Candle data (we have years) ← ONLY REQUIREMENT!

---

## Performance Considerations

### Calculation Overhead:
- **Volume Profile**: ~1ms per timestamp (simple aggregation)
- **Order Flow**: ~0.5ms per timestamp (candle analysis)
- **Market State**: ~0.5ms per timestamp (rule evaluation)
- **Total**: ~2ms per timestamp

### For 1-year backtest:
- Timestamps: ~100,000 (252 days × 390 min/day)
- Calculation time: ~200 seconds (3.3 minutes)
- Current backtest time: ~30 seconds
- **New total**: ~4 minutes (acceptable!)

### Optimization opportunities:
1. Cache volume profiles (only recalc every N minutes)
2. Vectorize calculations (NumPy)
3. Parallel processing (multiple symbols)

---

## Testing Plan

### Test 1: Verify Calculations Match Live
```python
# Compare live detector output vs backtest calculator
# For same timestamp, should get same market state
```

### Test 2: Parameter Sensitivity
```python
# Run backtest with different thresholds
# Results should differ (proving config works)

Test A: poc_distance_threshold = 1.5 → X trades
Test B: poc_distance_threshold = 2.5 → Y trades (Y > X)
```

### Test 3: Historical Coverage
```python
# Run backtest for 1 year ago
# Should work (not return "no data")
```

### Test 4: Allow Balance Trades
```python
# Run with allow_balance_trades = False → N trades
# Run with allow_balance_trades = True → M trades (M > N)
```

---

## Migration Path

### Step 1: Implement Calculators (Non-breaking)
- Create new calculator classes
- Add unit tests
- Don't integrate yet

### Step 2: Add Parallel Calculation (Testing)
- Calculate on-the-fly AND read from DB
- Compare results
- Log differences

### Step 3: Switch to Calculated (Breaking)
- Use calculated values
- Remove DB reads
- Update tests

### Step 4: Cleanup (Optimization)
- Remove unused code
- Add caching
- Performance tuning

---

## Files to Create

1. `services/engine/app/backtest_volume_profile.py` (NEW)
2. `services/engine/app/backtest_market_state.py` (NEW)
3. `services/engine/app/backtest_order_flow.py` (NEW)

## Files to Modify

1. `services/engine/app/backtest_engine.py` (MAJOR)
2. `services/engine/app/backtest_data.py` (MINOR - remove methods)
3. `services/engine/app/backtest_config.py` (MINOR - add param accessors)

## Files to Test

1. All new calculator files (unit tests)
2. Integration test (full backtest)
3. Comparison test (vs live engine)

---

## Success Criteria

✅ Backtest runs for any historical period (not just last 25 hours)
✅ Changing Expert Mode parameters produces different results
✅ Allow Balance Trades checkbox increases trade count
✅ Results are consistent and reproducible
✅ Performance is acceptable (<5 min for 1-year backtest)
✅ Market state calculations match live engine logic

---

## Timeline Estimate

- **Phase 1** (Volume Profile): 1-2 hours
- **Phase 2** (Market State): 1-2 hours
- **Phase 3** (Order Flow): 1 hour
- **Phase 4** (Integration): 2-3 hours
- **Phase 5** (Testing): 1-2 hours

**Total**: 6-10 hours of development

---

## Questions to Resolve

1. ❓ Should we cache calculations to improve performance?
2. ❓ Should we save calculated market states to DB for future reference?
3. ❓ Should we add progress indicators for long backtests?
4. ❓ Should we parallelize calculations across symbols?

---

## Next Steps

1. ✅ Review and approve this plan
2. ⏳ Implement Phase 1 (Volume Profile Calculator)
3. ⏳ Implement Phase 2 (Market State Calculator)
4. ⏳ Implement Phase 3 (Order Flow Calculator)
5. ⏳ Integrate into Backtest Engine
6. ⏳ Test and validate
7. ⏳ Deploy and verify

---

**Status**: 📋 PLANNING COMPLETE - Ready for implementation
**Priority**: 🔥 HIGH - Blocking accurate backtesting
**Impact**: 🎯 CRITICAL - Enables proper strategy validation
