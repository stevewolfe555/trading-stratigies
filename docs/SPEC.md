# Trading Playbook Platform – Specification (Condensed)

## Phases
- MVP: one live market feed, store to TimescaleDB, JSON/YAML rules, Laravel dashboard (auth, charts, rule builder), signal log, email/web notifications.
- Phase 2: multi-step rules (AND/OR), sentiment/news feeds, backtesting, editor and performance dashboard.
- Phase 3: ML models, graph analytics, external APIs, advanced alerting (webhooks/Slack/Telegram), scaling (Docker/K8s, Kafka/Redis Streams).

## Stack
- Python services for ingestion and rule engine.
- Laravel (TALL) for frontend + API.
- TimescaleDB/Postgres for time-series.
- Redis for caching/streams.
- Docker, GitHub Actions CI.

## Budget targets
- Market data $50–150/mo. News $50–200/mo. Hosting $20–50/mo. ≤ $200/mo for Phase 1–2.

## Deliverables (MVP)
- Real-time dashboard with one provider.
- Rule builder (basic conditions).
- Signals log + notifications.
