#!/bin/bash
cd /Users/steve/Projects/trading-strategies/web/..
docker compose exec -T engine python3 backtest.py --symbols 'AAPL,ABBV,ADBE,AMD,AMZN' --years '0.21' --initial-capital '100000' --risk-per-trade '1' --max-positions '3' --min-aggression '70' --atr-stop '1.5' --atr-target '3' --run-id 35
