from __future__ import annotations
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "trading"),
    )


def compute_volume_profile_from_candles(symbol_id: int, bucket_start: datetime, bucket_end: datetime, conn):
    """
    Fallback: Compute approximate volume profile from candles when ticks aren't available.
    
    Distributes each candle's volume across its price range (high to low).
    Uses close vs open to estimate buy/sell pressure.
    """
    cur = conn.cursor()
    
    # Fetch candles in this bucket
    cur.execute("""
        SELECT time, open, high, low, close, volume
        FROM candles
        WHERE symbol_id = %s
          AND time >= %s
          AND time < %s
        ORDER BY time ASC
    """, (symbol_id, bucket_start, bucket_end))
    
    candles = cur.fetchall()
    if not candles:
        return None
    
    # Build approximate volume profile
    profile: Dict[float, Dict] = {}
    
    for candle_time, open_price, high, low, close, volume in candles:
        # Round prices to 2 decimals for grouping
        open_price = round(float(open_price), 2)
        high = round(float(high), 2)
        low = round(float(low), 2)
        close = round(float(close), 2)
        volume = int(volume)
        
        # Determine if candle is bullish or bearish
        is_bullish = close >= open_price
        
        # Distribute volume across price range
        # Simple approach: divide volume evenly across price levels
        price_range = high - low
        if price_range == 0:
            price_range = 0.01  # Avoid division by zero
        
        # Create price levels (every $0.10 or adjust based on range)
        step = max(0.10, price_range / 10)  # At least 10 levels
        current_price = low
        
        while current_price <= high:
            price_level = round(current_price, 2)
            
            if price_level not in profile:
                profile[price_level] = {'total': 0, 'buy': 0, 'sell': 0, 'count': 0}
            
            # Distribute volume proportionally
            vol_at_level = volume // 10  # Simple distribution
            
            profile[price_level]['total'] += vol_at_level
            profile[price_level]['count'] += 1
            
            # Estimate buy/sell based on candle direction
            if is_bullish:
                # Bullish candle: more buying pressure
                profile[price_level]['buy'] += int(vol_at_level * 0.6)
                profile[price_level]['sell'] += int(vol_at_level * 0.4)
            else:
                # Bearish candle: more selling pressure
                profile[price_level]['buy'] += int(vol_at_level * 0.4)
                profile[price_level]['sell'] += int(vol_at_level * 0.6)
            
            current_price += step
    
    # Insert volume profile rows
    if not profile:
        return None
    
    rows = []
    for price_level, vol in profile.items():
        rows.append((
            bucket_start,
            symbol_id,
            price_level,
            vol['total'],
            vol['buy'],
            vol['sell'],
            vol['count']
        ))
    
    execute_batch(cur, """
        INSERT INTO volume_profile (bucket, symbol_id, price_level, total_volume, buy_volume, sell_volume, trade_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bucket, symbol_id, price_level)
        DO UPDATE SET
            total_volume = EXCLUDED.total_volume,
            buy_volume = EXCLUDED.buy_volume,
            sell_volume = EXCLUDED.sell_volume,
            trade_count = EXCLUDED.trade_count
    """, rows)
    
    conn.commit()
    logger.info(f"Computed volume profile from {len(candles)} candles, {len(profile)} price levels")
    return profile


