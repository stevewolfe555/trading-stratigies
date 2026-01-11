# Auction Market Strategy (Stocks)

This documents the current stock trading strategy and where to tune it.

## Source of truth

- Strategy logic: `services/engine/app/strategies/auction_market_strategy.py`
- Live runner: `services/engine/app/trading/auto_strategy.py`
- Backtest runner: `services/engine/app/backtest_engine.py` and `services/engine/backtest.py`

## Required inputs (from DB)

Live trading evaluates entries by querying:

- Latest `candles` close
- Latest `market_state` row
- Last 5 `order_flow` rows

`profile_calculator` is what populates `order_flow`.

## Entry logic (summary)

A trade is considered when:

- Market state is `IMBALANCE_UP` or `IMBALANCE_DOWN`
  - Optionally allow `BALANCE` trades if `allow_balance_trades=true` and aggression >= 80
- Aggression score >= `min_aggression_score`
- Flow direction matches market state
- ATR is available

The aggression score is derived from:

- CVD momentum
- buy/sell pressure thresholds
- pressure ratio

## Stops/targets

Stop loss and take profit are ATR-based:

- Stop: `atr_stop_multiplier * ATR`
- Target: `atr_target_multiplier * ATR`

Live execution uses Alpaca “bracket orders” (market entry + TP + SL).

## Configuration knobs

### DB-backed (per symbol)

Table: `strategy_configs`.

- `enabled` (master per-symbol on/off)
- `parameters` JSON supports:
  - `min_aggression_score`
  - `atr_stop_multiplier`
  - `atr_target_multiplier`
  - `allow_balance_trades`

### Env-backed (engine-wide)

Live position/risk gating is currently controlled by env vars in `PositionManager`:

- `MAX_POSITIONS`
- `RISK_PER_TRADE_PCT`
- `MAX_DAILY_LOSS_PCT`
- `MIN_ACCOUNT_BALANCE`

Note: this means “strategy params” are mostly DB-backed, but “risk caps” are env-backed.

## What to tune first

- `min_aggression_score`
- `atr_stop_multiplier`
- `atr_target_multiplier`
- `allow_balance_trades`

And separately (risk):

- `RISK_PER_TRADE_PCT`
- `MAX_POSITIONS`
- `MAX_DAILY_LOSS_PCT`

## Backtesting

Use `services/engine/backtest.py` to quantify changes before enabling live execution.

See `TUNING_PLAYBOOK.md`.
