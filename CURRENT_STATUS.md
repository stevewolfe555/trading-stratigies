# Trading Playbook Platform - Current Status

**Last Updated**: 2025-10-02 22:30 (UTC+3)

## What's Working

### Data Ingestion
- Real-time WebSocket data from Alpaca (IEX feed)
- Multi-provider infrastructure (Alpaca + IG Markets ready)
- Provider router for intelligent symbol routing
- 1-minute candle aggregation
- Support for 44 symbols (30 US + 8 LSE + 3 indices + 3 forex)
- Automatic reconnection on disconnect
- Data stored in TimescaleDB with compression

### Market Analysis
- Volume Profile calculation (POC, VAH, VAL, LVNs)
- Order Flow tracking (CVD, buy/sell pressure, volume ratio)
- Market State detection (BALANCE vs IMBALANCE)
- Aggressive Flow indicators with momentum
- LVN proximity alerts
- Session-based analysis (market hours detection)

### Trading Engine
- Automated trading strategy (Auction Market Theory)
- Database-backed strategy configuration
- Per-symbol strategy enable/disable
- Dynamic parameter adjustment without restart
- Position management with Alpaca API
- ATR-based stop loss and take profit
- Risk management (configurable per symbol)
- Daily loss limits

### Dashboard (Laravel + Livewire)
- **Watchlist** - Real-time overview of 30 stocks
- **Stock Detail** - Individual stock analysis with charts
- **Strategies** - Management UI with toggle switches and sliders
- **Account** - Portfolio and trade tracking
- Live position tracking
- Trade history with details
- Market state indicators
- Professional navigation across all pages

### Code Quality
- Service-oriented architecture
- Clean separation of concerns (MarketDataService, TradingMetricsService, AccountService)
- Refactored from 608-line monolith to 4 focused services
- Testable, maintainable codebase
### ✅ Real-Time Features
- **WebSocket streaming** - Reverb broadcasts new candles
- **Buy/Sell pressure bars** - Live market sentiment
- **CVD indicator** - Cumulative volume delta
- **Auto-updating chart** - New candles append automatically

## 📊 Current Data Flow

```
Market Data (Alpaca/Demo)
  ↓ (stores in UTC)
TimescaleDB
  ├─→ Candles (OHLCV)
  ├─→ Ticks (raw trades)
  └─→ Signals (strategy outputs)
       ↓
Profile Calculator (every 60s)
  ├─→ Volume Profile (POC, VAH, VAL, LVNs)
  └─→ Order Flow (CVD, buy/sell pressure)
       ↓
Dashboard (converts UTC → ET)
  └─→ TradingView Chart
       └─→ Browser (real-time updates)
```

## 🗂️ Database Schema

### Core Tables
- **`symbols`** - Trading symbols (AAPL, etc.)
- **`candles`** - OHLCV bars (hypertable, UTC)
- **`ticks`** - Raw trades (hypertable, compressed after 1 day)
- **`signals`** - Trading signals (BUY/SELL)
- **`strategies`** - Strategy definitions

### Auction Market Tables
- **`volume_profile`** - Volume by price level
- **`profile_metrics`** - POC, VAH, VAL, LVNs per bucket
- **`order_flow`** - Delta, CVD, buy/sell pressure
- **`market_state`** - Balance vs Imbalance detection

## 🔧 Services Running

| Service | Status | Purpose |
|---------|--------|---------|
| **PostgreSQL (TimescaleDB)** | ✅ Running | Time-series database |
| **Redis** | ✅ Running | Pub/sub messaging |
| **Ingestion** | ✅ Running | Market data ingestion (Demo provider) |
| **Profile Calculator** | ✅ Running | Volume profile computation |
| **Reverb** | ✅ Running | WebSocket broadcasting |
| **Relay** | ✅ Running | Redis → Reverb bridge |
| **Laravel (local)** | ✅ Running | Web application (port 8002) |

## 📍 Current Configuration

**Provider**: Demo (synthetic data)
- Generates realistic 1-min candles
- No API key required
- Good for testing

**Timezone**: 
- Storage: UTC
- Display: US Eastern Time (ET)

**Symbols**: 30 stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AMD, NFLX, INTC, CSCO, ORCL, CRM, ADBE, AVGO, JPM, BAC, WFC, GS, MS, JNJ, UNH, PFE, ABBV, MRK, XOM, CVX, SPY, QQQ, DIA)

## 🎯 How to Use

### View Dashboard
```bash
open http://127.0.0.1:8002/dashboard
```

### Reset Data (Start Fresh)
```bash
./scripts/reset-data.sh
```

### Switch to Real Data (Alpaca)
```bash
# 1. Get free Alpaca keys: https://alpaca.markets
# 2. Update .env:
PROVIDER=alpaca_ws
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret

# 3. Restart ingestion
docker compose restart ingestion
```

