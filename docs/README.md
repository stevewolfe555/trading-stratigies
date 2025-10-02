# Docs

- See `SPEC.md` for the product roadmap and phases.
- See `ARCHITECTURE.md` for technical architecture and data flow.

## High-level architecture

```mermaid
flowchart LR
  subgraph Docker
    DB[(TimescaleDB/Postgres)]
    R[Redis]
    ING[Ingestion Service (Python)]
    ENG[Rule Engine (Python)]
    WEB[Laravel Web/API]
  end

  ING -->|write candles| DB
  ING -->|publish ticks/signals| R
  ENG -->|read streams| R
  ENG -->|query history| DB
  WEB -->|read signals/metrics| DB
  WEB -->|subscribe updates| R
```

## Data model (MVP)
- `symbols(id, symbol, name, exchange)`
- `candles(time, symbol_id, open, high, low, close, volume)` hypertable
- `strategies(id, name, definition)`
- `signals(time, strategy_id, symbol_id, type, details)` hypertable
