# Services

This doc maps “what runs” to code entrypoints and key configuration.

## Docker compose services

Defined in `docker-compose.yml`.

- `db`
  - PostgreSQL + TimescaleDB
  - Initializes schemas from `sql/init/*.sql`

- `redis`
  - Pub/sub transport for real-time updates

- `ingestion`
  - **Code**: `services/ingestion`
  - **Entrypoint**: `python -m app.main`
  - **Key env**:
    - `PROVIDER` (`demo`, `alpaca_ws`, `alpha_vantage`, `ig`, `router`)
    - `SYMBOLS` (comma-separated)

- `profile_calculator`
  - **Code**: `services/profile_calculator`
  - **Entrypoint**: `python -m app.main`
  - Computes `volume_profile`, `profile_metrics`, `order_flow`

- `engine`
  - **Code**: `services/engine`
  - **Entrypoint**: `python -m app.main`
  - **Key env**:
    - `AUTO_TRADING_ENABLED` (`true`/`false`)

- `reverb`
  - Laravel Reverb WebSocket server

- `relay`
  - Redis → Reverb bridge (`php artisan relay:redis`)

- `web`
  - Laravel running in Docker in this compose file

## Manual/local scripts

- Backtesting CLI:
  - `services/engine/backtest.py`

## Key runtime configuration sources

- `.env` for Docker services
- Strategy config tables:
  - `strategy_configs` (per symbol)
  - `strategy_parameters` (defaults)
- Provider routing table:
  - `symbol_providers`
