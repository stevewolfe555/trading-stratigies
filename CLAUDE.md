# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Multi-asset automated trading platform with real-time data ingestion, strategy execution, and professional dashboard. Supports stocks (Alpaca, IG Markets) and binary options arbitrage (Polymarket).

**Stack**: Python services (ingestion, strategy engine) + Laravel/Livewire (dashboard) + TimescaleDB + Redis/Reverb WebSocket

## Development Commands

### Backend Services (Docker)
```bash
# Start all services (DB, Redis, Python services, Reverb)
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f                    # All services
docker compose logs ingestion -f          # Specific service
docker compose logs profile_calculator -f

# Restart a service after code changes
docker compose restart ingestion
docker compose restart engine

# Rebuild after dependency changes
docker compose build ingestion
docker compose up -d ingestion

# Stop all services
docker compose down
```

### Laravel Application (Runs Locally)
```bash
cd web

# Initial setup
composer install
npm install
php artisan migrate

# Development server
php artisan serve --host=127.0.0.1 --port=8002

# Frontend build
npm run build        # Production build
npm run dev          # Development with hot reload

# Database operations
php artisan migrate                    # Run migrations
php artisan migrate:rollback          # Rollback last batch
php artisan migrate:fresh             # Drop all tables and re-migrate

# Clear caches
php artisan optimize:clear
php artisan view:clear
php artisan cache:clear

# Database access
php artisan tinker   # Laravel REPL
```

### Testing
```bash
# PHP tests (Laravel/PHPUnit)
cd web
vendor/bin/phpunit                    # All tests
vendor/bin/phpunit --filter testName  # Specific test

# Python tests (direct scripts)
cd services/ingestion
python test_ig_connection.py         # Test IG Markets API

cd services/engine
python test_volume_profile.py        # Test volume profile calculator
```

### Data Management
```bash
# Reset all trading data (keeps schema)
./scripts/reset-data.sh

# View database data
docker compose exec -T db psql -U postgres -d trading -c \
  "SELECT time AT TIME ZONE 'America/New_York' as time_et, symbol, close
   FROM candles ORDER BY time DESC LIMIT 10;"

# Check volume profile data
docker compose exec -T db psql -U postgres -d trading -c \
  "SELECT bucket, poc, vah, val FROM profile_metrics
   ORDER BY bucket DESC LIMIT 5;"
```

## Architecture Overview

### Multi-Asset Provider System

**Provider Router** (`services/ingestion/app/provider_router.py`) routes symbols to correct data source:
- US stocks (AAPL, MSFT) → Alpaca WebSocket
- LSE stocks (.L suffix) → IG Markets REST/Stream
- Indices (^FTSE) → IG Markets
- Forex (GBPUSD) → IG Markets
- Binary options (PRES2024-TRUMP) → Polymarket CLOB WebSocket

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ INGESTION SERVICE (Python)                                  │
│ - Multi-provider routing                                    │
│ - Real-time WebSocket connections                           │
│ - Candle aggregation (1-min)                                │
│ - Redis pub/sub for live updates                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ TIMESCALEDB (PostgreSQL + Time-Series Extension)            │
│ - Hypertables: candles, ticks, binary_prices                │
│ - Compression policies (1 day retention)                    │
│ - Regular tables: symbols, strategies, positions            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────┬──────────────────────────────────┐
│ STRATEGY ENGINE (Python) │ PROFILE CALCULATOR (Python)      │
│ - Auction Market Theory  │ - Volume Profile (POC/VAH/VAL)   │
│ - Binary arbitrage       │ - Order Flow (CVD)               │
│ - Auto-trading (Alpaca)  │ - Market State detection         │
│ - Risk management        │ - Runs every 60s                 │
└──────────────────────────┴──────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LARAVEL DASHBOARD (PHP - Runs Locally)                      │
│ - Livewire components (Watchlist, StockDetail, Backtesting) │
│ - Service layer (MarketDataService, BacktestService)        │
│ - WebSocket broadcasting (Reverb)                           │
│ - TradingView Lightweight Charts                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Patterns

**1. Service Layer Pattern** (`web/app/Services/`)
- `MarketDataService` - Fetches candles, signals, volume profiles from DB
- `BacktestService` - Orchestrates backtest calculations
- `TradingMetricsService` - Computes win rate, profit factor, Sharpe ratio
- `AccountService` - Manages account state and positions

**2. Provider Abstraction**
- Base interface: `BaseProvider` with `connect()`, `fetch_intraday()`, `handle_tick()`
- Implementations: `AlpacaWSProvider`, `IGProvider`, `PolymarketWebSocketProvider`
- Registration: `ProviderRouter` maintains dict of symbol → provider

