#!/usr/bin/env python3
"""
Backfill demo data for a full trading day (6.5 hours = 390 minutes)
Generates realistic 1-minute candles from 09:30 to 16:00 ET (market hours)
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone, timedelta
import random

# Database connection
def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "trading"),
    )

def generate_trading_day_candles(symbol: str = "AAPL", base_price: float = 150.0):
    """
    Generate realistic candles for a full trading day.
    Market hours: 09:30 - 16:00 ET = 390 minutes
    """
    candles = []
    
    # Start at 09:30 ET today (convert to UTC)
    now_utc = datetime.now(timezone.utc)
    # Market opens at 09:30 ET (13:30 or 14:30 UTC depending on DST)
    market_open_et = now_utc.replace(hour=9, minute=30, second=0, microsecond=0)
    # Adjust for ET timezone (approximate - 4 or 5 hours from UTC)
    market_open_utc = market_open_et + timedelta(hours=4)  # EDT offset
    
    current_price = base_price
    volatility = 0.002  # 0.2% per minute
    
    # Generate 390 candles (6.5 hours)
    for i in range(390):
        candle_time = market_open_utc + timedelta(minutes=i)
        
        # Random price movement
        change = random.gauss(0, volatility)
        open_price = current_price
        close_price = open_price * (1 + change)
        
        # High/Low with some spread
        spread = abs(close_price - open_price) * random.uniform(1.2, 2.0)
        high_price = max(open_price, close_price) + spread * random.random()
        low_price = min(open_price, close_price) - spread * random.random()
        
        # Volume (higher at open/close, lower mid-day)
        hour = (i // 60)
        if hour == 0 or hour >= 5:  # First or last hour
            base_volume = random.randint(50000, 150000)
        else:
            base_volume = random.randint(20000, 80000)
        
        candles.append({
            'time': candle_time,
            'symbol': symbol,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': base_volume
        })
        
        current_price = close_price
    
    return candles

def insert_candles(conn, candles):
    """Insert candles into database."""
    cur = conn.cursor()
    
    # Get or create symbol
    symbol = candles[0]['symbol']
    cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
    row = cur.fetchone()
    
    if row:
        symbol_id = row[0]
    else:
        cur.execute("INSERT INTO symbols (symbol) VALUES (%s) RETURNING id", (symbol,))
        symbol_id = cur.fetchone()[0]
        conn.commit()
    
    # Insert candles
    inserted = 0
    for candle in candles:
        try:
            cur.execute("""
                INSERT INTO candles (time, symbol_id, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol_id) DO NOTHING
            """, (
                candle['time'],
                symbol_id,
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume']
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting candle at {candle['time']}: {e}")
    
    conn.commit()
    return inserted

def main():
    print("🕐 Backfilling demo data for full trading day...")
    print("")
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    base_price = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
    
    print(f"Symbol: {symbol}")
    print(f"Base Price: ${base_price}")
    print(f"Generating 390 candles (09:30 - 16:00 ET)...")
    print("")
    
    # Generate candles
    candles = generate_trading_day_candles(symbol, base_price)
    
    # Connect to database
    conn = get_db_conn()
    
    # Insert candles
    inserted = insert_candles(conn, candles)
    
    print(f"✅ Inserted {inserted} candles")
    print(f"📊 Time range: {candles[0]['time']} to {candles[-1]['time']} (UTC)")
    print(f"💰 Price range: ${min(c['close'] for c in candles):.2f} - ${max(c['close'] for c in candles):.2f}")
    print("")
    print("Next steps:")
    print("  1. Refresh dashboard: http://127.0.0.1:8002/dashboard")
    print("  2. Wait 60s for volume profile calculation")
    print("  3. Try different timeframes (1m, 5m, 15m, 30m, 1h)")
    print("")

if __name__ == "__main__":
    main()