### Check Logs
```bash
# Ingestion
docker compose logs ingestion -f

# Profile calculator
docker compose logs profile_calculator -f

# All services
docker compose logs -f
```

## 📚 Documentation

- **`docs/TIMEZONE_STRATEGY.md`** - Timezone handling guide
- **`docs/SPEC.md`** - Original specification
- **`docs/ARCHITECTURE.md`** - System architecture
- **`IMPLEMENTATION_STATUS.md`** - Feature tracking
- **`README.md`** - Getting started guide

## 🚀 Next Steps

### Immediate (This Week)
1. **Backtesting framework** - Test strategy on historical data
2. **Parameter optimization** - Find optimal aggression thresholds, ATR multipliers
3. **Performance metrics** - Win rate, profit factor, Sharpe ratio, max drawdown
4. **Historical data import** - Load 2-7 years from Alpaca SIP feed

### Short-term (Next 2 Weeks)
1. **Walk-forward optimization** - Validate parameters don't overfit
2. **Multi-timeframe analysis** - Test on different market conditions
3. **Monte Carlo simulation** - Stress test the strategy
4. **Trade journal** - Detailed performance tracking

### Long-term (Next 3 Months)
1. **Live trading transition** - Move from paper to real money (small size)
2. **Additional strategies** - Mean reversion, breakout models
3. **Portfolio optimization** - Optimal position sizing across multiple stocks
4. **Advanced risk management** - Correlation analysis, portfolio heat
5. **Mobile app** - iOS/Android monitoring

## 🐛 Known Issues

1. **Chart may be blank on first load** - Hard refresh (Cmd+Shift+R) fixes it
2. **Timeframe aggregation** - 5m/15m/30m/1h/1d work, but need more testing
3. **Volume profile overlays** - May not show if no data computed yet (wait 60s)

## 🔍 Troubleshooting

### Chart is blank
```bash
# 1. Check if data exists
docker compose exec -T db psql -U postgres -d trading -c "SELECT COUNT(*) FROM candles;"

# 2. Clear caches
cd web && php artisan view:clear && php artisan optimize:clear

# 3. Hard refresh browser (Cmd+Shift+R)
```

### No volume profile overlays
```bash
# 1. Check if profile calculator is running
docker compose ps profile_calculator

# 2. Check logs
docker compose logs profile_calculator --tail 50

# 3. Wait 60 seconds for first calculation
```

### Times are wrong
```bash
# 1. Verify UTC storage
docker compose exec -T db psql -U postgres -d trading -c \
  "SELECT time, time AT TIME ZONE 'America/New_York' as time_et FROM candles LIMIT 3;"

# 2. Should show UTC time and ET time (4-5 hours difference)
```

## 📊 Performance Metrics

**Current Load** (Demo provider):
- Candles: ~150 rows
- Storage: ~50 KB
- Latency: <100ms (trade → browser)
- CPU: <5%
- Memory: ~200 MB

**Expected Load** (Real data, 100 symbols):
- Candles: ~1M rows/month
- Storage: ~100 MB/month (compressed)
- Latency: <100ms
- CPU: 10-20%
- Memory: ~500 MB

## 🎓 Learning Resources

**Auction Market Theory:**
- [Chart Fanatics Playbook](https://www.chartfanatics.com/playbook/auction-market-playbook)
- Volume Profile basics
- Order Flow analysis

**TradingView Lightweight Charts:**
- [Official Docs](https://tradingview.github.io/lightweight-charts/)
- [Examples](https://tradingview.github.io/lightweight-charts/examples/)

**TimescaleDB:**
- [Time-series best practices](https://docs.timescale.com/timescaledb/latest/overview/core-concepts/)
- [Continuous aggregates](https://docs.timescale.com/timescaledb/latest/how-to-guides/continuous-aggregates/)

## 🤝 Contributing

This is a personal trading platform, but the architecture can serve as a reference for:
- Real-time trading dashboards
- Time-series data visualization
- Multi-provider data ingestion
- WebSocket streaming architecture

## 📝 Notes

- Laravel runs **locally** (not containerized) for easier development
- Backend services (DB, Redis, Python) run in Docker
- Chart library switched from Chart.js to TradingView Lightweight Charts for better financial visualization
- Timezone strategy documented and implemented consistently
- Ready for production use with real market data

## ✅ Summary

You now have a **professional-grade trading platform** with:
- ✅ Real-time candlestick charts
- ✅ Volume profile analysis
- ✅ Order flow tracking
- ✅ Signal visualization
- ✅ Proper timezone handling
- ✅ Scalable architecture
- ✅ Ready for live trading data

**The platform is ready to connect to Alpaca for real market data and start trading with the Auction Market playbook strategies!**
