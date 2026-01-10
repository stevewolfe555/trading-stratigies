# Phase 3: Testing & Validation Guide

**Status:** 🚀 Ready to Start
**Duration:** 2 weeks (1 week paper trading + 1 week live testing)
**Goal:** Validate 0.5%+ profit on arbitrage opportunities with zero fees

---

## Prerequisites

### 1. Database Setup

Run migrations to create binary options tables:

```bash
cd web
php artisan migrate
```

**Tables created:**
- `symbols` (add asset_type column)
- `binary_markets` (market metadata)
- `binary_prices` (real-time YES/NO prices - hypertable)
- `binary_positions` (position tracking)

### 2. Python Dependencies

Install required packages:

```bash
# Engine service
cd services/engine
pip install -r requirements.txt

# Ingestion service
cd services/ingestion
pip install -r requirements.txt
```

**Key packages:**
- `py-clob-client>=0.20` - Official Polymarket client
- `websockets>=12.0` - Async WebSocket
- `aiohttp>=3.9` - Async HTTP

### 3. Environment Variables

Add to `.env`:

```bash
# Database
DB_HOST=localhost
DB_NAME=trading
DB_USER=postgres
DB_PASSWORD=your_password

# Polymarket (for live trading only)
POLYMARKET_PRIVATE_KEY=0x...  # Ethereum private key (optional for phase 3a)
```

**Note:** Private key only needed for live trading (Week 2). Week 1 is read-only.

---

## Week 1: Paper Trading (No Risk)

### Step 1: Fetch Active Markets

Populate database with political and sports markets (zero fees!):

```bash
cd services/engine

# Fetch top 50 political and sports markets
python -m app.utils.market_fetcher \
    --limit 50 \
    --categories politics sports
```

**Expected output:**
```
[INFO] Fetching markets from Polymarket API (limit: 50)
[INFO] Fetched 87 markets
[INFO] Filtered to 52 markets in categories: ['politics', 'sports']
[INFO] After filtering short-term crypto: 50 markets
[SUCCESS] Successfully added/updated 50 markets
```

**Verify in database:**
```sql
SELECT COUNT(*) FROM binary_markets WHERE status = 'active';
-- Should return ~50

SELECT category, COUNT(*)
FROM binary_markets
GROUP BY category;
-- Should show politics, sports

SELECT question, category, end_date
FROM binary_markets
WHERE status = 'active'
ORDER BY end_date
LIMIT 10;
-- Shows upcoming markets
```

### Step 2: Monitor for Opportunities (Read-Only)

Start real-time monitoring without trading:

```bash
python -m app.utils.arbitrage_monitor \
    --mode monitor \
    --spread-threshold 0.995 \
    --min-profit 0.005
```

**What this does:**
- ✅ Connects to Polymarket WebSocket
- ✅ Subscribes to YES/NO tokens for all markets
- ✅ Monitors for spread < $0.995
- ✅ Logs opportunities but doesn't trade
- ✅ Calculates expected profit percentage

**Expected output:**
```
[INFO] Arbitrage monitor initialized | Mode: monitor | Capital: $500
[INFO] Monitoring 50 markets for arbitrage opportunities
[SUCCESS] Connected to Polymarket WebSocket
[INFO] Subscribed to 100 assets (50 markets × 2 tokens)

💰 ARBITRAGE OPPORTUNITY #1 | TRUMP-WIN-2024 | Spread: $0.9920 | Profit: 0.81% | Will Trump win 2024?
💰 ARBITRAGE OPPORTUNITY #2 | CHIEFS-SUPERBOWL | Spread: $0.9945 | Profit: 0.55% | Chiefs win Super Bowl?
...
```

**Monitor for 24 hours to observe:**
- How many opportunities appear
- What profit percentages are realistic
- Which markets have best spreads
- Peak trading times

### Step 3: Paper Trading Simulation

Simulate trades to validate profitability:

```bash
python -m app.utils.arbitrage_monitor \
    --mode paper \
    --capital 500 \
    --spread-threshold 0.995 \
    --min-profit 0.005
```

**What this does:**
- ✅ Everything from monitor mode +
- ✅ Simulates buying YES and NO at detected spreads
- ✅ Calculates actual profit per trade
- ✅ Tracks cumulative P&L
- ✅ Position size: £100 per trade (10% of capital)

**Expected output:**
```
💰 ARBITRAGE OPPORTUNITY #1 | TRUMP-WIN-2024 | Spread: $0.9920 | Profit: 0.81%
📝 PAPER TRADE #1 | TRUMP-WIN-2024 | Size: $100.00 | Profit: $0.80 | Total P&L: $0.80

💰 ARBITRAGE OPPORTUNITY #2 | CHIEFS-SUPERBOWL | Spread: $0.9945 | Profit: 0.55%
📝 PAPER TRADE #2 | CHIEFS-SUPERBOWL | Size: $100.00 | Profit: $0.55 | Total P&L: $1.35
...

📊 MONITORING STATISTICS
Runtime: 3600s (60.0 minutes)
Opportunities found: 15
Trades executed: 15
Paper P&L: $12.50
Mode: paper
```

