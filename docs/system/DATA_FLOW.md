# Data Flow

This describes the runtime data flow for the stock system (current) and the binary options system (in-progress).

## Stock data flow (current)

### 1) Ingestion → DB (+ Redis)

- **Service**: `services/ingestion` (`python -m app.main`)
- **Providers** controlled by `PROVIDER` env:
  - `demo` (synthetic)
  - `alpaca_ws` (Alpaca WebSocket)
  - `alpha_vantage` (polling REST)
  - `ig` (polling Level 1)
  - `router` (multi-provider; starts workers based on credentials)

Writes:

- `ticks` (raw trades) via `handle_tick()`
- `candles` (1m OHLCV) via `handle_candle()`

Publishes:

- Redis channel `ticks:candles` with `{symbol,time,close}` updates

### 2) Profile calculator → DB

- **Service**: `services/profile_calculator` (`python -m app.main`)
- Loops every ~60s.

Reads:

- `ticks` when available, else falls back to `candles`

Writes:

- `volume_profile` (bucketed profile)
- `profile_metrics` (POC/VAH/VAL/LVNs/HVNs)
- `order_flow` (delta/CVD/buy-sell pressure)

### 3) Engine analytics + optional execution

- **Service**: `services/engine` (`python -m app.main`)
- Runs a tight loop (every ~1s).

Analytics:

- Market state detection: `app/detectors/market_state.py` (every ~5s)
- LVN alerts: `app/alerts/lvn_alerts.py` (every ~2s)
- Aggressive flow detection: `app/indicators/aggressive_flow.py` (every loop)

Signals:

- Loads active strategies from `strategies` table and emits `signals` rows.
- Publishes `signals` to Redis.

Auto execution (optional):

- If `AUTO_TRADING_ENABLED=true`, runs `app/trading/auto_strategy.py` every loop.
- Uses Alpaca bracket orders (market entry + TP + SL).

### 4) Redis → Reverb → Browser

- **relay** bridges Redis pubsub into **Reverb**.
- Laravel dashboard subscribes and updates the chart/watchlist in real-time.

## Binary options / Polymarket flow (in-progress)

There are two parallel approaches in the repo right now:

- Ingestion provider in `services/ingestion/app/providers/polymarket_ws.py`
- Monitor script in `services/engine/app/utils/arbitrage_monitor.py`

Both are intended to:

- Subscribe to Polymarket CLOB WebSocket market stream
- Convert per-token updates into per-market YES/NO best bid/ask
- Compute `spread` and an `arbitrage_opportunity` flag
- Store those into a time-series table (planned: `binary_prices`)

See `docs/BINARY_OPTIONS_DESIGN.md` and `docs/POLYMARKET_API_RESEARCH.md` for the intended schema/flow.

## Timezones

All storage is UTC; display is converted to market timezone.

See `../TIMEZONE_STRATEGY.md`.
