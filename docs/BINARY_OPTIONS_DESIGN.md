# Binary Options Arbitrage - Design Document

**Version:** 1.0
**Date:** 2026-01-09
**Status:** Implementation Phase

---

## Executive Summary

This document outlines the design for adding binary options arbitrage trading capabilities to the existing multi-asset trading platform. The system will exploit market-making inefficiencies on Polymarket where YES + NO prices don't equal $1.00, executing paired positions for guaranteed profit at resolution.

**Key Goals:**
- Add binary options alongside existing stock trading (zero disruption)
- Achieve <100ms latency from price update to order execution
- Target £20+ profit over 2 weeks with £500 capital
- Maintain 100% architectural consistency with existing system

---

## 1. Architecture Overview

### 1.1 Multi-Asset Design Philosophy

The platform evolves from a **stock trading system** to a **multi-asset trading platform** supporting:

```
Current State:
- Stocks (NASDAQ, NYSE via Alpaca)
- LSE Stocks (via IG Markets)
- Indices & Forex (via IG Markets)

New State:
- Everything above +
- Binary Options (Polymarket)
- Future: Crypto, Commodities, etc.
```

### 1.2 System Architecture (Updated)

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRADING PLATFORM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INGESTION LAYER (Multi-Provider)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Alpaca     │  │      IG      │  │  Polymarket  │  [NEW]  │
│  │  WebSocket   │  │  REST/Stream │  │   CLOB WS    │         │
│  │   (Stocks)   │  │ (LSE/Forex)  │  │  (Binary)    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         ↓                  ↓                  ↓                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          Provider Router (Symbol → Provider)        │       │
│  │  - AAPL → Alpaca                                    │       │
│  │  - VOD.L → IG Markets                               │       │
│  │  - PRES2024-TRUMP → Polymarket          [NEW]      │       │
│  └─────────────────────────────────────────────────────┘       │
│         ↓                                                       │
│  ┌─────────────────────────────────────────────────────┐       │
│  │            TimescaleDB (Time-Series Data)           │       │
│  │  - candles (stocks)                                 │       │
│  │  - binary_prices (YES/NO prices)        [NEW]      │       │
│  │  - ticks (raw trades)                               │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STRATEGY LAYER (Multi-Asset)                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Auction    │  │   Auto       │  │  Arbitrage   │  [NEW]  │
│  │   Market     │  │  Trading     │  │  Strategy    │         │
│  │  (Stocks)    │  │  (Stocks)    │  │  (Binary)    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         ↓                  ↓                  ↓                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          Strategy Manager (DB-Backed Config)        │       │
│  │  - Enable/disable per symbol                        │       │
│  │  - Adjust parameters dynamically                    │       │
│  │  - Independent execution loops                      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EXECUTION LAYER (Multi-Provider)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │    Alpaca    │  │      IG      │  │  Polymarket  │  [NEW]  │
│  │   Trading    │  │   Trading    │  │   Trading    │         │
│  │    Client    │  │    Client    │  │    Client    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         ↓                  ↓                  ↓                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │           Position & Order Management               │       │
│  │  - Stock positions (bracket orders)                 │       │
│  │  - Binary positions (paired YES+NO)     [NEW]      │       │
│  │  - Unified risk management                          │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DASHBOARD (Multi-Asset Tabs)                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Stocks     │  │   Binary     │  │   Settings   │         │
│  │  Watchlist   │  │  Arbitrage   │  │   Strategy   │         │
│  │   + Chart    │  │   Monitor    │  │   Manager    │  [NEW]  │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema Design

### 2.1 Core Concept: Asset Type Extension

Add `asset_type` to symbols table to support multiple asset classes:

```sql
-- Extends existing symbols table
ALTER TABLE symbols ADD COLUMN asset_type VARCHAR(20) DEFAULT 'stock';

-- Possible values: 'stock', 'binary_option', 'crypto', 'forex', 'commodity'
-- Existing symbols auto-default to 'stock'
-- New Polymarket symbols will be 'binary_option'
```