### Step 4: Analyze Results

After 1 week of paper trading, analyze:

**Query paper trading results:**
```sql
-- Count opportunities by market
SELECT
    s.symbol,
    bm.question,
    COUNT(*) as opportunities,
    AVG(bp.spread) as avg_spread,
    AVG(bp.estimated_profit_pct) as avg_profit_pct
FROM binary_prices bp
JOIN symbols s ON bp.symbol_id = s.id
JOIN binary_markets bm ON bm.symbol_id = s.id
WHERE bp.arbitrage_opportunity = true
    AND bp.timestamp > NOW() - INTERVAL '7 days'
GROUP BY s.symbol, bm.question
ORDER BY opportunities DESC
LIMIT 20;
```

**Success Criteria (Week 1):**
- [ ] 10+ arbitrage opportunities detected
- [ ] Average profit per opportunity: 0.5%+
- [ ] Zero false positives (all opportunities are real)
- [ ] WebSocket latency: <50ms
- [ ] Opportunity detection: <10ms
- [ ] Paper P&L: Positive (even £5 validates concept)

**If criteria met:** Proceed to Week 2 (Live Trading)
**If not met:** Adjust thresholds and paper trade longer

---

## Week 2: Live Testing (Small Capital)

### Step 1: Setup Polymarket Account

**Requirements:**
1. Create Polymarket account at polymarket.com
2. Fund with USDC on Polygon (start with £50-100)
3. Get Ethereum private key (MetaMask, hardware wallet, etc.)
4. Set token allowances (USDC + Conditional Tokens)

**Set environment variable:**
```bash
export POLYMARKET_PRIVATE_KEY="0x..."  # Your Ethereum private key
```

**Test authentication:**
```python
from app.trading.polymarket_client import PolymarketTradingClient

client = PolymarketTradingClient(
    private_key=os.getenv('POLYMARKET_PRIVATE_KEY')
)

# Should initialize without errors
print("✅ Trading client initialized")
```

### Step 2: Start with Small Capital

Begin with £50 to minimize risk:

```bash
python -m app.utils.arbitrage_monitor \
    --mode live \
    --capital 50 \
    --spread-threshold 0.99 \  # More conservative for live
    --min-profit 0.01          # 1% minimum for safety
```

**Conservative settings for first live trades:**
- Lower capital: £50 instead of £500
- Tighter spread: $0.99 instead of $0.995
- Higher min profit: 1% instead of 0.5%
- Max position: £25 per trade (50% of capital)

**Monitor first trades closely:**
- Verify both YES and NO orders fill
- Check actual fees charged (should be $0.00 for political/sports)
- Confirm positions appear in Polymarket UI
- Validate profit calculations

### Step 3: Execute 5-10 Test Trades

**Target:** Complete 5-10 small trades over 2-3 days

**Track metrics:**
- Fill rate (both orders filled?)
- Execution speed (time from opportunity to fill)
- Actual vs expected profit
- Fee verification (should be zero!)
- Position resolution (wait for market close)

**Example trade log:**
```
Trade 1: TRUMP-WIN-2024
- Spread: $0.9850
- Size: $25
- Expected profit: $0.375 (1.5%)
- Actual fees: $0.00 ✅
- Status: Both orders filled ✅
- Execution time: 87ms ✅

Trade 2: CHIEFS-SUPERBOWL
- Spread: $0.9900
- Size: $25
- Expected profit: $0.25 (1.0%)
- Actual fees: $0.00 ✅
- Status: Both orders filled ✅
- Execution time: 93ms ✅
```

### Step 4: Validate & Scale

After 5-10 successful trades:

**Validation checklist:**
- [ ] All trades had zero fees (political/sports markets)
- [ ] Fill rate: 100% (both YES and NO filled)
- [ ] Average execution time: <100ms
- [ ] Actual profit matches expected profit
- [ ] No errors or failed orders
- [ ] Total P&L: Positive (even £1 is success)

**If validated:** Scale up capital

```bash
# Increase to £200
python -m app.utils.arbitrage_monitor \
    --mode live \
    --capital 200 \
    --spread-threshold 0.995 \
    --min-profit 0.005

# Then £400 (full capital)
python -m app.utils.arbitrage_monitor \
    --mode live \
    --capital 400 \
    --spread-threshold 0.995 \
    --min-profit 0.005
```

### Step 5: Monitor for 2 Weeks

Run continuously with £400 capital:

**Monitoring setup:**
```bash
# Run in background with logging
nohup python -m app.utils.arbitrage_monitor \
    --mode live \
    --capital 400 \
    --spread-threshold 0.995 \
    --min-profit 0.005 \
    > arbitrage_monitor.log 2>&1 &

# Tail logs
tail -f arbitrage_monitor.log
```

**Daily check:**
- Review executed trades
- Check P&L progress
- Verify no errors
- Monitor market conditions

