-- Seed minimal references
INSERT INTO symbols(symbol, name, exchange)
VALUES ('AAPL', 'Apple Inc.', 'NASDAQ')
ON CONFLICT DO NOTHING;
