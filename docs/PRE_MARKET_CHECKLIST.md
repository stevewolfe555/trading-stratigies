# Pre-Market Checklist - System Ready ✅

**Date**: 2025-10-01  
**Market Opens**: 09:30 ET (16:30 your time)  
**Status**: 🟢 ALL SYSTEMS GO

---

## ✅ System Status Check

### 1. Docker Services - ALL RUNNING
```
✅ trading_db                 - TimescaleDB (healthy)
✅ trading_redis              - Redis cache (healthy)
✅ trading_engine             - Trading engine + auto-trading
✅ trading_ingestion          - Data collection (Alpaca WebSocket)
✅ trading_profile_calculator - Volume profile analysis
✅ trading_reverb             - WebSocket server for dashboard
✅ trading_relay              - Laravel queue worker
```

### 2. Laravel Dashboard - READY
```
✅ Running on http://127.0.0.1:8002
✅ Database connected
✅ Redis connected
✅ WebSocket server active
✅ All views compiled
✅ Config cached
```

### 3. Symbols Configured - MAGNIFICENT 7
```
✅ AAPL  - Apple
✅ MSFT  - Microsoft
✅ GOOGL - Alphabet
✅ AMZN  - Amazon
✅ NVDA  - NVIDIA
✅ META  - Meta
✅ TSLA  - Tesla
```

### 4. Trading Configuration - CONSERVATIVE
```
✅ AUTO_TRADING_ENABLED=true
✅ MAX_POSITIONS=1              (1 trade at a time)
✅ RISK_PER_TRADE_PCT=1.0      ($1,000 on $100k account)
✅ MAX_DAILY_LOSS_PCT=3.0      ($3,000 max loss per day)
✅ STOP_LOSS_PCT=2.0           (2% stop loss)
✅ TAKE_PROFIT_PCT=4.0         (4% take profit - 2:1 R:R)
✅ MIN_AGGRESSION_SCORE=70     (High quality setups only)
```

### 5. Data Collection - READY
```
✅ Market state detection running (every 60s)
✅ Aggressive flow detection running (every 10s)
✅ LVN alert system active (every 10s)
✅ Auto-trading checks running (every 30s)
```

---

## ⚠️ IMPORTANT: API Keys Status

### Current Status: DEMO MODE
```
⚪ Using data feed API keys (not trading keys)
⚪ System will run but NOT execute real trades
⚪ Dashboard shows mock $100k account
```

### To Enable Live Paper Trading:
1. **Get trading API keys** from: https://app.alpaca.markets/paper/dashboard/overview
2. **Update both .env files**:
   - `/Users/steve/Projects/trading-strategies/.env` (line 20-21)
   - `/Users/steve/Projects/trading-strategies/web/.env` (line 93-94)
3. **Restart engine**: `docker compose restart engine`
4. **Refresh dashboard**: Will show 🟢 Connected

---

## 📊 Dashboard Widgets - ALL ACTIVE

1. ✅ **Account Overview** - Balance, buying power, risk metrics
2. ✅ **Session Indicator** - Shows current session (London/NY/Asian)
3. ✅ **Market State** - BALANCE/IMBALANCE detection
4. ✅ **Aggressive Flow** - Order flow strength indicator
5. ✅ **LVN Alerts** - Entry zone proximity alerts
6. ✅ **Active Positions** - Real-time position tracking
7. ✅ **Trade History** - Last 20 trades with details
8. ✅ **Professional Chart** - TradingView with volume profile

---

## 🕐 Market Schedule (ET)

### Pre-Market
- **04:00-09:30 ET** - Pre-market trading
- System monitors but doesn't trade (low liquidity)

### Regular Hours (BEST FOR TRADING)
- **09:30-16:00 ET** - New York session
- ✅ Auto-trading active
- ✅ Trend Model recommended
- ✅ High liquidity and momentum

### After-Hours
- **16:00-20:00 ET** - After-hours trading
- System monitors but reduced opportunities

---

## 🎯 What Happens When Market Opens

### 09:30 ET - Market Opens

**Minute 1-5:**
```
1. Ingestion service starts collecting real-time data
2. Candles start populating database
3. Volume profile begins calculating
4. Market state detection analyzes price action
```

**Minute 5-10:**
```
1. First volume profile metrics available
2. Market state determined (BALANCE/IMBALANCE)
3. Aggressive flow scores calculated
4. System ready to generate signals
```

**Minute 10+:**
```
1. Auto-trading actively monitoring all 7 symbols
2. If conditions met:
   - 🎯 Entry signal detected
   - 🚀 Bracket order placed
   - ✅ Position opened
   - 📊 Dashboard updates
```

---

## 🔍 How to Monitor

### Watch Engine Logs
```bash
# In terminal:
docker compose logs engine -f

# Look for:
🤖 Running automated trading check...
🎯 ENTRY SIGNAL DETECTED: AAPL - IMBALANCE_UP + Aggressive BUY (score: 85)
🚀 EXECUTING TRADE: BUY 10 AAPL @ $254.50 (SL: $249.41, TP: $264.68)
✅ Trade executed successfully! Order ID: abc123
```

