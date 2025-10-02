-- Core schema
CREATE TABLE IF NOT EXISTS symbols (
  id SERIAL PRIMARY KEY,
  symbol TEXT UNIQUE NOT NULL,
  name TEXT,
  exchange TEXT
);

CREATE TABLE IF NOT EXISTS strategies (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  definition JSONB NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS candles (
  time TIMESTAMPTZ NOT NULL,
  symbol_id INT NOT NULL REFERENCES symbols(id),
  open DOUBLE PRECISION,
  high DOUBLE PRECISION,
  low DOUBLE PRECISION,
  close DOUBLE PRECISION,
  volume BIGINT,
  PRIMARY KEY (time, symbol_id)
);

SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol_id, time DESC);

CREATE TABLE IF NOT EXISTS signals (
  time TIMESTAMPTZ NOT NULL DEFAULT now(),
  strategy_id INT REFERENCES strategies(id),
  symbol_id INT REFERENCES symbols(id),
  type TEXT NOT NULL,
  details JSONB,
  PRIMARY KEY (time, strategy_id, symbol_id)
);

SELECT create_hypertable('signals', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol_id, time DESC);