def compute_volume_profile(symbol_id: int, bucket_start: datetime, bucket_end: datetime, conn):
    """
    Compute volume profile from ticks for a given time bucket.
    Groups ticks by price level and calculates buy/sell volume using uptick/downtick rule.
    
    Fallback: If no ticks available, use candles to approximate volume profile.
    """
    cur = conn.cursor()
    
    # Fetch all ticks in this bucket, ordered by time
    cur.execute("""
        SELECT time, price, size
        FROM ticks
        WHERE symbol_id = %s
          AND time >= %s
          AND time < %s
        ORDER BY time ASC
    """, (symbol_id, bucket_start, bucket_end))
    
    ticks = cur.fetchall()
    
    # Fallback: If no ticks, use candles to approximate
    if not ticks:
        return compute_volume_profile_from_candles(symbol_id, bucket_start, bucket_end, conn)
    
    # Build volume profile: price_level -> {total, buy, sell, count}
    profile: Dict[float, Dict] = {}
    prev_price = None
    
    for tick_time, price, size in ticks:
        if price not in profile:
            profile[price] = {'total': 0, 'buy': 0, 'sell': 0, 'count': 0}
        
        profile[price]['total'] += size
        profile[price]['count'] += 1
        
        # Uptick/downtick rule to estimate aggressor
        if prev_price is not None:
            if price > prev_price:
                profile[price]['buy'] += size  # Uptick = aggressive buy
            elif price < prev_price:
                profile[price]['sell'] += size  # Downtick = aggressive sell
            else:
                # No change, split evenly
                profile[price]['buy'] += size // 2
                profile[price]['sell'] += size - (size // 2)
        else:
            # First tick, assume neutral
            profile[price]['buy'] += size // 2
            profile[price]['sell'] += size - (size // 2)
        
        prev_price = price
    
    # Insert volume profile rows
    rows = []
    for price_level, vol in profile.items():
        rows.append((
            bucket_start,
            symbol_id,
            price_level,
            vol['total'],
            vol['buy'],
            vol['sell'],
            vol['count']
        ))
    
    execute_batch(cur, """
        INSERT INTO volume_profile (bucket, symbol_id, price_level, total_volume, buy_volume, sell_volume, trade_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bucket, symbol_id, price_level)
        DO UPDATE SET
            total_volume = EXCLUDED.total_volume,
            buy_volume = EXCLUDED.buy_volume,
            sell_volume = EXCLUDED.sell_volume,
            trade_count = EXCLUDED.trade_count
    """, rows)
    
    conn.commit()
    return profile


def compute_profile_metrics(symbol_id: int, bucket_start: datetime, profile: Dict[float, Dict], conn):
    """
    Compute POC, VAH, VAL, LVNs, HVNs from volume profile.
    """
    if not profile:
        return
    
    # Sort by price
    sorted_prices = sorted(profile.keys())
    total_volume = sum(v['total'] for v in profile.values())
    
    # Find POC (Point of Control) - price with highest volume
    poc_price = max(profile.keys(), key=lambda p: profile[p]['total'])
    poc_volume = profile[poc_price]['total']
    
    # Find Value Area (70% of volume around POC)
    value_area_target = total_volume * 0.70
    value_area_volume = poc_volume
    lower_idx = sorted_prices.index(poc_price)
    upper_idx = lower_idx
    
    while value_area_volume < value_area_target and (lower_idx > 0 or upper_idx < len(sorted_prices) - 1):
        # Expand in direction with more volume
        lower_vol = profile[sorted_prices[lower_idx - 1]]['total'] if lower_idx > 0 else 0
        upper_vol = profile[sorted_prices[upper_idx + 1]]['total'] if upper_idx < len(sorted_prices) - 1 else 0
        
        if lower_vol >= upper_vol and lower_idx > 0:
            lower_idx -= 1
            value_area_volume += profile[sorted_prices[lower_idx]]['total']
        elif upper_idx < len(sorted_prices) - 1:
            upper_idx += 1
            value_area_volume += profile[sorted_prices[upper_idx]]['total']
        else:
            break
    
    vah = sorted_prices[upper_idx]
    val = sorted_prices[lower_idx]
    
    # Find LVNs (Low Volume Nodes) - gaps in volume profile
    avg_volume = total_volume / len(profile)
    lvn_threshold = avg_volume * 0.3  # 30% of average = low volume
    lvns = [p for p in sorted_prices if profile[p]['total'] < lvn_threshold]
    
    # Find HVNs (High Volume Nodes) - peaks
    hvn_threshold = avg_volume * 1.5  # 150% of average = high volume
    hvns = [p for p in sorted_prices if profile[p]['total'] > hvn_threshold]
    
    # Insert metrics
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO profile_metrics (bucket, symbol_id, poc, vah, val, total_volume, lvns, hvns)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bucket, symbol_id)
        DO UPDATE SET
            poc = EXCLUDED.poc,
            vah = EXCLUDED.vah,
            val = EXCLUDED.val,
            total_volume = EXCLUDED.total_volume,
            lvns = EXCLUDED.lvns,
            hvns = EXCLUDED.hvns
    """, (
        bucket_start,
        symbol_id,
        poc_price,
        vah,
        val,
        total_volume,
        psycopg2.extras.Json(lvns),
        psycopg2.extras.Json(hvns)
    ))
    conn.commit()
    
    logger.info(f"Computed profile metrics for bucket {bucket_start}: POC={poc_price:.2f}, VAH={vah:.2f}, VAL={val:.2f}, LVNs={len(lvns)}")


def compute_order_flow(symbol_id: int, bucket_start: datetime, profile: Dict[float, Dict], conn):
    """
    Compute order flow metrics (delta, CVD, buy/sell pressure) from volume profile.
    """
    if not profile:
        return
    
    total_buy = sum(v['buy'] for v in profile.values())
    total_sell = sum(v['sell'] for v in profile.values())
    total_volume = total_buy + total_sell
    
    delta = total_buy - total_sell
    buy_pressure = (total_buy / total_volume * 100) if total_volume > 0 else 50
    sell_pressure = (total_sell / total_volume * 100) if total_volume > 0 else 50
    
    # Get previous CVD to compute cumulative
    cur = conn.cursor()
    cur.execute("""
        SELECT cumulative_delta
        FROM order_flow
        WHERE symbol_id = %s AND bucket < %s
        ORDER BY bucket DESC
        LIMIT 1
    """, (symbol_id, bucket_start))
    
    row = cur.fetchone()
    prev_cvd = row[0] if row else 0
    cumulative_delta = prev_cvd + delta
    
    # Insert order flow
    cur.execute("""
        INSERT INTO order_flow (bucket, symbol_id, delta, cumulative_delta, aggressive_buys, aggressive_sells, buy_pressure, sell_pressure)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bucket, symbol_id)
        DO UPDATE SET
            delta = EXCLUDED.delta,
            cumulative_delta = EXCLUDED.cumulative_delta,
            aggressive_buys = EXCLUDED.aggressive_buys,
            aggressive_sells = EXCLUDED.aggressive_sells,
            buy_pressure = EXCLUDED.buy_pressure,
            sell_pressure = EXCLUDED.sell_pressure
    """, (
        bucket_start,
        symbol_id,
        delta,
        cumulative_delta,
        total_buy,
        total_sell,
        buy_pressure,
        sell_pressure
    ))
    conn.commit()
    
    logger.info(f"Computed order flow for bucket {bucket_start}: Delta={delta}, CVD={cumulative_delta}, Buy%={buy_pressure:.1f}")


def run():
    logger.info("Starting Volume Profile Calculator")
    conn = get_db_conn()
    
    # First run: process all historical data
    first_run = True
    
    while True:
        try:
            # Get all symbols
            cur = conn.cursor()
            cur.execute("SELECT id, symbol FROM symbols")
            symbols = cur.fetchall()
            
            for symbol_id, symbol_name in symbols:
                if first_run:
                    # On first run, process all available candles
                    logger.info(f"First run: processing all historical data for {symbol_name}")
                    
                    # Get time range of available candles
                    cur.execute("""
                        SELECT MIN(time), MAX(time) 
                        FROM candles 
                        WHERE symbol_id = %s
                    """, (symbol_id,))
                    
                    row = cur.fetchone()
                    if not row or not row[0]:
                        continue
                    
                    min_time, max_time = row
                    logger.info(f"Processing {symbol_name} from {min_time} to {max_time}")
                    
                    # Process in 1-minute buckets
                    current = min_time.replace(second=0, microsecond=0)
                    processed = 0
                    
                    while current < max_time:
                        bucket_end = current + timedelta(minutes=1)
                        
                        profile = compute_volume_profile(symbol_id, current, bucket_end, conn)
                        if profile:
                            compute_profile_metrics(symbol_id, current, profile, conn)
                            compute_order_flow(symbol_id, current, profile, conn)
                            processed += 1
                        
                        current = bucket_end
                    
                    logger.info(f"Processed {processed} buckets for {symbol_name}")
                else:
                    # Subsequent runs: process last 5 minutes
                    now = datetime.now(timezone.utc)
                    for i in range(5, 0, -1):
                        bucket_start = (now - timedelta(minutes=i)).replace(second=0, microsecond=0)
                        bucket_end = bucket_start + timedelta(minutes=1)
                        
                        profile = compute_volume_profile(symbol_id, bucket_start, bucket_end, conn)
                        if profile:
                            compute_profile_metrics(symbol_id, bucket_start, profile, conn)
                            compute_order_flow(symbol_id, bucket_start, profile, conn)
            
            first_run = False
            
            logger.info("Processed volume profiles, sleeping 60s...")
            time.sleep(60)
            
        except Exception as e:
            logger.exception("Profile calculator error: {}", e)
            time.sleep(15)


if __name__ == "__main__":
    run()