### Watch Dashboard
```
http://127.0.0.1:8002/dashboard

Monitor:
- Market State widget (BALANCE → IMBALANCE)
- Aggressive Flow score (watching for >70)
- Active Positions (trades will appear here)
- Trade History (execution log)
```

### Check Alpaca Account
```
https://app.alpaca.markets/paper/dashboard/overview

See:
- Real orders placed
- Position details
- Account balance changes
- Order history
```

---

## 🛡️ Safety Features ACTIVE

### Position Limits
- ✅ Max 1 position at a time
- ✅ Won't over-leverage
- ✅ Diversification across 7 symbols

### Risk Controls
- ✅ 1% risk per trade ($1,000 max)
- ✅ 3% daily loss limit ($3,000 max)
- ✅ Automatic stop-loss on every trade
- ✅ Bracket orders (can't forget to exit)

### Entry Filters
- ✅ Must be IMBALANCE (not choppy)
- ✅ Aggression score >70 (high quality)
- ✅ Flow direction matches trend
- ✅ Account balance checks

### Exit Management
- ✅ 2% stop-loss (automatic)
- ✅ 4% take-profit (automatic)
- ✅ Managed by Alpaca (no monitoring needed)
- ✅ Whichever hits first, other cancels

---

## 🚨 Emergency Procedures

### Stop All Trading Immediately
```bash
# 1. Disable auto-trading
# Edit: /Users/steve/Projects/trading-strategies/.env
AUTO_TRADING_ENABLED=false

# 2. Restart engine
docker compose restart engine

# 3. Close all positions (if needed)
docker compose exec engine python3 -c "
from app.trading.alpaca_client import AlpacaTradingClient
client = AlpacaTradingClient(paper=True)
for pos in client.get_positions():
    client.close_position(pos['symbol'])
"
```

### Check System Health
```bash
# All services running?
docker compose ps

# Engine working?
docker compose logs engine --tail 20

# Database accessible?
docker compose exec db psql -U postgres -d trading -c "SELECT COUNT(*) FROM candles;"

# Dashboard loading?
curl -I http://127.0.0.1:8002/dashboard
```

---

## 📝 Pre-Market Checklist

### 30 Minutes Before Open (09:00 ET)

- [ ] Check all Docker services running
- [ ] Verify dashboard loads: http://127.0.0.1:8002/dashboard
- [ ] Confirm AUTO_TRADING_ENABLED=true (if trading)
- [ ] Check Alpaca paper account accessible
- [ ] Review risk parameters (MAX_POSITIONS, RISK_PER_TRADE_PCT)
- [ ] Clear browser cache (Cmd+Shift+R)
- [ ] Open engine logs: `docker compose logs engine -f`

### At Market Open (09:30 ET)

- [ ] Watch for data ingestion starting
- [ ] Monitor market state detection
- [ ] Check aggressive flow scores
- [ ] Verify dashboard updating
- [ ] Keep logs visible

### First Hour (09:30-10:30 ET)

- [ ] Monitor for first signal
- [ ] Verify trade execution (if signal triggers)
- [ ] Check position appears in dashboard
- [ ] Confirm Alpaca shows order
- [ ] Watch for stop-loss/take-profit

---

## 🎓 What to Expect

### First Day
- May not trade if no clear signals
- System is conservative (score >70)
- Prefers IMBALANCE states
- Needs strong aggressive flow

### Typical Day
- 0-3 signals across all 7 symbols
- 1-2 trades executed (with 1 max position)
- Mix of wins and losses
- 2:1 risk:reward means 50% win rate = profitable

### Best Days
- Clear trending market (IMBALANCE)
- High volume (aggressive flow >80)
- Multiple symbols triggering
- Clean entries and exits

---

## 📞 Quick Reference

### URLs
- **Dashboard**: http://127.0.0.1:8002/dashboard
- **Alpaca Paper**: https://app.alpaca.markets/paper/dashboard/overview
- **Alpaca API Keys**: https://app.alpaca.markets/paper/dashboard/overview

### Commands
```bash
# Restart everything
docker compose restart

# Watch logs
docker compose logs engine -f

# Check database
docker compose exec db psql -U postgres -d trading

# Clear Laravel cache
cd web && php artisan cache:clear
```

### Files
- **Trading config**: `/Users/steve/Projects/trading-strategies/.env`
- **Dashboard config**: `/Users/steve/Projects/trading-strategies/web/.env`
- **Risk settings**: Lines 37-44 in root .env
- **Strategy code**: `/services/engine/app/trading/auto_strategy.py`

---

## ✅ SYSTEM STATUS: READY FOR MARKET OPEN

**All systems operational. Waiting for:**
1. ⏰ Market open (09:30 ET)
2. 🔑 Trading API keys (for live execution)

**When market opens, system will:**
- ✅ Collect real-time data for all 7 symbols
- ✅ Analyze market state every 60 seconds
- ✅ Check for entry signals every 30 seconds
- ✅ Execute trades when conditions met (if API keys configured)
- ✅ Manage positions automatically with bracket orders

**Your automated trading platform is ready!** 🚀

---

**Last Updated**: 2025-10-01 15:14 (3 hours before market open)