**3. Real-Time Updates**
- Python services publish to Redis (`r.publish("ticks:candles", ...)`)
- Relay service bridges Redis → Reverb WebSocket
- Livewire components auto-refresh on broadcast events

## Database Schema (TimescaleDB)

### Hypertables (Time-Series Optimized)
```sql
-- OHLCV data (partitioned by time, compressed after 7 days)
candles(time, symbol_id, open, high, low, close, volume)

-- Raw trades (compressed after 1 day)
ticks(time, symbol_id, price, volume, side)

-- Binary option prices with precomputed arbitrage flags
binary_prices(timestamp, symbol_id, yes_bid, yes_ask, no_bid, no_ask,
              spread, arbitrage_opportunity, estimated_profit_pct)

-- Volume profile metrics
volume_profile(bucket, symbol_id, price_level, volume)
profile_metrics(bucket, symbol_id, poc, vah, val, lvns)
```

### Regular Tables
```sql
-- Multi-asset symbols (stock, binary_option, forex, etc.)
symbols(id, symbol, name, exchange, market, asset_type)

-- Binary options markets
binary_markets(id, symbol_id, market_id, question, end_date,
               status, resolution)

-- Binary arbitrage positions
binary_positions(id, symbol_id, yes_qty, no_qty, yes_entry_price,
                 no_entry_price, status, profit_loss)

-- Strategy configurations (applies to both stocks and binary)
strategy_configs(id, symbol_id, strategy_name, enabled, parameters,
                 risk_per_trade_pct)
```

### Migration Pattern (TimescaleDB)
```php
// 1. Create standard table
Schema::create('candles', function (Blueprint $table) {
    $table->timestampTz('time');
    $table->foreignId('symbol_id')->constrained('symbols');
    $table->decimal('close', 10, 2);
    $table->primary(['time', 'symbol_id']);
});

// 2. Convert to hypertable
DB::statement("SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);");

// 3. Add time-series index
DB::statement("CREATE INDEX idx_candles_symbol_time ON candles(symbol_id, time DESC);");

// 4. Optional: Enable compression
DB::statement("ALTER TABLE candles SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol_id');");
DB::statement("SELECT add_compression_policy('candles', INTERVAL '7 days', if_not_exists => TRUE);");
```

## Binary Options Arbitrage (New Feature)

### Concept
Exploit price inefficiencies on Polymarket where YES + NO prices ≠ $1.00. Buy both sides when spread < $1.00 for guaranteed profit at resolution.

### Implementation Status
- ✅ Database schema (binary_markets, binary_positions, binary_prices)
- ✅ Models (BinaryMarket, BinaryPosition, BinaryPrice)
- ✅ WebSocket provider (PolymarketWebSocketProvider with py-clob-client)
- ✅ Provider router integration
- 🚧 Strategy engine (ArbitrageStrategy - in progress)
- 🚧 Dashboard UI (ArbitrageMonitor component)

### Speed Optimizations
- Precomputed `arbitrage_opportunity` boolean flag on binary_prices
- Partial index: `CREATE INDEX WHERE arbitrage_opportunity = true`
- Async parallel order execution: `asyncio.gather(place_yes_order(), place_no_order())`
- Target latency: <100ms from detection to filled orders

### Risk Management
```python
# Capital allocation for binary arbitrage
MAX_BINARY_EXPOSURE = 400  # £400 max (80% of £500 capital)
MAX_POSITION_SIZE = 100    # £100 per market
MAX_POSITIONS_PER_MARKET = 1  # Avoid overexposure to single event
MIN_PROFIT_PCT = 0.015     # 1.5% minimum after fees
```

## Timezone Handling

**Critical**: All timestamps stored in UTC, displayed in market timezone.

```php
// Storage (always UTC)
DB::table('candles')->insert([
    'time' => now()->utc()  // Stored as UTC
]);

// Display (convert to ET for US stocks)
$candle->time->timezone('America/New_York')->format('Y-m-d H:i:s')

// TimescaleDB query
SELECT time AT TIME ZONE 'America/New_York' as time_et FROM candles;
```

See `docs/TIMEZONE_STRATEGY.md` for full details.

## Common Development Tasks

### Adding a New Data Provider
1. Create provider class in `services/ingestion/app/providers/`
2. Extend `BaseProvider` with `connect()` and `handle_tick()` methods
3. Add routing logic to `ProviderRouter.get_provider_for_symbol()`
4. Add credentials to `.env` file
5. Test with `docker compose restart ingestion`

