#!/bin/bash
cd /Users/steve/Projects/trading-strategies/web/..
docker compose exec -T engine python3 backtest.py --symbols 'AAPL,ABBV,ADBE,AMD,AMZN' --years '1.01' --initial-capital '10000' --risk-per-trade '1' --max-positions '3' --run-id 29