**Examples:**
| symbol | name | exchange | asset_type |
|--------|------|----------|------------|
| AAPL | Apple Inc. | NASDAQ | stock |
| VOD.L | Vodafone | LSE | stock |
| PRES2024-TRUMP | Trump wins 2024? | POLYMARKET | binary_option |
| BTC-100K-Q1 | Bitcoin $100K Q1? | POLYMARKET | binary_option |

### 2.2 Binary Markets Table

Stores metadata about Polymarket binary option markets.

```sql
CREATE TABLE binary_markets (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    market_id VARCHAR(100) UNIQUE NOT NULL,  -- Polymarket's internal ID
    question TEXT NOT NULL,                  -- "Will Trump win 2024?"
    description TEXT,                        -- Full market description
    end_date TIMESTAMPTZ NOT NULL,           -- Resolution deadline
    category VARCHAR(50),                    -- Politics, Sports, Crypto, etc.
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, resolved, closed, cancelled
    resolution VARCHAR(10),                  -- yes, no, null (after resolution)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_binary_markets_symbol_id ON binary_markets(symbol_id);
CREATE INDEX idx_binary_markets_status ON binary_markets(status);
CREATE INDEX idx_binary_markets_end_date ON binary_markets(end_date);
CREATE INDEX idx_binary_markets_category ON binary_markets(category);
```

**Purpose:**
- Track active markets for monitoring
- Filter by category (e.g., only trade politics markets)
- Know when positions will resolve

### 2.3 Binary Prices Table (Hypertable - Speed Critical)

Real-time YES/NO prices with precomputed arbitrage flags for ultra-fast queries.

```sql
CREATE TABLE binary_prices (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol_id BIGINT NOT NULL,

    -- YES order book
    yes_bid NUMERIC(10, 6) NOT NULL,         -- Best bid for YES
    yes_ask NUMERIC(10, 6) NOT NULL,         -- Best ask for YES
    yes_mid NUMERIC(10, 6) NOT NULL,         -- (bid + ask) / 2
    yes_volume BIGINT DEFAULT 0,             -- Volume at best bid/ask

    -- NO order book
    no_bid NUMERIC(10, 6) NOT NULL,          -- Best bid for NO
    no_ask NUMERIC(10, 6) NOT NULL,          -- Best ask for NO
    no_mid NUMERIC(10, 6) NOT NULL,          -- (bid + ask) / 2
    no_volume BIGINT DEFAULT 0,              -- Volume at best bid/ask

    -- Precomputed metrics (SPEED OPTIMIZATION)
    spread NUMERIC(10, 6) NOT NULL,          -- yes_ask + no_ask (what we'd pay)
    arbitrage_opportunity BOOLEAN NOT NULL,  -- true if spread < threshold
    estimated_profit_pct NUMERIC(6, 4),      -- Expected profit % after fees

    PRIMARY KEY (timestamp, symbol_id)
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('binary_prices', 'timestamp');

-- Indexes for ultra-fast arbitrage queries
CREATE INDEX idx_binary_prices_symbol ON binary_prices(symbol_id, timestamp DESC);
CREATE INDEX idx_binary_prices_arb ON binary_prices(timestamp DESC)
    WHERE arbitrage_opportunity = true;  -- Partial index for speed

-- Compression policy (save disk space on old data)
SELECT add_compression_policy('binary_prices', INTERVAL '7 days');
```

**Speed Optimizations:**
1. **Hypertable:** TimescaleDB optimizes time-series queries
2. **Precomputed spread:** No calculation needed during queries
3. **Arbitrage flag:** Indexed for instant filtering
4. **Partial index:** Only indexes arbitrage opportunities (faster)

