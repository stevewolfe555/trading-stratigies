# System Overview

## What this repo is

A multi-service trading platform with:

- Market data ingestion (multi-provider)
- Time-series storage in TimescaleDB
- Market analytics (volume profile, order flow, market state)
- Trading engine (signals + optional auto-execution)
- Web dashboard (Laravel + Livewire) with real-time updates

The system currently focuses on **stocks** (Alpaca paper trading + IG Market data support) and has an **in-progress** expansion into **binary options / Polymarket**.

## High-level architecture

### Services

- `services/ingestion` (Python)
- `services/profile_calculator` (Python)
- `services/engine` (Python)
- `web` (Laravel + Livewire)
- `db` (PostgreSQL + TimescaleDB)
- `redis` (pub/sub)
- `reverb` + `relay` (WebSocket broadcasting)

### Storage model

- All market data and analytics are stored in PostgreSQL/TimescaleDB.
- Redis is used as a low-latency broadcast channel for UI updates.

### Current strategy

- Auction Market Theory strategy implemented in `services/engine/app/strategies/auction_market_strategy.py`.
- Live trading uses the same strategy logic as backtesting.

## What works today

### Stocks

- Ingestion via Demo, Alpaca WS, Alpha Vantage REST, or IG (Level 1 ticks)
- Candles stored in `candles` hypertable
- Profile metrics and order flow computed by `profile_calculator`
- Market state + LVN alerts + aggressive flow computed by `engine`
- Optional automated trading via Alpaca bracket orders (`AUTO_TRADING_ENABLED=true`)

### Backtesting

- CLI backtester: `services/engine/backtest.py`
- On-the-fly calculation of profile/flow/state (not dependent on live DB artifacts)
- Results persisted in `backtest_*` tables

## What is in-progress

### Polymarket (Binary options)

- Ingestion provider exists: `services/ingestion/app/providers/polymarket_ws.py`
- Trading client + strategy code exists: `services/engine/app/trading/polymarket_client.py`, `services/engine/app/strategies/arbitrage_strategy.py`
- Monitoring script exists: `services/engine/app/utils/arbitrage_monitor.py`

The Polymarket DB schema described in `docs/BINARY_OPTIONS_DESIGN.md` is not yet present in `sql/`.

## Where the “truth” lives

- **Runtime entrypoints**: see `system/SERVICES.md`
- **Current capabilities**: `../CURRENT_STATUS.md`
- **Strategy logic**: `trading/AUCTION_MARKET_STRATEGY.md`
- **Tuning workflow**: `trading/TUNING_PLAYBOOK.md`
