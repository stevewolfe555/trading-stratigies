# Tuning Playbook

This is the recommended workflow to improve trading performance without fooling ourselves.

## Core loop

1. Define objective metrics (Sharpe, profit factor, max drawdown, trade count)
2. Make one change at a time (parameter or logic)
3. Backtest across enough history and multiple symbols
4. Validate out-of-sample (walk-forward / different regimes)
5. Paper trade with small risk
6. Promote to larger size only after stability

## Where parameters live

### Live trading knobs

- Per-symbol strategy params: `strategy_configs.parameters`
- Per-engine risk limits: env vars (`RISK_PER_TRADE_PCT`, `MAX_POSITIONS`, etc.)

### Backtest knobs

Backtest CLI flags in `services/engine/backtest.py`:

- `--min-aggression`
- `--atr-stop`
- `--atr-target`
- `--risk-per-trade`
- `--max-positions`
- `--max-daily-loss`
- `--allow-balance-trades`

## Suggested experiments

### Baseline

- Run a baseline backtest with the current defaults and record metrics.

### Grid search (manual at first)

Try a small parameter sweep:

- `min_aggression_score`: 60, 70, 80
- `atr_stop_multiplier`: 1.0, 1.5, 2.0
- `atr_target_multiplier`: 2.0, 3.0, 4.0
- `allow_balance_trades`: false/true

Keep risk constant while tuning entries/exits.

### Risk tuning (second)

Once entries/exits are stable:

- Adjust `RISK_PER_TRADE_PCT` and `MAX_POSITIONS` to control drawdown and diversification.

## What “better” means

Don’t optimize for a single metric. A typical acceptance set:

- Profit factor improves without collapsing trade count
- Sharpe improves without doubling drawdown
- Out-of-sample doesn’t degrade dramatically

## Promotion checklist (paper → live)

- Backtest is stable across multiple symbols
- No single-symbol dependency
- Drawdowns are acceptable at target risk
- Live run uses conservative limits initially

## Notes on current implementation

- The strategy logic is shared between live and backtest (`AuctionMarketStrategy`).
- Live execution requires the analytics tables (`market_state`, `order_flow`) to be populated.
- The backtest engine calculates state/flow/profile on-the-fly, so it can test historical ranges.