**Example Query (< 5ms):**
```sql
-- Find all current arbitrage opportunities
SELECT
    s.symbol,
    bm.question,
    bp.yes_ask,
    bp.no_ask,
    bp.spread,
    bp.estimated_profit_pct
FROM binary_prices bp
JOIN symbols s ON bp.symbol_id = s.id
JOIN binary_markets bm ON bm.symbol_id = s.id
WHERE bp.arbitrage_opportunity = true
    AND bm.status = 'active'
    AND bp.timestamp > NOW() - INTERVAL '10 seconds'
ORDER BY bp.estimated_profit_pct DESC
LIMIT 20;
```

### 2.4 Binary Positions Table

Tracks paired YES+NO positions from arbitrage execution.

```sql
CREATE TABLE binary_positions (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    market_id VARCHAR(100) NOT NULL,         -- Polymarket market ID

    -- Position details
    yes_qty NUMERIC(10, 4) NOT NULL,         -- Quantity of YES shares
    no_qty NUMERIC(10, 4) NOT NULL,          -- Quantity of NO shares
    yes_entry_price NUMERIC(10, 6) NOT NULL, -- Entry price for YES
    no_entry_price NUMERIC(10, 6) NOT NULL,  -- Entry price for NO
    entry_spread NUMERIC(10, 6) NOT NULL,    -- yes_price + no_price at entry

    -- Order tracking
    yes_order_id VARCHAR(100),               -- Polymarket order ID for YES
    no_order_id VARCHAR(100),                -- Polymarket order ID for NO

    -- Position status
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- open, resolved, closed, partial
    resolution VARCHAR(10),                  -- yes, no (after market resolves)

    -- P&L tracking
    profit_loss NUMERIC(10, 2),              -- Realized P&L
    profit_loss_pct NUMERIC(6, 4),           -- P&L as % of cost
    fees_paid NUMERIC(10, 2),                -- Total fees paid

    -- Timestamps
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,

    -- Metadata
    notes TEXT                               -- Any special notes
);

-- Indexes
CREATE INDEX idx_binary_positions_symbol_id ON binary_positions(symbol_id);
CREATE INDEX idx_binary_positions_status ON binary_positions(status);
CREATE INDEX idx_binary_positions_market_id ON binary_positions(market_id);
CREATE INDEX idx_binary_positions_opened_at ON binary_positions(opened_at DESC);
```

**Position Lifecycle:**
1. `status = 'open'` → Position active, waiting for resolution
2. `status = 'resolved'` → Market resolved, calculating P&L
3. `status = 'closed'` → P&L settled, position archived

### 2.5 Strategy Configuration (Reuse Existing)

Binary arbitrage strategy uses the same `strategy_configs` table as stock strategies:

```sql
-- Example configuration for arbitrage strategy
INSERT INTO strategy_configs (symbol_id, strategy_name, enabled, parameters, risk_per_trade_pct, max_positions)
VALUES (
    (SELECT id FROM symbols WHERE symbol = 'PRES2024-TRUMP'),
    'arbitrage',
    true,
    '{
        "spread_threshold": 0.98,
        "min_profit_pct": 0.015,
        "max_position_size": 100,
        "fee_rate": 0.02,
        "order_type": "market"
    }'::jsonb,
    5.0,   -- 5% of capital per trade
    1      -- Max 1 position per market
);
```

**Benefits:**
- Unified configuration system
- Enable/disable via existing UI
- Same parameter adjustment workflow

---

## 3. Data Flow & Speed Optimizations

### 3.1 Real-Time Price Ingestion (Target: <50ms)

```
Polymarket CLOB API (WebSocket)
    ↓ [~10ms network latency]
PolymarketWebSocketProvider.on_message()
    ↓ [~5ms parsing JSON]
Calculate spread & arbitrage flag
    ↓ [~2ms computation]
Symbol ID lookup (cached)
    ↓ [~1ms cache hit]
INSERT INTO binary_prices
    ↓ [~10ms database write]
Redis PUBLISH arbitrage_alert (non-blocking)
    ↓ [~2ms]
Dashboard WebSocket update
    ↓ [~20ms total latency]
User sees opportunity
```

**Total Latency: ~50ms from Polymarket to user screen**

