# Timezone Strategy

## Overview

This document defines how we handle timezones throughout the trading platform to ensure consistency and avoid confusion.

## Core Principles

1. **Store everything in UTC** - Database stores all timestamps in UTC (Coordinated Universal Time)
2. **Display in market timezone** - UI shows times in the relevant market timezone (ET for US stocks)
3. **Convert at the edges** - Conversion happens at ingestion (to UTC) and display (from UTC)

## Timezone Flow

```
Market Data Provider (various timezones)
  ↓ convert to UTC
Database (UTC only - TIMESTAMPTZ)
  ↓ convert to market timezone
Display (ET for US stocks, JST for Japan, etc.)
```

## Implementation Details

### 1. Database Storage (UTC)

**All tables use `TIMESTAMPTZ`:**
```sql
CREATE TABLE candles (
    time TIMESTAMPTZ NOT NULL,  -- Stored in UTC
    ...
);
```

**Why UTC?**
- No ambiguity (no DST transitions)
- Easy to compare times across markets
- Standard for distributed systems
- TimescaleDB optimized for UTC

### 2. Ingestion (Convert to UTC)

**Alpaca WebSocket:**
```python
# Alpaca sends: "2025-10-01T09:30:00.123Z" (already UTC)
dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
# Store as-is in UTC
```

**Alpha Vantage:**
```python
# Alpha Vantage sends: "2025-10-01 09:30:00" (US Eastern Time)
dt = datetime.fromisoformat(ts_str)
dt = dt.replace(tzinfo=timezone(timedelta(hours=-4)))  # EDT
dt_utc = dt.astimezone(timezone.utc)
# Store in UTC
```

**Demo Provider:**
```python
# Generate in UTC
dt = datetime.now(timezone.utc)
# Store in UTC
```

### 3. Display (Convert from UTC)

**Dashboard (Laravel/PHP):**
```sql
-- Convert UTC to US Eastern Time for display
SELECT time AT TIME ZONE 'America/New_York' as time_et
FROM candles
```

**JavaScript (TradingView Charts):**
```javascript
// Timestamps are already in ET from backend
// Just parse and display
const time = parseTime(timeStr);  // "2025-10-01 09:30:00" (ET)
```

## Market Timezones

| Market | Timezone | UTC Offset | Trading Hours (Local) |
|--------|----------|------------|----------------------|
| **US Stocks** | America/New_York | UTC-5 (EST) / UTC-4 (EDT) | 09:30 - 16:00 |
| **US Futures** | America/Chicago | UTC-6 (CST) / UTC-5 (CDT) | 17:00 - 16:00 (next day) |
| **Europe** | Europe/London | UTC+0 (GMT) / UTC+1 (BST) | 08:00 - 16:30 |
| **Asia** | Asia/Tokyo | UTC+9 (JST) | 09:00 - 15:00 |

## Configuration

**Environment Variables:**
```bash
# Database timezone (always UTC)
DB_TIMEZONE=UTC

# Application timezone (for logging, etc.)
APP_TIMEZONE=UTC

# Display timezone per symbol (future enhancement)
# SYMBOL_TIMEZONE_AAPL=America/New_York
# SYMBOL_TIMEZONE_NQ=America/Chicago
```

## Code Examples

### Storing Data (Python)

```python
from datetime import datetime, timezone

# Always store in UTC
def insert_candle(time: datetime, ...):
    # Ensure timezone-aware
    if time.tzinfo is None:
        time = time.replace(tzinfo=timezone.utc)
    
    # Convert to UTC if not already
    time_utc = time.astimezone(timezone.utc)
    
    # Store
    cur.execute(
        "INSERT INTO candles (time, ...) VALUES (%s, ...)",
        (time_utc, ...)
    )
```

### Retrieving Data (PHP/Laravel)

```php
// Get data in market timezone
$candles = DB::select(
    "SELECT time AT TIME ZONE 'America/New_York' as time_et, close
     FROM candles
     WHERE symbol_id = ?",
    [$symbolId]
);

// Times are now in ET (without timezone suffix)
// "2025-10-01 09:30:00" (ET)
```

### Displaying Data (JavaScript)

```javascript
// Backend sends: "2025-10-01 09:30:00" (already in ET)
// Just format for display
function formatTime(timeStr) {
    const parts = timeStr.split(' ');
    return parts[1].substring(0, 5);  // "09:30"
}
```

## Testing Timezone Handling

### Verify UTC Storage

```sql
-- Check raw timestamps (should be in UTC)
SELECT time, time AT TIME ZONE 'UTC' as time_utc
FROM candles
LIMIT 5;
```

### Verify ET Display

```sql
-- Check converted timestamps (should be in ET)
SELECT 
    time AT TIME ZONE 'UTC' as time_utc,
    time AT TIME ZONE 'America/New_York' as time_et
FROM candles
LIMIT 5;
```

### Example Output

```
time_utc            | time_et
--------------------|--------------------
2025-10-01 13:30:00 | 2025-10-01 09:30:00  (EDT, UTC-4)
2025-12-01 14:30:00 | 2025-12-01 09:30:00  (EST, UTC-5)
```

## Daylight Saving Time (DST)

**Handled automatically by PostgreSQL:**
- `America/New_York` automatically switches between EST and EDT
- No manual intervention needed
- Database handles DST transitions correctly

**DST Transitions:**
- **Spring Forward**: 2nd Sunday in March, 2:00 AM → 3:00 AM
- **Fall Back**: 1st Sunday in November, 2:00 AM → 1:00 AM

## Best Practices

### ✅ DO

- Store all timestamps in UTC
- Use `TIMESTAMPTZ` in PostgreSQL
- Convert to market timezone only for display
- Use timezone-aware datetime objects in Python
- Test across DST boundaries

### ❌ DON'T

- Store timestamps without timezone info
- Mix timezones in the same table
- Convert to local timezone before storage
- Assume timestamps are in a specific timezone
- Hard-code UTC offsets (use timezone names)

## Troubleshooting

### Issue: Times are off by N hours

**Cause**: Timezone conversion not happening correctly

**Solution**:
1. Check database: `SELECT time, pg_typeof(time) FROM candles LIMIT 1;`
2. Should return `timestamp with time zone`
3. Check conversion: `SELECT time AT TIME ZONE 'America/New_York' FROM candles LIMIT 1;`

### Issue: Chart shows wrong times

**Cause**: JavaScript parsing timestamps incorrectly

**Solution**:
1. Check backend output format
2. Ensure times are strings, not Date objects
3. Verify parseTime() function handles format correctly

### Issue: Signals don't align with candles

**Cause**: Signals and candles in different timezones

**Solution**:
1. Ensure both use same conversion: `AT TIME ZONE 'America/New_York'`
2. Check signal generation uses UTC timestamps
3. Verify join conditions match exactly

## Future Enhancements

1. **Multi-market support**: Different timezones per symbol
2. **User preferences**: Allow users to choose display timezone
3. **Timezone indicator**: Show current timezone in UI
4. **24-hour markets**: Handle futures that trade around the clock

## Summary

**Golden Rule**: Store in UTC, display in market timezone.

This ensures:
- ✅ Consistency across the platform
- ✅ No ambiguity or confusion
- ✅ Easy to add new markets
- ✅ Correct handling of DST
- ✅ Standard practice in financial systems
