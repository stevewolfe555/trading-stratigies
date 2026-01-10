# Testing Database Insertion Fix

**Date:** 2026-01-10
**Status:** Ready for testing
**Branch:** `claude/phase4-early-exit-dashboard-fHzQ7`

---

## What Was Fixed

The `binary_prices` table was staying empty because the engine's WebSocket provider was just a stub. The ingestion service had the DB insertion logic, but the arbitrage monitor in the engine didn't.

**Solution:** Added comprehensive WebSocket message processing directly to the arbitrage monitor that:
1. Maps token IDs to markets (YES/NO pairs)
2. Caches individual token prices as WebSocket updates arrive
3. Inserts into `binary_prices` when we have prices for BOTH YES and NO
4. Precomputes spread and arbitrage flags

---

## Changes Made

### 1. Database Migration
**File:** `web/database/migrations/2026_01_10_000001_add_token_ids_to_binary_markets.php`

Added columns to `binary_markets`:
- `yes_token_id` - Polymarket token ID for YES outcome
- `no_token_id` - Polymarket token ID for NO outcome
- Indexes for fast WebSocket lookups

### 2. Market Fetcher
**File:** `services/engine/app/utils/market_fetcher.py`

Updated to populate `yes_token_id` and `no_token_id` when fetching markets from Polymarket API.

### 3. Arbitrage Monitor
**File:** `services/engine/app/utils/arbitrage_monitor.py`

Added:
- `_build_token_market_map()` - Maps token IDs to markets on startup
- `_process_ws_message()` - Routes WebSocket events
- `_process_book_event()` - Handles full orderbook snapshots
- `_process_price_change_event()` - Handles best bid/ask updates
- `_try_insert_price_data()` - Inserts into `binary_prices` when both YES/NO available

---

## Testing Steps

### Step 1: Run Database Migration

```bash
# SSH into web container
docker compose exec web bash

# Run migration
php artisan migrate

# Verify columns exist
php artisan tinker
>>> \DB::select("SELECT column_name FROM information_schema.columns WHERE table_name = 'binary_markets' AND column_name LIKE '%token%'");
# Should show: yes_token_id, no_token_id
```

### Step 2: Fetch Markets with Token IDs

```bash
# SSH into engine container
docker compose exec engine bash

# Run market fetcher
python -m app.utils.market_fetcher --limit 20 --categories politics sports

# Expected output:
# - Fetched X markets
# - Filtered to Y markets in categories: ['politics', 'sports']
# - After filtering short-term crypto: Z markets
# - Successfully added/updated Z markets
```

### Step 3: Verify Token IDs Populated

```bash
# Check database
docker compose exec web php artisan tinker

>>> \App\Models\BinaryMarket::whereNotNull('yes_token_id')->count();
# Should be > 0

>>> $market = \App\Models\BinaryMarket::whereNotNull('yes_token_id')->first();
>>> echo "YES: {$market->yes_token_id}\nNO: {$market->no_token_id}\n";
# Should show two different token IDs
```

### Step 4: Run Arbitrage Monitor in Monitor Mode

```bash
# SSH into engine container
docker compose exec engine bash

# Run in monitor-only mode (no trading)
python -m app.utils.arbitrage_monitor --mode monitor

# Expected output:
# [SUCCESS] Built token-market mapping for X tokens
# [INFO] Subscribing to X tokens (Y markets)
# [SUCCESS] Connected to Polymarket WebSocket
# [INFO] Processing WebSocket messages...
```

**What to look for:**
- Token-market mapping builds successfully
- WebSocket connects
- Price updates logged as they arrive
- Arbitrage opportunities detected (if any exist)

### Step 5: Verify binary_prices Gets Populated

```bash
# In another terminal, check database
docker compose exec web php artisan tinker

>>> \DB::table('binary_prices')->count();
# Should increase over time as prices arrive

>>> \DB::table('binary_prices')->latest('timestamp')->first();
# Should show recent price data with:
# - yes_bid, yes_ask, yes_mid
# - no_bid, no_ask, no_mid
# - spread (yes_ask + no_ask)
# - arbitrage_opportunity (true if spread < 0.995)
# - estimated_profit_pct
```

