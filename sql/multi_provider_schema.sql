-- Multi-Provider Schema
-- Adds support for multiple data providers (Alpaca, IG, etc.)

-- Table: symbol_providers
-- Maps symbols to their data providers
CREATE TABLE IF NOT EXISTS symbol_providers (
    symbol VARCHAR(20) PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,  -- 'alpaca', 'ig', etc.
    market VARCHAR(10) NOT NULL,    -- 'NYSE', 'NASDAQ', 'LSE', 'DAX', etc.
    level INT NOT NULL DEFAULT 1,   -- Data level: 1 or 2
    epic VARCHAR(50),               -- IG-specific market identifier
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_symbol_providers_provider ON symbol_providers(provider);
CREATE INDEX IF NOT EXISTS idx_symbol_providers_market ON symbol_providers(market);
CREATE INDEX IF NOT EXISTS idx_symbol_providers_active ON symbol_providers(active);

-- Table: order_book
-- Stores Level 2 order book data
CREATE TABLE IF NOT EXISTS order_book (
    time TIMESTAMPTZ NOT NULL,
    symbol_id INT NOT NULL REFERENCES symbols(id),
    side VARCHAR(4) NOT NULL,       -- 'BID' or 'ASK'
    price DECIMAL(18, 8) NOT NULL,
    size DECIMAL(18, 8) NOT NULL,
    level INT NOT NULL,             -- Order book level (1-10)
    PRIMARY KEY (time, symbol_id, side, level)
);

-- Convert to hypertable if not already
SELECT create_hypertable('order_book', 'time', if_not_exists => TRUE);

-- Add compression policy
ALTER TABLE order_book SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id,side'
);

SELECT add_compression_policy('order_book', INTERVAL '1 day', if_not_exists => TRUE);

-- Seed data: US stocks (Alpaca)
INSERT INTO symbol_providers (symbol, provider, market, level, epic) VALUES
    ('AAPL', 'alpaca', 'NASDAQ', 1, NULL),
    ('MSFT', 'alpaca', 'NASDAQ', 1, NULL),
    ('GOOGL', 'alpaca', 'NASDAQ', 1, NULL),
    ('AMZN', 'alpaca', 'NASDAQ', 1, NULL),
    ('NVDA', 'alpaca', 'NASDAQ', 1, NULL),
    ('META', 'alpaca', 'NASDAQ', 1, NULL),
    ('TSLA', 'alpaca', 'NASDAQ', 1, NULL),
    ('AMD', 'alpaca', 'NASDAQ', 1, NULL),
    ('NFLX', 'alpaca', 'NASDAQ', 1, NULL),
    ('INTC', 'alpaca', 'NASDAQ', 1, NULL),
    ('CSCO', 'alpaca', 'NASDAQ', 1, NULL),
    ('ORCL', 'alpaca', 'NYSE', 1, NULL),
    ('CRM', 'alpaca', 'NYSE', 1, NULL),
    ('ADBE', 'alpaca', 'NASDAQ', 1, NULL),
    ('AVGO', 'alpaca', 'NASDAQ', 1, NULL),
    ('JPM', 'alpaca', 'NYSE', 1, NULL),
    ('BAC', 'alpaca', 'NYSE', 1, NULL),
    ('WFC', 'alpaca', 'NYSE', 1, NULL),
    ('GS', 'alpaca', 'NYSE', 1, NULL),
    ('MS', 'alpaca', 'NYSE', 1, NULL),
    ('JNJ', 'alpaca', 'NYSE', 1, NULL),
    ('UNH', 'alpaca', 'NYSE', 1, NULL),
    ('PFE', 'alpaca', 'NYSE', 1, NULL),
    ('ABBV', 'alpaca', 'NYSE', 1, NULL),
    ('MRK', 'alpaca', 'NYSE', 1, NULL),
    ('XOM', 'alpaca', 'NYSE', 1, NULL),
    ('CVX', 'alpaca', 'NYSE', 1, NULL),
    ('SPY', 'alpaca', 'NYSE', 1, NULL),
    ('QQQ', 'alpaca', 'NASDAQ', 1, NULL),
    ('DIA', 'alpaca', 'NYSE', 1, NULL)
ON CONFLICT (symbol) DO NOTHING;

