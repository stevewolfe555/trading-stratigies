-- Backtesting Schema
-- Stores backtest runs, trades, and performance metrics

-- Backtest runs (each parameter combination test)
CREATE TABLE IF NOT EXISTS backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    strategy_name VARCHAR(100) NOT NULL,
    
    -- Date range
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    
    -- Symbols tested
    symbols TEXT[] NOT NULL,
    
    -- Strategy parameters (JSON for flexibility)
    parameters JSONB NOT NULL,
    
    -- Performance metrics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    
    -- P&L metrics
    total_pnl DECIMAL(15,2),
    total_pnl_pct DECIMAL(8,4),
    avg_win DECIMAL(15,2),
    avg_loss DECIMAL(15,2),
    largest_win DECIMAL(15,2),
    largest_loss DECIMAL(15,2),
    
    -- Risk metrics
    max_drawdown DECIMAL(8,4),
    max_drawdown_pct DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    profit_factor DECIMAL(8,4),
    
    -- Execution stats
    avg_trade_duration_minutes INTEGER,
    avg_bars_in_trade INTEGER,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- pending, running, completed, failed
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_runs_strategy ON backtest_runs(strategy_name);
CREATE INDEX idx_backtest_runs_status ON backtest_runs(status);
CREATE INDEX idx_backtest_runs_dates ON backtest_runs(start_date, end_date);
CREATE INDEX idx_backtest_runs_created ON backtest_runs(created_at DESC);

-- Backtest trades (individual trades from backtest)
CREATE TABLE IF NOT EXISTS backtest_trades (
    id BIGSERIAL PRIMARY KEY,
    backtest_run_id BIGINT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    
    -- Entry
    entry_time TIMESTAMPTZ NOT NULL,
    entry_price DECIMAL(15,4) NOT NULL,
    entry_reason TEXT,
    
    -- Exit
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(15,4),
    exit_reason TEXT,
    
    -- Position details
    direction VARCHAR(10) NOT NULL, -- LONG, SHORT
    quantity INTEGER NOT NULL,
    
    -- P&L
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(8,4),
    
    -- Risk management
    stop_loss DECIMAL(15,4),
    take_profit DECIMAL(15,4),
    atr_at_entry DECIMAL(15,4),
    
    -- Market context at entry
    market_state VARCHAR(50),
    aggressive_flow_score INTEGER,
    volume_ratio DECIMAL(8,4),
    cvd_momentum INTEGER,
    
    -- Trade metrics
    bars_in_trade INTEGER,
    duration_minutes INTEGER,
    mae DECIMAL(15,4), -- Maximum Adverse Excursion
    mfe DECIMAL(15,4), -- Maximum Favorable Excursion
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_trades_run ON backtest_trades(backtest_run_id);
CREATE INDEX idx_backtest_trades_symbol ON backtest_trades(symbol_id);
CREATE INDEX idx_backtest_trades_entry_time ON backtest_trades(entry_time);
CREATE INDEX idx_backtest_trades_pnl ON backtest_trades(pnl DESC);

-- Backtest equity curve (portfolio value over time)
CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    id BIGSERIAL PRIMARY KEY,
    backtest_run_id BIGINT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    
    time TIMESTAMPTZ NOT NULL,
    equity DECIMAL(15,2) NOT NULL,
    cash DECIMAL(15,2) NOT NULL,
    positions_value DECIMAL(15,2) NOT NULL,
    drawdown DECIMAL(15,2),
    drawdown_pct DECIMAL(8,4),
    
    open_positions INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_equity_run ON backtest_equity_curve(backtest_run_id);
CREATE INDEX idx_backtest_equity_time ON backtest_equity_curve(backtest_run_id, time);

-- Backtest daily stats (aggregated by day)
CREATE TABLE IF NOT EXISTS backtest_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    backtest_run_id BIGINT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    
    date DATE NOT NULL,
    
    -- Trades
    trades_count INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    
    -- P&L
    daily_pnl DECIMAL(15,2),
    daily_pnl_pct DECIMAL(8,4),
    cumulative_pnl DECIMAL(15,2),
    
    -- Equity
    starting_equity DECIMAL(15,2),
    ending_equity DECIMAL(15,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(backtest_run_id, date)
);

CREATE INDEX idx_backtest_daily_run ON backtest_daily_stats(backtest_run_id);
CREATE INDEX idx_backtest_daily_date ON backtest_daily_stats(date);

-- Parameter optimization results
CREATE TABLE IF NOT EXISTS backtest_optimization (
    id BIGSERIAL PRIMARY KEY,
    optimization_name VARCHAR(255) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    
    -- Date range
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    
    -- Parameter ranges tested
    parameter_ranges JSONB NOT NULL,
    
    -- Best result
    best_run_id BIGINT REFERENCES backtest_runs(id),
    best_sharpe_ratio DECIMAL(8,4),
    best_profit_factor DECIMAL(8,4),
    
    -- Optimization stats
    total_combinations INTEGER,
    completed_combinations INTEGER,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_optimization_strategy ON backtest_optimization(strategy_name);
CREATE INDEX idx_backtest_optimization_status ON backtest_optimization(status);

-- Comments
COMMENT ON TABLE backtest_runs IS 'Stores individual backtest runs with parameters and results';
COMMENT ON TABLE backtest_trades IS 'Individual trades generated during backtests';
COMMENT ON TABLE backtest_equity_curve IS 'Portfolio value over time during backtest';
COMMENT ON TABLE backtest_daily_stats IS 'Daily aggregated statistics for backtests';
COMMENT ON TABLE backtest_optimization IS 'Parameter optimization runs';

-- Grant permissions
GRANT ALL ON backtest_runs TO postgres;
GRANT ALL ON backtest_trades TO postgres;
GRANT ALL ON backtest_equity_curve TO postgres;
GRANT ALL ON backtest_daily_stats TO postgres;
GRANT ALL ON backtest_optimization TO postgres;

GRANT ALL ON SEQUENCE backtest_runs_id_seq TO postgres;
GRANT ALL ON SEQUENCE backtest_trades_id_seq TO postgres;
GRANT ALL ON SEQUENCE backtest_equity_curve_id_seq TO postgres;
GRANT ALL ON SEQUENCE backtest_daily_stats_id_seq TO postgres;
GRANT ALL ON SEQUENCE backtest_optimization_id_seq TO postgres;
