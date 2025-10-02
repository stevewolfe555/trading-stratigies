# Automated Trading Setup Guide

**Status**: ✅ Code Complete - Awaiting API Key Configuration

## 🎯 What We Built

### Automated Trading System
- ✅ Alpaca Trading Client (market/limit/bracket orders)
- ✅ Position Manager (risk controls, position sizing)
- ✅ Auto Trading Strategy (market state + aggressive flow)
- ✅ Safety limits and logging
- ✅ Integration with engine service

### Strategy Details

**Entry Conditions:**
1. Market state is IMBALANCE (up or down)
2. Aggressive flow score > 70
3. Flow direction matches market state

**Exit Conditions:**
- 2% stop loss
- 4% take profit (2:1 risk:reward)
- Bracket orders (automatic)

**Risk Management:**
- 1% risk per trade
- Max 1 position at a time
- 3% max daily loss limit
- Minimum $1,000 account balance

## 🔑 API Key Setup Required

### Current Issue
The Alpaca API keys in `.env` are for **data feed only**, not trading.

### Solution: Get Trading API Keys

1. **Log into Alpaca**: https://app.alpaca.markets
2. **Go to Paper Trading**: https://app.alpaca.markets/paper/dashboard/overview
3. **Generate API Keys**:
   - Click "View" or "Generate" API Key
   - You need keys with **trading permissions**
   - Copy both API Key and Secret Key

4. **Update `.env` file**:
   ```bash
   # Replace these with your PAPER TRADING keys
   ALPACA_API_KEY=your_paper_trading_key_here
   ALPACA_SECRET_KEY=your_paper_trading_secret_here
   ```

### Verify Keys Work

Test the connection:
```bash
docker compose exec engine python3 -c "
from app.trading.alpaca_client import AlpacaTradingClient
client = AlpacaTradingClient(paper=True)
account = client.get_account()
if account:
    print('✅ Connected!')
    print(f'Portfolio: \${float(account[\"portfolio_value\"]):,.2f}')
else:
    print('❌ Failed - check API keys')
"
```

## 🚀 How to Enable Auto-Trading

### Step 1: Update API Keys (see above)

### Step 2: Enable Auto-Trading

Edit `.env`:
```bash
# Change from false to true
AUTO_TRADING_ENABLED=true
```

### Step 3: Restart Engine

```bash
docker compose restart engine
```

### Step 4: Monitor Logs

```bash
# Watch for trading activity
docker compose logs engine -f

# You should see:
# 🤖 Starting engine service with AUTOMATED TRADING enabled
# 🤖 Running automated trading check...
# 🎯 ENTRY SIGNAL DETECTED: AAPL - ...
# 🚀 EXECUTING TRADE: BUY 10 AAPL @ $254.50
# ✅ Trade executed successfully!
```

## 📊 Strategy Performance Monitoring

### Check Account Status

```bash
docker compose exec engine python3 -c "
from app.trading.alpaca_client import AlpacaTradingClient
from app.trading.position_manager import PositionManager
import psycopg2
import os

conn = psycopg2.connect(
    host='db', port=5432, user='postgres',
    password='postgres', dbname='trading'
)

client = AlpacaTradingClient(paper=True)
pm = PositionManager(conn, client)
summary = pm.get_account_summary()

print(f'Portfolio Value: \${summary[\"portfolio_value\"]:,.2f}')
print(f'Buying Power: \${summary[\"buying_power\"]:,.2f}')
print(f'Open Positions: {summary[\"num_positions\"]}')

for pos in summary['positions']:
    pnl = pos['unrealized_plpc']
    print(f'  {pos[\"symbol\"]}: {pos[\"qty\"]} shares @ \${pos[\"avg_entry_price\"]:.2f} ({pnl:+.2f}%)')
"
```

### View Trade History

Check the `signals` table in database:
```sql
SELECT time, type, details 
FROM signals 
WHERE type IN ('BUY', 'SELL')
ORDER BY time DESC 
LIMIT 10;
```

## ⚙️ Strategy Configuration