-- Seed data: LSE stocks (IG Markets - Level 2)
INSERT INTO symbol_providers (symbol, provider, market, level, epic) VALUES
    ('VOD.L', 'ig', 'LSE', 2, 'IX.D.VOD.DAILY.IP'),
    ('BP.L', 'ig', 'LSE', 2, 'IX.D.BP.DAILY.IP'),
    ('HSBA.L', 'ig', 'LSE', 2, 'IX.D.HSBA.DAILY.IP'),
    ('LLOY.L', 'ig', 'LSE', 2, 'IX.D.LLOY.DAILY.IP'),
    ('BARC.L', 'ig', 'LSE', 2, 'IX.D.BARC.DAILY.IP'),
    ('GSK.L', 'ig', 'LSE', 2, 'IX.D.GSK.DAILY.IP'),
    ('AZN.L', 'ig', 'LSE', 2, 'IX.D.AZN.DAILY.IP'),
    ('RIO.L', 'ig', 'LSE', 2, 'IX.D.RIO.DAILY.IP')
ON CONFLICT (symbol) DO NOTHING;

-- Seed data: Indices (IG Markets)
INSERT INTO symbol_providers (symbol, provider, market, level, epic) VALUES
    ('^FTSE', 'ig', 'LSE', 1, 'IX.D.FTSE.DAILY.IP'),
    ('^GDAXI', 'ig', 'DAX', 1, 'IX.D.DAX.DAILY.IP'),
    ('^FCHI', 'ig', 'CAC', 1, 'IX.D.CAC.DAILY.IP')
ON CONFLICT (symbol) DO NOTHING;

-- Seed data: Forex (IG Markets)
INSERT INTO symbol_providers (symbol, provider, market, level, epic) VALUES
    ('GBPUSD', 'ig', 'FOREX', 1, 'CS.D.GBPUSD.TODAY.IP'),
    ('EURUSD', 'ig', 'FOREX', 1, 'CS.D.EURUSD.TODAY.IP'),
    ('EURGBP', 'ig', 'FOREX', 1, 'CS.D.EURGBP.TODAY.IP')
ON CONFLICT (symbol) DO NOTHING;

-- Add LSE symbols to symbols table if they don't exist
INSERT INTO symbols (symbol, name) VALUES
    ('VOD.L', 'Vodafone Group'),
    ('BP.L', 'BP plc'),
    ('HSBA.L', 'HSBC Holdings'),
    ('LLOY.L', 'Lloyds Banking Group'),
    ('BARC.L', 'Barclays'),
    ('GSK.L', 'GSK plc'),
    ('AZN.L', 'AstraZeneca'),
    ('RIO.L', 'Rio Tinto'),
    ('^FTSE', 'FTSE 100 Index'),
    ('^GDAXI', 'DAX Index'),
    ('^FCHI', 'CAC 40 Index'),
    ('GBPUSD', 'GBP/USD'),
    ('EURUSD', 'EUR/USD'),
    ('EURGBP', 'EUR/GBP')
ON CONFLICT (symbol) DO NOTHING;

-- Create view for easy querying
CREATE OR REPLACE VIEW v_symbol_routing AS
SELECT 
    s.id as symbol_id,
    s.symbol,
    s.name,
    sp.provider,
    sp.market,
    sp.level,
    sp.epic,
    sp.active,
    CASE 
        WHEN sp.level = 2 THEN 'Level 1 + Level 2 (Order Book)'
        ELSE 'Level 1 Only'
    END as data_level_description
FROM symbols s
LEFT JOIN symbol_providers sp ON s.symbol = sp.symbol
ORDER BY sp.market, s.symbol;

-- Grant permissions
GRANT SELECT ON v_symbol_routing TO PUBLIC;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Multi-provider schema created successfully!';
    RAISE NOTICE '📊 Configured % symbols', (SELECT COUNT(*) FROM symbol_providers);
    RAISE NOTICE '🇺🇸 US stocks (Alpaca): %', (SELECT COUNT(*) FROM symbol_providers WHERE market IN ('NYSE', 'NASDAQ'));
    RAISE NOTICE '🇬🇧 LSE stocks (IG): %', (SELECT COUNT(*) FROM symbol_providers WHERE market = 'LSE');
    RAISE NOTICE '📈 Indices (IG): %', (SELECT COUNT(*) FROM symbol_providers WHERE market IN ('LSE', 'DAX', 'CAC') AND symbol LIKE '^%');
    RAISE NOTICE '💱 Forex (IG): %', (SELECT COUNT(*) FROM symbol_providers WHERE market = 'FOREX');
END $$;