**Weekly review:**
```sql
-- Profit by week
SELECT
    DATE_TRUNC('week', opened_at) as week,
    COUNT(*) as trades,
    SUM(profit_loss) as total_profit,
    AVG(profit_loss_pct) as avg_profit_pct
FROM binary_positions
WHERE status = 'closed'
GROUP BY week
ORDER BY week;

-- Best performing markets
SELECT
    bm.question,
    COUNT(*) as trades,
    SUM(bp.profit_loss) as total_profit,
    AVG(bp.entry_spread) as avg_spread
FROM binary_positions bp
JOIN binary_markets bm ON bp.market_id = bm.market_id
WHERE bp.status = 'closed'
GROUP BY bm.question
ORDER BY total_profit DESC
LIMIT 10;
```

---

## Success Criteria (Final)

**After 2 weeks of live trading:**

### Minimum Requirements (MVP Validation)
- [ ] Total profit: **£20+** (4% return on £500)
- [ ] Win rate: **100%** (arbitrage guarantees profit if executed correctly)
- [ ] Trades executed: **10+**
- [ ] Zero fees verified on political/sports markets
- [ ] No failed trades or errors
- [ ] System uptime: 95%+

### Stretch Goals (Excellent Performance)
- [ ] Total profit: £50+ (10% return)
- [ ] Trades executed: 25+
- [ ] Average profit per trade: 1%+
- [ ] Execution speed: <100ms consistently
- [ ] Multiple markets profitable

---

## Troubleshooting

### Issue: No markets in database
**Solution:**
```bash
python -m app.utils.market_fetcher --limit 50 --categories politics sports
```

### Issue: WebSocket connection fails
**Solution:**
- Check internet connection
- Verify URL: wss://ws-subscriptions-clob.polymarket.com/ws/market
- Check firewall/proxy settings

### Issue: No arbitrage opportunities found
**Possible causes:**
- Spread threshold too low (try 0.998 or 0.999)
- Markets efficiently priced (arbitrage is rare)
- Not enough markets monitored (add more categories)
- Wrong time of day (try during US market hours)

### Issue: Orders not filling (live mode)
**Solution:**
- Check USDC balance on Polygon
- Verify token allowances set
- Try smaller position sizes
- Check Polymarket account status

### Issue: Fees being charged
**Cause:** Trading 15-minute crypto markets (have fees)
**Solution:**
- Filter out short-term crypto markets
- Stick to political and sports categories

---

## Performance Monitoring

### Real-time Metrics

Monitor these KPIs during testing:

| Metric | Target | Measurement |
|--------|--------|-------------|
| WebSocket latency | <50ms | Time from exchange to DB insert |
| Opportunity detection | <10ms | Time to scan and identify arbitrage |
| Order execution | <100ms | Time from detection to filled orders |
| Fill rate | 100% | Percentage of orders that fill |
| Profit accuracy | 100% | Actual vs expected profit match |
| System uptime | 99%+ | Hours online / total hours |

### Query performance metrics

```sql
-- Average latency (price update to DB)
SELECT AVG(EXTRACT(EPOCH FROM (NOW() - timestamp))) as avg_latency_seconds
FROM binary_prices
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- Arbitrage opportunities per hour
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as opportunities
FROM binary_prices
WHERE arbitrage_opportunity = true
    AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Average spread by market
SELECT
    s.symbol,
    bm.question,
    AVG(bp.spread) as avg_spread,
    MIN(bp.spread) as min_spread,
    COUNT(*) as data_points
FROM binary_prices bp
JOIN symbols s ON bp.symbol_id = s.id
JOIN binary_markets bm ON bm.symbol_id = s.id
WHERE bp.timestamp > NOW() - INTERVAL '7 days'
GROUP BY s.symbol, bm.question
ORDER BY avg_spread ASC
LIMIT 20;
```

---

## Next Steps After Phase 3

**If successful (£20+ profit validated):**

### Phase 4: Dashboard Development
- Build ArbitrageMonitor Livewire component
- Real-time opportunity display
- Position tracking UI
- Performance metrics visualization

### Phase 5: Scale & Optimize
- Increase capital to £1000+
- Add more markets (50 → 100+)
- Optimize execution speed (<50ms)
- Add cross-platform arbitrage (Kalshi, PredictIt)
- Implement auto-compounding

### Phase 6: Production Deployment
- Containerize services
- Add monitoring and alerts
- Implement auto-restart on failures
- Set up daily/weekly reports
- Add mobile notifications

---

## Resources

### Documentation
- [Polymarket API Research](./POLYMARKET_API_RESEARCH.md)
- [Binary Options Design](./BINARY_OPTIONS_DESIGN.md)
- [Architecture Overview](./ARCHITECTURE.md)

### Code
- Market Fetcher: `services/engine/app/utils/market_fetcher.py`
- Arbitrage Monitor: `services/engine/app/utils/arbitrage_monitor.py`
- WebSocket Provider: `services/ingestion/app/providers/polymarket_ws.py`
- Trading Client: `services/engine/app/trading/polymarket_client.py`

### External Resources
- [Polymarket Documentation](https://docs.polymarket.com)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Trading Fees](https://docs.polymarket.com/polymarket-learn/trading/fees)

---

**Status:** Ready to begin Week 1 (Paper Trading)
**Last Updated:** 2026-01-09
