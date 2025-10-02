# Architecture

## Containers
```mermaid
flowchart TB
  DB[(TimescaleDB)]
  R[Redis]
  ING[Python Ingestion]
  ENG[Python Rule Engine]
  WEB[Laravel Web]

  ING --> DB
  ING --> R
  ENG --> DB
  ENG --> R
  WEB --> DB
  WEB --> R
```

## Notes
- Timescale hypertables for `candles` and `signals`.
- Providers are pluggable via simple class interface (`services/ingestion/app/providers/`).
- Rule engine consumes Redis streams or pub/sub (future), queries history from DB, emits signals.
- Laravel reads from DB and Redis for real-time dashboard.