Edit `/services/engine/app/trading/auto_strategy.py`:

```python
# Strategy parameters (lines 27-30)
self.min_aggression_score = 70  # Lower = more trades
self.stop_loss_pct = 2.0  # Tighter = less risk
self.take_profit_pct = 4.0  # Higher = bigger wins
```

Edit `/services/engine/app/trading/position_manager.py`:

```python
# Risk parameters (lines 24-27)
self.max_positions = 1  # Increase for multiple positions
self.risk_per_trade_pct = 1.0  # % of account per trade
self.max_daily_loss_pct = 3.0  # Daily loss limit
```

## 🛡️ Safety Features

### Built-in Protections
- ✅ Max 1 position at a time (configurable)
- ✅ 1% risk per trade
- ✅ 3% daily loss limit
- ✅ Minimum account balance check
- ✅ Account blocked check
- ✅ Bracket orders (auto stop-loss/take-profit)
- ✅ All trades logged to database

### Emergency Stop

To immediately stop auto-trading:

1. **Disable in .env**:
   ```bash
   AUTO_TRADING_ENABLED=false
   ```

2. **Restart engine**:
   ```bash
   docker compose restart engine
   ```

3. **Close all positions** (if needed):
   ```bash
   docker compose exec engine python3 -c "
   from app.trading.alpaca_client import AlpacaTradingClient
   client = AlpacaTradingClient(paper=True)
   
   positions = client.get_positions()
   for pos in positions:
       print(f'Closing {pos[\"symbol\"]}...')
       client.close_position(pos['symbol'])
   "
   ```

## 📈 Expected Behavior

### When Market is CLOSED
- Strategy will evaluate but not trade
- Logs will show: "Market state: BALANCE" or similar
- No trades executed

### When Market is OPEN (09:30-16:00 ET)
- Strategy checks every 30 seconds
- If conditions met:
  1. Logs: "🎯 ENTRY SIGNAL DETECTED"
  2. Calculates position size
  3. Places bracket order
  4. Logs: "✅ Trade executed successfully!"

### After Entry
- Alpaca automatically manages stop-loss and take-profit
- Position will close when either level is hit
- Strategy can enter new trade after position closes

## 🧪 Testing Recommendations

### Phase 1: Observation (1-2 days)
- Enable auto-trading
- Let it run with 1% risk
- Monitor logs and dashboard
- Check Alpaca paper account

### Phase 2: Tuning (3-5 days)
- Adjust aggression score threshold
- Tune stop-loss/take-profit levels
- Test with different symbols

### Phase 3: Validation (1-2 weeks)
- Track win rate
- Calculate profit factor
- Measure max drawdown
- Compare to manual trading

## 📝 Next Steps

1. **Get Trading API Keys** from Alpaca paper account
2. **Update `.env`** with new keys
3. **Test connection** with verification script
4. **Enable auto-trading** (`AUTO_TRADING_ENABLED=true`)
5. **Monitor for 24 hours** before leaving unattended

## ⚠️ Important Notes

- This is **PAPER TRADING** only (no real money)
- Strategy is **conservative** (1% risk, 1 position max)
- Requires **market hours** (09:30-16:00 ET) for best results
- **Monitor daily** for first week
- **Backtest results** don't guarantee future performance

## 🎓 Understanding the Strategy

**Why This Works:**
1. **Market State** filters for trending conditions (IMBALANCE)
2. **Aggressive Flow** confirms institutional activity
3. **Bracket Orders** ensure disciplined exits
4. **Position Sizing** limits risk per trade

**When It Struggles:**
- Choppy/ranging markets (filtered by BALANCE state)
- Low volume periods (filtered by aggression score)
- Gap ups/downs (bracket orders help)

**Ideal Conditions:**
- New York session (09:30-16:00 ET)
- Clear trend (IMBALANCE state)
- High volume (aggression score > 70)
- Liquid stocks (AAPL, SPY, QQQ, etc.)

---

**Your automated trading system is ready! Just need the correct API keys to activate it.** 🚀