### 3.2 Arbitrage Detection & Execution (Target: <100ms)

```
Arbitrage opportunity detected (precomputed flag)
    ↓ [~1ms query with partial index]
ArbitrageStrategy.check_arbitrage_opportunity()
    ↓ [~5ms fetch latest prices]
Risk checks (max exposure, limits)
    ↓ [~10ms database query]
Calculate position size
    ↓ [~1ms]
Place YES order (async)
    │ [~30ms API call]
    ├──→ PolymarketClient.place_order()
    │
Place NO order (async, parallel)
    │ [~30ms API call]
    └──→ PolymarketClient.place_order()

Wait for both fills (await asyncio.gather)
    ↓ [~50ms total for both]
Save position to database
    ↓ [~10ms]
Publish position update to Redis
    ↓ [~2ms]
Dashboard shows new position
```

**Total Execution Time: ~100ms from detection to filled orders**

### 3.3 Speed Optimization Techniques

| Technique | Benefit | Implementation |
|-----------|---------|----------------|
| WebSocket (not polling) | No polling delay, instant updates | PolymarketWebSocketProvider |
| Precomputed flags | 10x faster queries | `arbitrage_opportunity` column |
| Partial indexes | Only index relevant rows | `WHERE arbitrage_opportunity = true` |
| Symbol ID caching | Avoid repeated DB lookups | In-memory dict in provider |
| Async order placement | Parallel YES+NO execution | `asyncio.gather()` |
| TimescaleDB hypertables | Optimized time-series queries | `create_hypertable()` |
| Market orders | Guaranteed fills, no waiting | Order type: MARKET |
| Redis pub/sub | Non-blocking notifications | Don't wait for dashboard updates |

---

## 4. Provider Layer Design

### 4.1 PolymarketWebSocketProvider

**File:** `services/ingestion/app/providers/polymarket_ws.py`

**Responsibilities:**
- Connect to Polymarket CLOB WebSocket API
- Subscribe to order book updates for tracked markets
- Parse YES/NO bid/ask prices
- Calculate spread and arbitrage flags
- Insert into `binary_prices` table
- Publish alerts to Redis

**Key Features:**
- Symbol ID caching for speed
- Automatic reconnection on disconnect
- Error handling with exponential backoff
- Rate limit awareness
- Precompute all metrics before database insert

**WebSocket Message Format (estimated):**
```json
{
  "type": "orderbook_update",
  "market_id": "0x1234abcd...",
  "timestamp": "2026-01-09T10:30:45.123Z",
  "yes_book": {
    "bids": [[0.52, 1000], [0.51, 500]],
    "asks": [[0.53, 800], [0.54, 1200]]
  },
  "no_book": {
    "bids": [[0.44, 900], [0.43, 600]],
    "asks": [[0.45, 1100], [0.46, 700]]
  }
}
```

### 4.2 ProviderRouter Extension

Add routing logic for binary options:

```python
def get_provider_for_symbol(self, symbol: str) -> Optional[Any]:
    # Existing routing...

    # Polymarket binary options
    # Format: PRES2024-TRUMP, BTC-100K-Q1, etc.
    # Heuristic: Contains dash and > 6 chars (not forex like GBPUSD)
    if '-' in symbol and len(symbol) > 6:
        return self.providers.get('polymarket')

    # ... rest of existing routing
```

---

## 5. Strategy Layer Design

### 5.1 ArbitrageStrategy

**File:** `services/engine/app/strategies/arbitrage_strategy.py`

