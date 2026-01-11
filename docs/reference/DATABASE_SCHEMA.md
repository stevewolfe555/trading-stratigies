# Database Schema Reference

This describes the tables that exist today.

In this repo, the **authoritative schema** for runtime tables is implemented as **Laravel migrations** under `web/database/migrations/` (including TimescaleDB hypertables/policies).
The `sql/` folder contains bootstrap/reference SQL (including backtesting-related tables) and is useful for understanding the data model, but it is not the only source of truth.

## Core tables (sql/init/01-schema.sql)

- `symbols`
- `strategies`
- `candles` (Timescale hypertable)
- `signals` (Timescale hypertable)

## Multi-provider (sql/multi_provider_schema.sql)

- `symbol_providers` (symbol → provider/market mapping)
- `order_book` (Timescale hypertable for L2 snapshots)
- View: `v_symbol_routing`

## Strategy management (sql/strategy_management_schema.sql)

- `strategy_configs` (per-symbol config)
- `strategy_parameters` (defaults)
- View: `v_strategy_configs`

## Backtesting (sql/backtesting_schema.sql)

- `backtest_runs`
- `backtest_trades`
- `backtest_equity_curve`
- `backtest_daily_stats`
- `backtest_optimization`

## Market analytics tables

These are referenced by services and may be created by other init scripts or migrations in this repo:

- `ticks` (raw trades)
- `volume_profile`
- `profile_metrics`
- `order_flow`
- `market_state`

If you don’t see them in `sql/`, check other init SQL files or the service code assumptions.

## Binary options tables (Polymarket)

Implemented via Laravel migrations in `web/database/migrations/` and described in `docs/BINARY_OPTIONS_DESIGN.md`:

- `binary_markets`
- `binary_prices` (hypertable)
- `binary_positions`
- `symbols.asset_type` (migration exists)
