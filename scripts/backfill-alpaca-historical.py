#!/usr/bin/env python3
"""
Backfill real historical data from Alpaca API.
Fetches actual market data for the specified symbol and date range.
"""

import os
import sys
import requests
import psycopg2
from datetime import datetime, timezone, timedelta

def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "trading"),
    )

def fetch_alpaca_bars(symbol, start_date, end_date, api_key, secret_key):
    """
    Fetch historical bars from Alpaca API.
    Uses the v2 bars endpoint with 1-minute timeframe.
    """
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    
    params = {
        "timeframe": "1Min",
        "start": start_date.isoformat() + "Z",
        "end": end_date.isoformat() + "Z",
        "limit": 10000,
        "adjustment": "raw",
        "feed": "iex"  # Free tier
    }
    
    print(f"Fetching bars from Alpaca API...")
    print(f"  Symbol: {symbol}")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return []
    
    data = response.json()
    bars = data.get("bars", [])
    
    print(f"✅ Fetched {len(bars)} bars from Alpaca")
    
    return bars

def insert_bars(conn, symbol, bars):
    """Insert bars into database."""
    cur = conn.cursor()
    
    # Get or create symbol
    cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
    row = cur.fetchone()
    
    if row:
        symbol_id = row[0]
    else:
        cur.execute("INSERT INTO symbols (symbol) VALUES (%s) RETURNING id", (symbol,))
        symbol_id = cur.fetchone()[0]
        conn.commit()
    
    # Insert bars
    inserted = 0
    skipped = 0
    
    for bar in bars:
        try:
            # Parse timestamp (Alpaca returns ISO8601 in UTC)
            timestamp = datetime.fromisoformat(bar['t'].replace('Z', '+00:00'))
            
            cur.execute("""
                INSERT INTO candles (time, symbol_id, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol_id) DO NOTHING
            """, (
                timestamp,
                symbol_id,
                float(bar['o']),
                float(bar['h']),
                float(bar['l']),
                float(bar['c']),
                int(bar['v'])
            ))
            
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"Error inserting bar: {e}")
            continue
    
    conn.commit()
    return inserted, skipped

def main():
    # Get credentials from environment
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    if not api_key or not secret_key:
        print("❌ Error: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        print("   Set them in .env file")
        sys.exit(1)
    
    # Parse arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    print("🔄 Backfilling real historical data from Alpaca")
    print("")
    
    # Calculate date range (last N trading days)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    
    # Fetch bars from Alpaca
    bars = fetch_alpaca_bars(symbol, start_date, end_date, api_key, secret_key)
    
    if not bars:
        print("❌ No data received from Alpaca")
        sys.exit(1)
    
    # Connect to database
    conn = get_db_conn()
    
    # Insert bars
    inserted, skipped = insert_bars(conn, symbol, bars)
    
    print("")
    print(f"✅ Backfill complete!")
    print(f"   Inserted: {inserted} candles")
    print(f"   Skipped: {skipped} (already existed)")
    print(f"   Symbol: {symbol}")
    
    if bars:
        prices = [float(b['c']) for b in bars]
        print(f"   Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        print(f"   Time range: {bars[0]['t']} to {bars[-1]['t']}")
    
    print("")
    print("Next steps:")
    print("  1. Refresh dashboard: http://127.0.0.1:8002/dashboard")
    print("  2. Wait 60s for volume profile calculation")
    print("")

if __name__ == "__main__":
    main()