**Core Logic:**
```python
def check_arbitrage_opportunity(symbol):
    # 1. Get latest prices (optimized query)
    prices = db.query("""
        SELECT yes_ask, no_ask, spread, estimated_profit_pct
        FROM binary_prices
        WHERE symbol_id = %s
          AND arbitrage_opportunity = true
        ORDER BY timestamp DESC
        LIMIT 1
    """, symbol_id)

    # 2. Validate profit threshold
    if prices.estimated_profit_pct < min_profit_pct:
        return None

    # 3. Check risk limits
    if not check_risk_limits():
        return None

    # 4. Return opportunity
    return prices

def execute_arbitrage(symbol, yes_ask, no_ask):
    # 1. Calculate position size
    position_size = min(max_position_size, available_capital)
    yes_qty = position_size / yes_ask
    no_qty = position_size / no_ask

    # 2. Place orders in parallel (CRITICAL)
    yes_order, no_order = await asyncio.gather(
        client.place_order(symbol, 'YES', yes_ask, yes_qty),
        client.place_order(symbol, 'NO', no_ask, no_qty)
    )

    # 3. Save position
    save_position(symbol, yes_qty, no_qty, yes_ask, no_ask)

    # 4. Log success
    logger.success(f"Arbitrage: {symbol} | Spread: ${yes_ask + no_ask:.4f}")
```

**Parameters (Configurable):**
- `spread_threshold`: 0.98 (buy if spread < this)
- `min_profit_pct`: 0.015 (minimum 1.5% profit after fees)
- `max_position_size`: £100 per market
- `max_total_exposure`: £400 (80% of £500 capital)
- `fee_rate`: 0.02 (2% total fees - estimate)

### 5.2 Risk Management

**Position Limits:**
- Max 1 position per market (avoid overexposure to single event)
- Max £400 total exposure (keep £100 buffer for stocks)
- Max £100 per position (diversification)

**Capital Allocation:**
```
Total Capital: £500
├── Binary Options: £400 max (80%)
│   ├── Position 1: £100
│   ├── Position 2: £100
│   ├── Position 3: £100
│   └── Position 4: £100
└── Reserved: £100 (stocks + buffer)
```

**Safety Checks:**
```python
def check_risk_limits():
    # 1. Check total exposure
    total_exposure = get_total_binary_exposure()
    if total_exposure >= max_total_exposure:
        return False

    # 2. Check existing position for this market
    existing = get_position_for_market(market_id)
    if existing and existing.status == 'open':
        return False  # Already have position

    # 3. Check account balance
    account_balance = get_account_balance()
    if account_balance < min_balance:
        return False

    return True
```

---

## 6. Execution Layer Design

### 6.1 PolymarketTradingClient

**File:** `services/engine/app/trading/polymarket_client.py`

**Responsibilities:**
- Authenticate with Polymarket CLOB API
- Place market orders for YES/NO positions
- Monitor order fills
- Handle partial fills
- Manage API rate limits

**API Structure (estimated based on typical CLOB):**

```python
class PolymarketTradingClient:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://clob.polymarket.com"

    async def place_order(
        self,
        market_id: str,
        side: str,  # 'YES' or 'NO'
        price: Decimal,
        quantity: Decimal,
        order_type: str = 'MARKET'
    ) -> dict:
        """
        Place order on Polymarket.

        Returns:
            {
                'order_id': '0xabc123...',
                'status': 'filled',
                'filled_qty': 100.0,
                'filled_price': 0.53,
                'fees': 1.06
            }
        """
        # Sign request
        signature = self._sign_request(...)

        # Place order
        response = await self._post('/orders', {
            'market_id': market_id,
            'side': side,
            'price': str(price),
            'quantity': str(quantity),
            'type': order_type
        }, signature)

        return response

    async def get_order_status(self, order_id: str) -> dict:
        """Check if order is filled"""
        return await self._get(f'/orders/{order_id}')

    async def get_positions(self) -> list:
        """Get all open positions"""
        return await self._get('/positions')
```

### 6.2 Order Execution Strategy

**Market Orders (Speed Priority):**
- Use MARKET orders for guaranteed fills
- Accept slight price slippage for execution certainty
- Arbitrage profit margin covers small slippage

