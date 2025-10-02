-- Insert a sample strategy for MVP: price above SMA20 on AAPL
INSERT INTO strategies(name, definition, active)
VALUES (
  'AAPL SMA20 Breakout',
  '{"type": "price_above_sma", "period": 20, "symbol": "AAPL", "signal": "BUY"}',
  TRUE
)
ON CONFLICT DO NOTHING;
