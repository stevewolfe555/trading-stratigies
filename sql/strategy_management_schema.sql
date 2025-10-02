-- Strategy Management Schema
-- Provides database-backed configuration for trading strategies

-- Table: strategy_configs
-- Stores configuration for each strategy per symbol
CREATE TABLE IF NOT EXISTS strategy_configs (
    id SERIAL PRIMARY KEY,
    symbol_id INT NOT NULL REFERENCES symbols(id),
    strategy_name VARCHAR(50) NOT NULL,  -- 'auction_market', 'mean_reversion', etc.
    enabled BOOLEAN DEFAULT true,
    
    -- Strategy-specific parameters (JSON for flexibility)
    parameters JSONB NOT NULL DEFAULT '{}',
    
    -- Risk management
    risk_per_trade_pct DECIMAL(5, 2) DEFAULT 1.0,
    max_positions INT DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol_id, strategy_name)
);

CREATE INDEX IF NOT EXISTS idx_strategy_configs_symbol ON strategy_configs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_strategy_configs_enabled ON strategy_configs(enabled);
CREATE INDEX IF NOT EXISTS idx_strategy_configs_strategy ON strategy_configs(strategy_name);

-- Table: strategy_parameters
-- Global strategy parameters (defaults)
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    
    -- Default parameters
    default_parameters JSONB NOT NULL DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default strategy: Auction Market
INSERT INTO strategy_parameters (strategy_name, description, default_parameters) VALUES
(
    'auction_market',
    'Auction Market Theory strategy with market state detection and aggressive flow analysis',
    jsonb_build_object(
        'min_aggression_score', 70,
        'atr_stop_multiplier', 1.5,
        'atr_target_multiplier', 3.0,
        'risk_per_trade_pct', 1.0,
        'max_positions', 3,
        'max_daily_loss_pct', 3.0
    )
)
ON CONFLICT (strategy_name) DO UPDATE
SET default_parameters = EXCLUDED.default_parameters,
    updated_at = NOW();

-- Enable Auction Market strategy for all current US symbols
INSERT INTO strategy_configs (symbol_id, strategy_name, enabled, parameters, risk_per_trade_pct, max_positions)
SELECT 
    s.id,
    'auction_market',
    true,
    jsonb_build_object(
        'min_aggression_score', 70,
        'atr_stop_multiplier', 1.5,
        'atr_target_multiplier', 3.0
    ),
    1.0,
    1
FROM symbols s
WHERE s.symbol IN (
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 
    'AMD', 'NFLX', 'INTC', 'CSCO', 'ORCL', 'CRM', 'ADBE', 'AVGO',
    'JPM', 'BAC', 'WFC', 'GS', 'MS',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK',
    'XOM', 'CVX',
    'SPY', 'QQQ', 'DIA'
)
ON CONFLICT (symbol_id, strategy_name) DO NOTHING;

-- Create view for easy querying
CREATE OR REPLACE VIEW v_strategy_configs AS
SELECT 
    sc.id,
    s.symbol,
    s.name as symbol_name,
    sc.strategy_name,
    sc.enabled,
    sc.parameters,
    sc.risk_per_trade_pct,
    sc.max_positions,
    sp.default_parameters,
    sc.updated_at
FROM strategy_configs sc
JOIN symbols s ON sc.symbol_id = s.id
LEFT JOIN strategy_parameters sp ON sc.strategy_name = sp.strategy_name
ORDER BY s.symbol, sc.strategy_name;

-- Function to update strategy config
CREATE OR REPLACE FUNCTION update_strategy_config(
    p_symbol VARCHAR(20),
    p_strategy_name VARCHAR(50),
    p_enabled BOOLEAN DEFAULT NULL,
    p_parameters JSONB DEFAULT NULL,
    p_risk_per_trade_pct DECIMAL DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE strategy_configs sc
    SET 
        enabled = COALESCE(p_enabled, sc.enabled),
        parameters = COALESCE(p_parameters, sc.parameters),
        risk_per_trade_pct = COALESCE(p_risk_per_trade_pct, sc.risk_per_trade_pct),
        updated_at = NOW()
    FROM symbols s
    WHERE sc.symbol_id = s.id
        AND s.symbol = p_symbol
        AND sc.strategy_name = p_strategy_name;
END;
$$ LANGUAGE plpgsql;

-- Function to get active strategies for a symbol
CREATE OR REPLACE FUNCTION get_active_strategies(p_symbol VARCHAR(20))
RETURNS TABLE (
    strategy_name VARCHAR(50),
    parameters JSONB,
    risk_per_trade_pct DECIMAL,
    max_positions INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sc.strategy_name,
        sc.parameters,
        sc.risk_per_trade_pct,
        sc.max_positions
    FROM strategy_configs sc
    JOIN symbols s ON sc.symbol_id = s.id
    WHERE s.symbol = p_symbol
        AND sc.enabled = true;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON strategy_configs TO PUBLIC;
GRANT SELECT ON strategy_parameters TO PUBLIC;
GRANT SELECT ON v_strategy_configs TO PUBLIC;
GRANT USAGE ON SEQUENCE strategy_configs_id_seq TO PUBLIC;
GRANT USAGE ON SEQUENCE strategy_parameters_id_seq TO PUBLIC;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Strategy management schema created successfully!';
    RAISE NOTICE '📊 Configured strategies: %', (SELECT COUNT(*) FROM strategy_configs);
    RAISE NOTICE '🎯 Enabled strategies: %', (SELECT COUNT(*) FROM strategy_configs WHERE enabled = true);
    RAISE NOTICE '📈 Symbols with strategies: %', (SELECT COUNT(DISTINCT symbol_id) FROM strategy_configs);
END $$;