**Parallel Execution:**
```python
# Execute YES and NO simultaneously
async def execute_paired_orders(market_id, yes_price, no_price, qty):
    # Launch both orders at same time
    yes_order_task = client.place_order(market_id, 'YES', yes_price, qty)
    no_order_task = client.place_order(market_id, 'NO', no_price, qty)

    # Wait for both to complete
    yes_order, no_order = await asyncio.gather(
        yes_order_task,
        no_order_task
    )

    # Both filled in ~50ms total (not 100ms sequential)
    return yes_order, no_order
```

---

## 7. Dashboard Design

### 7.1 Navigation Structure

```
┌─────────────────────────────────────────┐
│  Trading Platform                       │
├─────────────────────────────────────────┤
│  [Stocks] [Binary Options] [Settings]   │  ← New tab
└─────────────────────────────────────────┘
```

### 7.2 Binary Options Tab - ArbitrageMonitor Component

**File:** `web/app/Livewire/ArbitrageMonitor.php`

**Sections:**

1. **Active Opportunities** (auto-refreshing every 2s)
   - Question
   - YES price + NO price
   - Spread
   - Estimated profit %
   - [Execute] button

2. **Open Positions**
   - Market question
   - Entry spread
   - Locked profit
   - Resolution date
   - Days until resolution

3. **Performance Metrics**
   - Total positions: 12
   - Total profit: £18.40 (3.68%)
   - Win rate: 100% (arbitrage guarantee)
   - Average hold time: 8.3 days

4. **Recent History**
   - Closed positions
   - Actual profit vs expected
   - Resolution outcome

**Real-time Updates:**
- WebSocket connection via Reverb
- Live price updates
- New opportunity alerts
- Position resolution notifications

---

## 8. Implementation Phases

### Phase 1: Foundation (Days 1-2)
**Goal:** Database schema & migrations

- [ ] Create migration for `asset_type` field
- [ ] Create `binary_markets` table
- [ ] Create `binary_prices` hypertable
- [ ] Create `binary_positions` table
- [ ] Seed test data for development
- [ ] Update Laravel models

### Phase 2: Data Ingestion (Days 3-4)
**Goal:** Real-time price streaming

- [ ] Research Polymarket CLOB API documentation
- [ ] Implement `PolymarketWebSocketProvider`
  - WebSocket connection
  - Market subscription
  - Order book parsing
  - Spread calculation
  - Database insertion
- [ ] Add Polymarket routing to `ProviderRouter`
- [ ] Test with live markets (read-only)

### Phase 3: Strategy Implementation (Days 5-6)
**Goal:** Arbitrage detection & execution

- [ ] Implement `ArbitrageStrategy`
  - Opportunity detection
  - Profit calculation
  - Risk management
- [ ] Implement `PolymarketTradingClient`
  - Order placement
  - Order monitoring
  - Position tracking
- [ ] Add strategy to engine execution loop
- [ ] Test with paper trading / testnet

### Phase 4: Dashboard (Days 7-9)
**Goal:** User interface for monitoring

- [ ] Create `ArbitrageMonitor` Livewire component
- [ ] Build opportunity list view
- [ ] Build position tracking view
- [ ] Add performance metrics
- [ ] Integrate WebSocket real-time updates
- [ ] Add manual execution controls

### Phase 5: Testing & Deployment (Days 10-14)
**Goal:** Production readiness

- [ ] Integration testing (all components)
- [ ] Load testing (handle 100+ markets)
- [ ] Paper trading validation
- [ ] Deploy with £50 test capital
- [ ] Monitor for 2-3 days
- [ ] Scale to £400 if profitable

---

## 9. API Research Checklist

### Polymarket CLOB API Investigation

**Priority 1 - Core Functionality:**
- [ ] WebSocket endpoint URL
- [ ] Authentication method (API key, JWT, signature?)
- [ ] Market data format (order book structure)
- [ ] Order placement endpoint
- [ ] Order status checking
- [ ] Position retrieval

**Priority 2 - Technical Details:**
- [ ] Rate limits (requests per minute)
- [ ] WebSocket message types
- [ ] Error codes and handling
- [ ] Fee structure (maker/taker fees)
- [ ] Minimum order sizes
- [ ] Market ID format

