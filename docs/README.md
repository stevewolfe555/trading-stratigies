# Documentation

This folder contains the canonical documentation for how the trading platform works, what it can do today, and how to improve/tune it.

## Start here

- `system/OVERVIEW.md` - What the system is, the main components, and how they fit together
- `system/DATA_FLOW.md` - End-to-end data flow (ingestion → storage → analysis → strategy → execution → UI)
- `system/SERVICES.md` - What runs in Docker vs locally, and service entrypoints

## Trading

- `trading/AUCTION_MARKET_STRATEGY.md` - Current stock strategy logic (shared between live + backtest)
- `trading/TUNING_PLAYBOOK.md` - How to tune the strategy and improve trading performance

## Reference

- `reference/DATABASE_SCHEMA.md` - Tables that exist today (and what’s planned for binary options)

## Existing project docs (kept as-is)

### Architecture / operations

- `ARCHITECTURE.md`
- `TIMEZONE_STRATEGY.md`

### Backtesting / research

- `BACKTEST_REFACTOR_PLAN.md`
- `../BACKTESTING_PLAN.md`

### Binary options (in-progress)

- `BINARY_OPTIONS_DESIGN.md`
- `POLYMARKET_API_RESEARCH.md`
- `PHASE4_EARLY_EXIT_STRATEGY.md`

### Misc / historical notes

- `PHASE3_TESTING_GUIDE.md`
- `TESTING_DB_INSERTION.md`

## Current scope notes

- The **stock trading system** (Alpaca + IG routing) is working end-to-end.
- The **binary options / Polymarket** work is in-progress: the schema exists as **Laravel migrations** under `web/database/migrations/` (tables like `binary_markets`, `binary_prices`, `binary_positions`), while the `sql/` folder is primarily used for DB bootstrap/reference SQL (including backtesting-related tables).
