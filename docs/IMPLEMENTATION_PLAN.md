# Auction Market Playbook - Implementation Plan

⚠️ **OUTDATED** - This document was the original plan. See [BACKTESTING_PLAN.md](../BACKTESTING_PLAN.md) for current roadmap.

**Date**: 2025-10-01  
**Status**: Phase 1 & 2 COMPLETED  
**Next**: Backtesting & Optimization

---

## 📋 Table of Contents

1. [Data Requirements & Provider Analysis](#data-requirements--provider-analysis)
2. [Phase 1: Semi-Automated (Option B)](#phase-1-semi-automated-option-b)
3. [Phase 2: Full Automation (Option C)](#phase-2-full-automation-option-c)
4. [Historical Data Import Strategy](#historical-data-import-strategy)
5. [Testing & Validation Plan](#testing--validation-plan)

---

## 🔍 Data Requirements & Provider Analysis

### What the Playbook Needs

| Data Type | Required For | Current Status | Provider |
|-----------|-------------|----------------|----------|
| **Tick Data** | Order flow, aggression detection | ✅ Have | Alpaca |
| **Volume Profile** | POC, VAH, VAL, LVNs | ✅ Have | Computed from ticks |
| **Order Flow** | CVD, buy/sell pressure | ⚠️ Estimated | Alpaca (uptick/downtick) |
| **True Aggressor** | Accurate buy/sell side | ❌ Missing | Need Rithmic/CME |
| **Bid/Ask Spread** | Footprint charts | ❌ Missing | Need Level 2 data |
| **Historical Bars** | Backtesting | ✅ Can fetch | Alpaca API |

### Provider Comparison

#### 1. Alpaca (Current - FREE)

**✅ Pros:**
- Free for paper trading
- Real-time WebSocket for stocks
- Historical data API (1-min bars)
- Good for US stocks during market hours
- IEX feed included

**❌ Cons:**
- No true aggressor data (uses uptick/downtick estimation)
- No Level 2 / bid-ask data
- Stocks only (no futures)
- No crypto support on IEX feed
- Limited to US market hours

**Accuracy for Playbook**: 70-80% (good enough for stocks)

**Recommendation**: ✅ **Use for Phase 1 & 2 with US stocks**

---

#### 2. Rithmic (Professional - $50-100/mo)

**✅ Pros:**
- TRUE aggressor data (knows actual buy/sell side)
- Full order flow (bid/ask, depth)
- Futures support (ES, NQ, etc.)
- 24/7 trading (futures)
- Low latency
- Designed for order flow trading

**❌ Cons:**
- Costs $50-100/month
- Requires broker connection
- More complex integration
- Futures-focused (not stocks)

**Accuracy for Playbook**: 95-99% (professional grade)

**Recommendation**: ⏰ **Upgrade for Phase 3 (futures trading)**

---

#### 3. Polygon.io (Middle Ground - $29-99/mo)

**✅ Pros:**
- Real-time tick data
- Stocks + Crypto
- Historical data included
- Better than Alpaca, cheaper than Rithmic
- Good API documentation

**❌ Cons:**
- Still no true aggressor for stocks
- No futures
- Monthly cost

**Accuracy for Playbook**: 75-85%

**Recommendation**: ⏰ **Consider if need crypto or better stock data**

---

### 🎯 Recommended Data Strategy

**Phase 1-2 (Now - 3 months):**
- ✅ Use **Alpaca** for US stocks
- ✅ Trade during **US market hours** (09:30-16:00 ET)
- ✅ Focus on **liquid stocks** (AAPL, SPY, QQQ, TSLA)
- ✅ Accept 70-80% accuracy on order flow

**Phase 3 (3-6 months):**
- ⏰ Upgrade to **Rithmic** for futures
- ⏰ Trade **ES, NQ** (most liquid futures)
- ⏰ Get true aggressor data
- ⏰ 24/7 trading capability

**Why This Works:**
1. Learn the strategy with stocks first (cheaper, simpler)
2. Validate the approach before paying for Rithmic
3. Alpaca is good enough to prove the concept
4. Upgrade when ready for serious futures trading

---

## 🚀 Phase 1: Semi-Automated (Option B)

**Goal**: Get actionable alerts and indicators in 5-10 hours  
**Timeline**: This week (1-2 days)  
**Cost**: $0 (use Alpaca free tier)

### Component 1: Market State Detection (3-4 hours)

**File**: `services/engine/app/detectors/market_state.py`

**What It Does:**
- Analyzes last 60 minutes of price action
- Determines if market is BALANCE or IMBALANCE
- Updates `market_state` table every minute
- Displays on dashboard

**Algorithm:**
```python
def detect_market_state(symbol_id):
    """
    Simple market state detection based on:
    1. Distance from POC
    2. Price range vs value area
    3. Directional momentum
    """
    # Get recent data
    poc = get_current_poc(symbol_id)
    current_price = get_latest_price(symbol_id)
    vah, val = get_value_area(symbol_id)
    
    # Calculate metrics
    distance_from_poc = abs(current_price - poc) / poc * 100
    in_value_area = val <= current_price <= vah
    momentum = calculate_momentum(symbol_id, lookback=20)
    
    # Decision logic
    if distance_from_poc < 1.0 and in_value_area:
        return 'BALANCE'
    elif momentum > 0.5 and current_price > vah:
        return 'IMBALANCE_UP'
    elif momentum < -0.5 and current_price < val:
        return 'IMBALANCE_DOWN'
    else:
        return 'BALANCE'
```

**Dashboard Display:**
```
┌─────────────────────────────┐
│ Market State: IMBALANCE_UP  │
│ Distance from POC: 1.8%     │
│ Momentum: Strong ↑          │
└─────────────────────────────┘
```

**Deliverables:**
- [x] Python detector script
- [x] Database updates every 60s
- [x] Dashboard widget
- [x] Color coding (green=imbalance, yellow=balance)

---

### Component 2: LVN Alert System (2 hours)

**File**: `services/engine/app/alerts/lvn_alerts.py`

**What It Does:**
- Monitors price approaching LVNs
- Sends alert when within 0.5% of LVN
- Shows distance to nearest LVN on dashboard

**Algorithm:**
```python
def check_lvn_proximity(symbol_id):
    """
    Check if price is approaching any LVN.
    """
    current_price = get_latest_price(symbol_id)
    lvns = get_current_lvns(symbol_id)
    
    for lvn in lvns:
        distance = abs(current_price - lvn) / lvn * 100
        if distance < 0.5:  # Within 0.5%
            return {
                'alert': True,
                'lvn_price': lvn,
                'distance': distance,
                'direction': 'approaching'
            }
    
    return {'alert': False}
```

**Dashboard Display:**
```
┌─────────────────────────────┐
│ 🔔 LVN ALERT                │
│ Price: $254.20              │
│ Target LVN: $254.50         │
│ Distance: 0.3% (↑)          │
└─────────────────────────────┘
```

**Deliverables:**
- [x] Alert detection logic
- [x] Dashboard alert widget
- [x] Sound notification (optional)
- [x] Show nearest LVN on chart

---

### Component 3: Aggressive Flow Indicator (2-3 hours)

**File**: `services/engine/app/indicators/aggressive_flow.py`

**What It Does:**
- Detects volume spikes
- Identifies aggressive buying/selling
- Shows real-time aggression score

**Algorithm:**
```python
def detect_aggressive_flow(symbol_id, lookback_minutes=5):
    """
    Detect aggressive order flow.
    
    Indicators:
    - Volume spike (> 2x average)
    - Strong CVD momentum
    - Consecutive trades in one direction
    """
    # Get recent order flow
    recent_flow = get_order_flow(symbol_id, lookback_minutes)
    avg_volume = calculate_average_volume(symbol_id, 60)
    
    # Check for spikes
    current_volume = recent_flow[-1]['volume']
    volume_ratio = current_volume / avg_volume
    
    # Check CVD momentum
    cvd_change = recent_flow[-1]['cvd'] - recent_flow[0]['cvd']
    cvd_momentum = cvd_change / lookback_minutes
    
    # Calculate aggression score
    aggression_score = 0
    if volume_ratio > 2.0:
        aggression_score += 30
    if abs(cvd_momentum) > 1000:
        aggression_score += 40
    if recent_flow[-1]['buy_pressure'] > 70:
        aggression_score += 30
    
    return {
        'score': min(aggression_score, 100),
        'direction': 'BUY' if cvd_momentum > 0 else 'SELL',
        'volume_spike': volume_ratio > 2.0
    }
```

**Dashboard Display:**
```
┌─────────────────────────────┐
│ 🔥 AGGRESSIVE FLOW          │
│ Score: 85/100               │
│ Direction: BUY ↑            │
│ Volume: 2.3x average        │
│ CVD: +1,250 (accelerating)  │
└─────────────────────────────┘
```

**Deliverables:**
- [x] Aggression detection logic
- [x] Real-time score calculation
- [x] Dashboard indicator
- [x] Visual alerts (color changes)

---

### Component 4: Session Indicator (1 hour)

**File**: `web/app/Livewire/SessionIndicator.php`

**What It Does:**
- Shows current trading session
- Recommends which setup to use
- Displays session-specific stats

**Dashboard Display:**
```
┌─────────────────────────────┐
│ Session: NEW YORK 🗽        │
│ Time: 10:45 ET              │
│ Recommended: Trend Model    │
│ Market Open: 09:30-16:00    │
└─────────────────────────────┘
```

**Deliverables:**
- [x] Session detection logic
- [x] Dashboard widget
- [x] Setup recommendations
- [x] Time until next session

---

### Phase 1 Summary

**Total Time**: 8-10 hours  
**Deliverables**: 4 new components  
**Value**: Actionable trading alerts

**What You Can Do After Phase 1:**
1. ✅ See market state in real-time
2. ✅ Get alerted when price hits LVNs
3. ✅ Know when aggressive flow appears
4. ✅ Understand which session/setup to use
5. ✅ Make informed manual trading decisions

---

## 🎯 Phase 2: Full Automation (Option C)

**Goal**: Automated signal generation with full playbook logic  
**Timeline**: 2-3 weeks (40-55 hours)  
**Cost**: $0 (still using Alpaca)

### Week 1: Core Detection Logic (15-20 hours)

#### 1. Balance Range Identification (4 hours)
**File**: `services/engine/app/detectors/balance_range.py`

```python
def identify_balance_range(symbol_id, session_start):
    """
    Define balance high/low for the session.
    Uses previous session's volume profile.
    """
    # Get previous session's profile
    # Identify VAH/VAL as balance boundaries
    # Store in market_state table
```

#### 2. Impulse Leg Detection (5 hours)
**File**: `services/engine/app/detectors/impulse_leg.py`

```python
def detect_impulse_leg(symbol_id):
    """
    Identify when market breaks out of balance.
    Track the impulse move for LVN analysis.
    """
    # Detect breakout from balance
    # Track price movement
    # Calculate impulse start/end
```

#### 3. LVN on Impulse Leg (4 hours)
**File**: `services/engine/app/detectors/impulse_lvns.py`

```python
def find_impulse_lvns(symbol_id, impulse_start, impulse_end):
    """
    Apply volume profile to impulse leg.
    Find LVNs within that specific move.
    """
    # Get volume profile for impulse timeframe
    # Identify LVNs
    # Return as potential entry zones
```

#### 4. Pullback Detection (3 hours)
**File**: `services/engine/app/detectors/pullback.py`

```python
def detect_pullback_to_lvn(symbol_id, lvn_price):
    """
    Monitor for price pulling back to LVN.
    """
    # Check if price approaching LVN
    # Confirm pullback structure
    # Ready for entry evaluation
```

---

### Week 2: Setup Implementation (15-20 hours)

#### 5. Trend Model Setup (8 hours)
**File**: `services/engine/app/setups/trend_model.py`

```python
class TrendModel:
    """
    Setup 1: Out-of-Balance → Seek New Balance
    
    Entry Conditions:
    1. Market state = IMBALANCE
    2. Impulse leg identified
    3. Price pulls back to LVN on impulse
    4. Aggressive flow in trend direction
    """
    
    def evaluate(self, symbol_id):
        # Check all conditions
        # Generate signal if met
        # Calculate stop/target
        return signal
```

**Signal Output:**
```json
{
  "signal_type": "BUY",
  "setup": "TREND_MODEL",
  "entry_price": 254.50,
  "stop_loss": 254.20,
  "target": 255.80,
  "confidence": 85,
  "reason": "Imbalance up, pullback to LVN, aggressive buying"
}
```

#### 6. Mean Reversion Setup (8 hours)
**File**: `services/engine/app/setups/mean_reversion.py`

```python
class MeanReversionModel:
    """
    Setup 2: Failed Breakout → Back to Balance
    
    Entry Conditions:
    1. Market was in BALANCE
    2. Breakout attempt failed
    3. Price reclaimed inside balance
    4. Pullback to LVN on reclaim leg
    5. Aggressive flow toward POC
    """
    
    def evaluate(self, symbol_id):
        # Check all conditions
        # Generate signal if met
        # Calculate stop/target
        return signal
```

---

### Week 3: Risk Management & Testing (10-15 hours)

#### 7. Risk Calculator (3 hours)
**File**: `services/engine/app/risk/calculator.py`

```python
def calculate_risk_parameters(signal, account_balance):
    """
    Calculate position size based on risk %.
    
    Risk: 0.25-0.5% of account per trade
    """
    risk_amount = account_balance * 0.005  # 0.5%
    stop_distance = abs(signal.entry - signal.stop)
    position_size = risk_amount / stop_distance
    
    return {
        'position_size': position_size,
        'risk_amount': risk_amount,
        'risk_reward_ratio': calculate_rr(signal)
    }
```

#### 8. Signal Manager (4 hours)
**File**: `services/engine/app/signals/manager.py`

```python
class SignalManager:
    """
    Manages signal generation and storage.
    """
    
    def generate_signals(self):
        # Run all setups
        # Evaluate conditions
        # Store valid signals
        # Send notifications
```

#### 9. Backtesting Framework (5 hours)
**File**: `services/engine/app/backtest/runner.py`

```python
class Backtester:
    """
    Test strategies on historical data.
    """
    
    def run_backtest(self, symbol, start_date, end_date):
        # Load historical data
        # Run strategy logic
        # Calculate performance metrics
        # Generate report
```

#### 10. Performance Metrics (3 hours)
**File**: `services/engine/app/metrics/calculator.py`

```python
def calculate_metrics(trades):
    """
    Calculate strategy performance.
    
    Metrics:
    - Win rate
    - Average R:R
    - Profit factor
    - Max drawdown
    - Sharpe ratio
    """
```

---

## 📊 Historical Data Import Strategy

### Option 1: Alpaca Historical API (Recommended)

**What You Get:**
- 1-minute bars for any US stock
- Up to 5 years of history
- Free with paper trading account
- Easy to fetch via API

**Implementation:**
```python
# Already created: scripts/backfill-alpaca-historical.py

# Usage:
docker compose run --rm ingestion python3 -c "
# Fetch last 30 days of AAPL data
# Store in database
# Ready for backtesting
"
```

**Limitations:**
- 1-minute resolution (no tick data for history)
- Can't backtest order flow accurately
- Good for volume profile backtesting

**Recommendation**: ✅ Use for initial backtesting

---

### Option 2: Polygon.io Historical (Better Quality)

**What You Get:**
- Tick-level historical data
- Better for order flow backtesting
- Stocks + Crypto
- $99/mo plan includes history

**When to Use:**
- After validating strategy with Alpaca
- When need tick-level backtesting
- Before going live with real money

---

### Option 3: Manual CSV Import

**What You Get:**
- Import any data source
- Full control over format
- Can use free datasets

**Implementation:**
```python
# Create: scripts/import-csv.py

def import_csv(file_path, symbol):
    """
    Import historical data from CSV.
    
    Expected format:
    timestamp,open,high,low,close,volume
    """
```

---

### Historical Data Strategy

**Phase 1 (Now):**
- ✅ Use Alpaca API to fetch last 30-90 days
- ✅ Store in database
- ✅ Use for initial backtesting

**Phase 2 (After validation):**
- ⏰ Consider Polygon.io for tick data
- ⏰ More accurate order flow backtesting
- ⏰ Longer history (years)

**Phase 3 (Production):**
- ⏰ Rithmic for live futures
- ⏰ Use Rithmic historical data
- ⏰ True aggressor data for backtesting

---

## 🧪 Testing & Validation Plan

### Stage 1: Unit Testing (Week 1)
- Test each detector independently
- Verify calculations are correct
- Mock data for edge cases

### Stage 2: Integration Testing (Week 2)
- Test full signal generation pipeline
- Verify database updates
- Check dashboard displays

### Stage 3: Historical Backtesting (Week 3)
- Run on 30 days of historical data
- Calculate win rate, R:R, profit factor
- Tune parameters

### Stage 4: Paper Trading (Week 4)
- Run live with paper account
- Monitor signal quality
- Track performance

### Stage 5: Live Trading (Month 2+)
- Start with small position sizes
- Gradually increase as confidence grows
- Continuous monitoring and tuning

---

## 📈 Success Metrics

### Phase 1 (Semi-Automated)
- ✅ Market state accuracy > 80%
- ✅ LVN alerts trigger at right times
- ✅ Aggressive flow detection catches big moves
- ✅ User can make informed manual trades

### Phase 2 (Full Automation)
- ✅ Signal generation working
- ✅ Win rate > 50%
- ✅ Average R:R > 1.5:1
- ✅ Profit factor > 1.5
- ✅ Max drawdown < 10%

### Phase 3 (Production)
- ✅ Consistent profitability (3+ months)
- ✅ Sharpe ratio > 1.0
- ✅ Ready for live trading

---

## 💰 Cost Breakdown

### Phase 1-2 (First 3 months)
- **Alpaca**: $0 (paper trading)
- **Infrastructure**: $0 (local Docker)
- **Total**: $0/month

### Phase 3 (After validation)
- **Rithmic**: $50-100/month (futures data)
- **Broker**: Variable (depends on broker)
- **VPS** (optional): $20-50/month
- **Total**: $70-150/month

### ROI Calculation
If strategy generates $500-1000/month profit:
- Break-even: Month 1
- Net profit: $350-850/month after costs

---

## 🎯 Next Steps (This Week)

### Day 1-2: Market State Detection
1. Create `market_state.py` detector
2. Implement simple algorithm
3. Add dashboard widget
4. Test with live data

### Day 3: LVN Alerts
1. Create `lvn_alerts.py`
2. Add proximity detection
3. Dashboard alert widget
4. Test alerts

### Day 4: Aggressive Flow
1. Create `aggressive_flow.py`
2. Implement scoring algorithm
3. Dashboard indicator
4. Test with historical spikes

### Day 5: Session Indicator + Testing
1. Add session detection
2. Integration testing
3. User acceptance testing
4. Documentation

---

## 📝 Summary

**Phase 1 (This Week):**
- 🎯 Goal: Semi-automated alerts
- ⏱️ Time: 8-10 hours
- 💰 Cost: $0
- 📊 Data: Alpaca (good enough)
- ✅ Deliverable: Actionable trading tool

**Phase 2 (Weeks 2-4):**
- 🎯 Goal: Full automation
- ⏱️ Time: 40-55 hours
- 💰 Cost: $0
- 📊 Data: Alpaca + historical
- ✅ Deliverable: Complete playbook implementation

**Phase 3 (Months 2-3):**
- 🎯 Goal: Production-ready
- ⏱️ Time: Ongoing tuning
- 💰 Cost: $70-150/month (Rithmic)
- 📊 Data: Professional futures data
- ✅ Deliverable: Live trading system

**You're ready to start! Want me to begin implementing Phase 1, Component 1 (Market State Detection)?**