**Priority 3 - Testing:**
- [ ] Testnet/sandbox availability
- [ ] Paper trading support
- [ ] API documentation quality
- [ ] Client libraries (Python)
- [ ] Code examples

---

## 10. Risk Considerations

### Technical Risks

| Risk | Mitigation |
|------|------------|
| API downtime | Graceful degradation, retry logic, alerts |
| Order fill failures | Partial fill handling, cancel & retry |
| Price slippage | Use market orders, monitor fill prices |
| WebSocket disconnection | Auto-reconnect with exponential backoff |
| Database performance | Hypertables, indexes, query optimization |

### Financial Risks

| Risk | Mitigation |
|------|------------|
| Market manipulation | Avoid low-liquidity markets |
| Resolution disputes | Only trade on clear, verifiable events |
| Fee changes | Monitor fee structure, update calculations |
| Capital loss | Position limits, max exposure caps |
| Opportunity disappears | Fast execution (<100ms), accept this risk |

### Market Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Competition | Other bots close arbitrage faster | Optimize for speed (<100ms execution) |
| Low liquidity | Can't fill full position | Check volume before executing |
| Market closure | Position stuck until resolution | Diversify across multiple markets |
| Fee increases | Erodes profit margin | Monitor fees, adjust thresholds |

---

## 11. Success Metrics

### Development Metrics (2 Weeks)
- [ ] Latency: Price update to user screen < 50ms
- [ ] Execution: Detection to filled orders < 100ms
- [ ] Uptime: 99%+ (< 2 hours downtime)
- [ ] Code coverage: 80%+ tests

### Trading Metrics (2 Week Live Test)
- [ ] Total positions executed: 10+
- [ ] Win rate: 100% (arbitrage should guarantee profit)
- [ ] Average profit per trade: £2-5
- [ ] Total profit: £20+ (validates concept)
- [ ] Sharpe ratio: > 2.0

### Validation Criteria
✅ **Success:** Net profit > £20 after fees over 2 weeks
⚠️ **Partial Success:** Break even or small profit (validates concept, needs optimization)
❌ **Failure:** Net loss (re-evaluate strategy or market conditions)

---

## 12. Future Enhancements

### Short-term (Month 2)
- Add more binary platforms (Kalshi, PredictIt, Manifold)
- Cross-platform arbitrage (Polymarket vs Kalshi)
- Category filtering (only trade politics, sports, etc.)
- Mobile notifications for opportunities

### Medium-term (Month 3-6)
- Machine learning for optimal position sizing
- Historical backtest on past markets
- Auto-compounding (reinvest profits)
- Multi-account support (scale beyond £500)

### Long-term (6+ months)
- Market making (provide liquidity for fees)
- Predictive modeling (estimate resolution probability)
- Crypto integration (prediction markets on-chain)
- API for third-party strategy plugins

---

## 13. Appendix

### A. Glossary

- **Arbitrage:** Risk-free profit from price inefficiencies
- **CLOB:** Central Limit Order Book
- **Hypertable:** TimescaleDB's optimized time-series table
- **Spread:** Difference between bid and ask prices
- **YES/NO:** Binary outcome tokens (YES = event happens, NO = doesn't)

### B. References

- [Polymarket Documentation](https://docs.polymarket.com) (TBD - to be researched)
- [TimescaleDB Hypertables](https://docs.timescale.com/use-timescale/latest/hypertables/)
- [Laravel Livewire](https://livewire.laravel.com)
- Existing project docs: `ARCHITECTURE.md`, `TIMEZONE_STRATEGY.md`

### C. Contact & Support

- **Project Lead:** [User]
- **Implementation:** Claude Code Agent
- **Repository:** `/home/user/trading-stratigies`
- **Branch:** `claude/binary-options-arbitrage-fHzQ7`

---

**Document Status:** ✅ Ready for Implementation
**Next Steps:** Begin Phase 1 (Database Migrations)
