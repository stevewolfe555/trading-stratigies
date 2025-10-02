# Trading Playbook Platform

**Automated trading system** with Auction Market Theory strategies, real-time execution, and professional-grade analytics.

![Platform Status](https://img.shields.io/badge/status-live%20trading-brightgreen)
![Automation](https://img.shields.io/badge/automation-active-success)
![Chart](https://img.shields.io/badge/chart-TradingView%20Lightweight-blue)
![Database](https://img.shields.io/badge/database-TimescaleDB-orange)
![Stocks](https://img.shields.io/badge/stocks-30%20monitored-blueviolet)

## 🎯 Features

### 🤖 Automated Trading
- ✅ **Live Execution** - Trades automatically on Alpaca paper account
- ✅ **Market State Detection** - BALANCE vs IMBALANCE identification
- ✅ **Aggressive Flow Analysis** - Institutional activity detection
- ✅ **ATR-Based Targets** - Volatility-adjusted stop-loss/take-profit
- ✅ **Risk Management** - 1% risk per trade, max 3 positions, daily limits
- ✅ **30 Stocks Monitored** - Mag 7 + Tech/Finance/Healthcare/Energy/ETFs

### 📊 Professional Dashboard
- ✅ **Multi-Stock Overview** - Monitor all 30 stocks simultaneously
- ✅ **Live P&L Tracking** - Real-time position monitoring with close buttons
- ✅ **Account Overview** - Portfolio value, buying power, daily P&L
- ✅ **Trade History** - Recent trades with entry reasons
- ✅ **Engine Activity Monitor** - Live strategy evaluation logs
- ✅ **Auto-Refresh** - Updates every 3 seconds

### 📈 Technical Analysis
- ✅ **TradingView Charts** - Professional candlestick visualization
- ✅ **Volume Profile** - POC, VAH, VAL, LVNs
- ✅ **Order Flow** - CVD, Buy/Sell Pressure
- ✅ **Real-Time Data** - WebSocket streaming via Reverb

## 🚀 Quick Start

### 1. Start Backend Services

```bash
# Start Docker services (DB, Redis, Python services)
docker compose up -d

# Check status
docker compose ps
```

### 2. Setup Laravel (Local)

```bash
cd web

# Install dependencies
composer install
npm install

# Run migrations
php artisan migrate

# Build frontend
npm run build

# Start dev server
php artisan serve --host=127.0.0.1 --port=8002
```

### 3. Open Dashboard

```bash
open http://127.0.0.1:8002/dashboard
```

You should see:
- Professional candlestick chart
- Real-time price updates
- Buy/Sell pressure indicators
- Volume profile overlays (after 60s)

## 📊 Architecture

```
┌─────────────────┐
│ Market Data     │ (Alpaca WS / Alpha Vantage / Demo)
└────────┬────────┘
         │ trades (UTC)
         ↓
┌─────────────────┐
│ Ingestion       │ (Python) - Stores ticks + aggregates to 1-min candles
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ TimescaleDB     │ - Hypertables: candles, ticks, signals
│ (PostgreSQL)    │ - Compression, retention policies
└────────┬────────┘
         │
         ├──→ Profile Calculator (Python) - Computes POC, VAH, VAL, LVNs
         │
         ├──→ Rule Engine (Python) - Evaluates strategies
         │
         └──→ Dashboard (Laravel) - Converts UTC → ET, renders chart
                    │
                    ↓
              ┌─────────────┐
              │ TradingView │ - Candlestick chart
              │   Chart     │ - Signal markers
              └─────────────┘
```

## 🗂️ Project Structure

```
trading-strategies/
├── services/
│   ├── ingestion/          # Market data ingestion (Python)
│   ├── engine/             # Strategy evaluation (Python)
│   └── profile_calculator/ # Volume profile computation (Python)
├── web/                    # Laravel application (local dev)
│   ├── app/Livewire/      # Dashboard components
│   ├── database/migrations/
│   └── resources/views/
├── sql/                    # Database initialization
├── docs/                   # Documentation
│   ├── TIMEZONE_STRATEGY.md
│   ├── SPEC.md
│   └── ARCHITECTURE.md
├── scripts/                # Utility scripts
│   └── reset-data.sh      # Clean database
├── docker-compose.yml      # Service orchestration
├── CURRENT_STATUS.md       # Platform status
└── README.md              # This file
```

## 🔧 Configuration

### Environment Variables (`.env`)

```bash
# Market Data Provider
PROVIDER=demo                    # Options: demo, alpaca_ws, alpha_vantage

# Alpaca (Free Paper Trading)
ALPACA_API_KEY=
ALPACA_SECRET_KEY=

# Alpha Vantage (Rate Limited)
ALPHA_VANTAGE_API_KEY=

# Database
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=trading

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Symbols
SYMBOLS=AAPL                     # Comma-separated
```

### Switch to Real Market Data

```bash
# 1. Get free Alpaca keys: https://alpaca.markets
# 2. Update .env:
PROVIDER=alpaca_ws
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here

# 3. Restart ingestion
docker compose restart ingestion

# 4. Wait 60-120 seconds for data
# 5. Refresh dashboard
```

## 📈 Data Providers

| Provider | Type | Cost | Rate Limit | Real-Time | Order Flow |
|----------|------|------|------------|-----------|------------|
| **Demo** | Synthetic | Free | None | ✅ | ✅ (simulated) |
| **Alpaca** | WebSocket | Free | None | ✅ | ⚠️ (estimated) |
| **Alpha Vantage** | REST | Free | 25/day | ❌ | ❌ |
| **Rithmic** | Native | $50-100/mo | None | ✅ | ✅ (true) |

## 🎨 Chart Features

### TradingView Lightweight Charts
- **Candlesticks**: Green (bullish) / Red (bearish)
- **Zoom**: Scroll wheel
- **Pan**: Click and drag
- **Crosshair**: Hover for OHLC values
- **Time Axis**: US Eastern Time (ET)
- **Price Axis**: USD

### Overlays
- **POC** (Point of Control) - Blue dashed line
- **VAH/VAL** (Value Area) - Blue dotted lines
- **LVNs** (Low Volume Nodes) - Red dotted lines
- **Signals** - Green ▲ (BUY) / Red ▼ (SELL)

### Indicators
- **Buy Pressure** - Green bar (% of aggressive buying)
- **Sell Pressure** - Red bar (% of aggressive selling)
- **CVD** - Cumulative Volume Delta

## 🕐 Timezone Handling

**Strategy**: Store in UTC, Display in Market Timezone

- **Storage**: All timestamps in UTC (`TIMESTAMPTZ`)
- **Display**: Converted to US Eastern Time (ET) for stocks
- **DST**: Automatic handling (EST ↔ EDT)
- **Consistency**: No timezone confusion

See [`docs/TIMEZONE_STRATEGY.md`](docs/TIMEZONE_STRATEGY.md) for details.

## 🧪 Testing

### Check Data

```bash
# View candles
docker compose exec -T db psql -U postgres -d trading -c \
  "SELECT time AT TIME ZONE 'America/New_York' as time_et, close 
   FROM candles ORDER BY time DESC LIMIT 5;"

# Check volume profile
docker compose exec -T db psql -U postgres -d trading -c \
  "SELECT bucket, poc, vah, val FROM profile_metrics 
   ORDER BY bucket DESC LIMIT 3;"
```

### Reset Data

```bash
# Clean all data (keeps schema)
./scripts/reset-data.sh

# Restart ingestion
docker compose restart ingestion
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs ingestion -f
docker compose logs profile_calculator -f
```

## 📚 Documentation

- **[CURRENT_STATUS.md](CURRENT_STATUS.md)** - Platform status and capabilities
- **[docs/TIMEZONE_STRATEGY.md](docs/TIMEZONE_STRATEGY.md)** - Timezone handling guide
- **[docs/SPEC.md](docs/SPEC.md)** - Original specification
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Feature tracking

## 🐛 Troubleshooting

### Chart is blank
```bash
# 1. Hard refresh browser
Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

# 2. Clear Laravel caches
cd web && php artisan view:clear && php artisan optimize:clear

# 3. Check data exists
docker compose exec -T db psql -U postgres -d trading -c "SELECT COUNT(*) FROM candles;"
```

### No volume profile overlays
```bash
# Wait 60 seconds for first calculation
docker compose logs profile_calculator --tail 20

# Should see: "Computed profile metrics for bucket..."
```

### Services not running
```bash
# Check status
docker compose ps

# Restart all
docker compose restart

# Rebuild if needed
docker compose build && docker compose up -d
```

## 🚀 Next Steps

### Immediate (This Week)
1. **Backtesting Framework** - Validate strategy on historical data
2. **Parameter Optimization** - Find optimal thresholds
3. **Performance Metrics** - Win rate, Sharpe ratio, drawdown analysis
4. **Historical Data Import** - Load 2-7 years from Alpaca SIP

### Short-term (Next 2 Weeks)
1. **Walk-Forward Validation** - Prevent overfitting
2. **Monte Carlo Simulation** - Stress test the strategy
3. **Trade Journal** - Detailed performance tracking

### Long-term (Next 3 Months)
1. **Live Trading** - Transition to real money (small size)
2. **Additional Strategies** - Mean reversion, breakout models
3. **Portfolio Optimization** - Multi-stock position sizing
4. **Mobile App** - iOS/Android monitoring

📖 **See [BACKTESTING_PLAN.md](BACKTESTING_PLAN.md) for detailed implementation plan**

## 🤝 Contributing

This is a personal trading platform. Feel free to use the architecture as a reference for your own projects.

## 📝 License

Private project - All rights reserved

## 🙏 Acknowledgments

- **TradingView** - Lightweight Charts library
- **TimescaleDB** - Time-series database
- **Laravel** - Web framework
- **Chart Fanatics** - Auction Market playbook inspiration

---

**Built with ❤️ for systematic trading**