### Step 6: Check for Arbitrage Opportunities

```bash
>>> \DB::table('binary_prices')->where('arbitrage_opportunity', true)->count();
# Number of arbitrage opportunities detected

>>> \DB::table('binary_prices')
      ->where('arbitrage_opportunity', true)
      ->orderBy('estimated_profit_pct', 'desc')
      ->limit(5)
      ->get(['symbol_id', 'spread', 'estimated_profit_pct', 'timestamp']);
# Top 5 arbitrage opportunities
```

---

## Expected Performance

### WebSocket Message Flow

1. **Polymarket sends "book" or "price_change" event** for a single token (YES or NO)
2. **arbitrage_monitor receives** and parses the message
3. **Cache updated** with latest bid/ask for that token
4. **Check if we have both YES and NO prices** for this market
5. **If yes:** Calculate spread and insert into `binary_prices`
6. **If arbitrage detected:** Log opportunity

### Database Insertion Rate

- **Expected:** 1-10 rows/second (depends on market activity)
- **Latency:** <50ms from WebSocket to database
- **Storage:** ~100KB per market per day (TimescaleDB compression)

### Arbitrage Detection

With 20 markets monitored:
- **Opportunities:** 0-5 per day (rare!)
- **Profit threshold:** 0.5%+ (spread < $0.995)
- **Zero fees** on political/sports markets

---

## Troubleshooting

### Issue: Token-market mapping is empty

**Cause:** No markets with token IDs in database

**Fix:**
```bash
python -m app.utils.market_fetcher --limit 50 --categories politics sports
```

### Issue: WebSocket connects but no price data

**Cause:** Token IDs might be incorrect or markets inactive

**Check:**
```sql
SELECT yes_token_id, no_token_id, question, status
FROM binary_markets
WHERE status = 'active'
LIMIT 5;
```

Verify token IDs are valid by checking Polymarket API:
```bash
curl "https://gamma-api.polymarket.com/markets" | jq '.[0].tokens'
```

### Issue: binary_prices stays empty

**Possible causes:**
1. WebSocket not receiving messages (check logs)
2. Token IDs don't match (check binary_markets.yes_token_id)
3. Messages being filtered out (check event_type in logs)

**Debug:**
Enable verbose logging in arbitrage_monitor:
```python
logger.add(sys.stderr, level="DEBUG")
```

### Issue: Only seeing one token's prices

**Cause:** Markets might only have activity on one side

**Expected behavior:**
- Some markets are one-sided (e.g., 95% YES probability)
- We need BOTH YES and NO prices to calculate spread
- This is normal - keep monitoring, prices will arrive

---

## Success Criteria

✅ **Migration runs successfully** - token ID columns added
✅ **Market fetcher populates token IDs** - verified in database
✅ **Token-market mapping builds** - logged on monitor startup
✅ **WebSocket connects** - receives messages
✅ **binary_prices gets populated** - rows inserted over time
✅ **Arbitrage opportunities detected** - logged when spread < $0.995
✅ **Early exit monitoring works** - queries latest spreads from binary_prices

---

## Next Steps After Testing

Once verified working:

1. **Run paper trading** for 24 hours
   ```bash
   python -m app.utils.arbitrage_monitor --mode paper --capital 500
   ```

2. **Analyze results**
   - How many opportunities detected?
   - How many positions opened?
   - How many early exits?
   - Average hold time?
   - Total P&L?

3. **Build dashboard** (Phase 5)
   - Real-time opportunity feed
   - Open position monitor with exit signals
   - Performance metrics

4. **Deploy live** (if profitable)
   - Start with £50-100
   - Enable early exit
   - Monitor for 1 week
   - Scale if successful

---

**Status:** Ready for testing
**Blockers:** None - all code in place
**Risk:** Low - monitor-only mode is read-only