### Creating a New Strategy
1. Create strategy class in `services/engine/app/strategies/`
2. Implement `check_opportunity()` and `execute()` methods
3. Add configuration to `strategy_configs` table
4. Register in `services/engine/app/main.py` execution loop
5. Add UI toggle in `web/app/Livewire/StrategyManager.php`

### Adding TimescaleDB Table
1. Create migration: `php artisan make:migration create_table_name`
2. In migration `up()`:
   - Create table with timestampTz column
   - Call `create_hypertable('table_name', 'time_column')`
   - Add indexes
3. Run: `php artisan migrate`
4. Add Eloquent model if needed

### Debugging WebSocket Issues
```bash
# Check Reverb server status
docker compose logs reverb -f

# Check Redis pub/sub
docker compose exec redis redis-cli
> SUBSCRIBE ticks:candles
> MONITOR  # Watch all Redis commands

# Check browser connection
# Open browser console → Network → WS tab → Check messages
```

## Important Files & Locations

### Entry Points
- `services/ingestion/app/main.py` - Data ingestion orchestration
- `services/engine/app/main.py` - Strategy execution loop
- `services/profile_calculator/app/main.py` - Volume profile calculator
- `web/routes/web.php` - Laravel web routes
- `web/app/Livewire/` - Reactive UI components

### Configuration
- `.env` - Root environment (Python services, Docker)
- `web/.env` - Laravel environment (DB connection, Reverb, APIs)
- `services/*/app/config.py` - Python service configs (Pydantic)
- `docker-compose.yml` - Service orchestration

### Key Models
- `web/app/Models/Symbol.php` - Multi-asset symbols
- `web/app/Models/BinaryMarket.php` - Polymarket markets
- `web/app/Models/BinaryPosition.php` - Arbitrage positions
- `web/app/Models/BacktestRun.php` - Historical backtest results

### Documentation
- `docs/ARCHITECTURE.md` - System architecture diagrams
- `docs/TIMEZONE_STRATEGY.md` - Timezone handling guide
- `docs/BINARY_OPTIONS_DESIGN.md` - Binary arbitrage design doc
- `CURRENT_STATUS.md` - Feature status and capabilities

## Testing Guidelines

### PHP Tests (PHPUnit)
- Location: `web/tests/Feature/` and `web/tests/Unit/`
- Uses SQLite in-memory database for speed
- Run with: `vendor/bin/phpunit`
- Example: Test Livewire component responses, model relationships

### Python Tests
- Location: `services/*/test_*.py` (direct executable scripts)
- Pattern: Manual assertions with emoji output (✅ ❌ ⚠️)
- Run with: `python test_ig_connection.py`
- Example: Test API connections, volume profile calculations

### Integration Testing
- Start all services: `docker compose up -d`
- Run ingestion for 2 minutes: Monitor logs for data flow
- Check DB: Query candles table for new data
- Test dashboard: Load http://localhost:8002 and verify real-time updates

## Performance Considerations

### TimescaleDB Query Optimization
```sql
-- Fast: Use time_bucket for aggregation
SELECT time_bucket('5 minutes', time) AS bucket,
       LAST(close, time) as close
FROM candles
WHERE time > NOW() - INTERVAL '1 day'
GROUP BY bucket;

-- Slow: Avoid large date ranges without time_bucket
SELECT * FROM candles WHERE time > '2023-01-01';  -- DON'T DO THIS

-- Fast: Use symbol_id index
SELECT * FROM candles
WHERE symbol_id = 1 AND time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;
```

### WebSocket Broadcasting
- Non-blocking: Use `broadcast()` not `broadcastNow()`
- Batch updates: Don't broadcast every tick, aggregate to 1-second intervals
- Selective subscriptions: Only subscribe to needed channels

### Python Service Memory
- Use context managers for DB cursors: `with get_cursor() as cur:`
- Close WebSocket connections on shutdown
- Limit in-memory candle buffers (e.g., last 1000 candles per symbol)

## Notes for Future Development

- Laravel runs **locally** (not in Docker) for easier development
- Python services connect to DB at `db:5432` (Docker network)
- Laravel connects to DB at `127.0.0.1:5432` (host network)
- Redis port mapped to 6380 (avoid conflicts with local Redis)
- Reverb WebSocket on port 8080
- Frontend uses Vite for builds (not Laravel Mix)
- TimescaleDB migrations are **irreversible** (can't rollback hypertables easily)
- Binary options feature under active development (see BINARY_OPTIONS_DESIGN.md)
- All API keys in .env are development/demo credentials (not production)
