# Strategy Refactoring - One Source of Truth

**Date**: 2025-10-02  
**Status**: ✅ Phase 1 Complete - Shared Strategy Created

## 🎯 Goal

Create ONE source of truth for trading strategy logic that is used by both:
- Live trading engine
- Backtesting engine

This ensures backtests accurately represent live trading performance.

## 📊 Current Status

### ✅ Completed

**Phase 1: Create Shared Strategy Class**
- Created `app/strategies/auction_market_strategy.py`
- Contains all core strategy logic:
  - Entry signal evaluation
  - Aggression score calculation
  - Flow direction determination
  - Position sizing
  - Exit signal evaluation
  - ATR-based stops/targets

### ⏳ Next Steps

**Phase 2: Update Live Engine** (`auto_strategy.py`)
- Refactor to use `AuctionMarketStrategy` class
- Keep Alpaca API integration
- Keep database config loading
- Delegate strategy logic to shared class

**Phase 3: Update Backtest Engine** (`backtest.py`)
- Replace placeholder logic with `AuctionMarketStrategy`
- Load market_state, order_flow, volume_profile from DB
- Use same entry/exit logic as live
- Calculate accurate performance metrics

**Phase 4: Test & Validate**
- Run backtest with real strategy
- Compare results with live trading
- Verify accuracy

## 🏗️ Architecture

### Before (❌ Wrong)
```
Live Engine (auto_strategy.py)
├── Strategy Logic A
└── Alpaca API

Backtest Engine (backtest.py)
├── Strategy Logic B (different!)
└── Historical Data
```

### After (✅ Correct)
```
Shared Strategy (auction_market_strategy.py)
├── Entry Logic
├── Exit Logic
└── Position Sizing

Live Engine (auto_strategy.py)
├── Uses Shared Strategy ←
├── Alpaca API
└── Database Config

Backtest Engine (backtest.py)
├── Uses Shared Strategy ←
└── Historical Data
```

## 📝 Strategy Logic

### Entry Conditions
1. Market state = IMBALANCE_UP or IMBALANCE_DOWN
2. Aggression score >= threshold (default 70)
3. Flow direction matches market state
4. Valid ATR available

### Exit Conditions
1. Stop loss hit (1.5x ATR)
2. Take profit hit (3x ATR, 2:1 R:R)
3. Opposite signal detected

### Position Sizing
- Risk per trade: 1% of equity (configurable)
- Based on stop loss distance
- Limited by available cash

## 🎯 Benefits

✅ **Accurate Backtests** - Test exactly what you trade  
✅ **Single Source of Truth** - One place to update strategy  
✅ **Confidence** - Know backtest results are real  
✅ **Easy Maintenance** - Change once, affects both  
✅ **Testable** - Can unit test strategy logic  

## 📊 Expected Impact

**Before Refactor:**
- Backtest: 22.76% return (fake strategy)
- Live: Unknown performance
- Confidence: Low (different logic)

**After Refactor:**
- Backtest: Real strategy performance
- Live: Same strategy
- Confidence: High (same logic)

## 🚀 Timeline

- ✅ Phase 1: Shared Strategy - **Complete**
- ⏳ Phase 2: Update Live Engine - **30 minutes**
- ⏳ Phase 3: Update Backtest - **30 minutes**
- ⏳ Phase 4: Test & Validate - **15 minutes**

**Total**: ~1.5 hours for complete refactor

## 💡 Next Actions

1. Update `auto_strategy.py` to use shared class
2. Update `backtest.py` to use shared class
3. Run new backtest with real strategy
4. Compare results and validate

---

**This is the right way to build a trading system!** 🎯
