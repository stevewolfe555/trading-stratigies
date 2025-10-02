#!/usr/bin/env python3
"""
Download historical data from Alpaca IEX feed for backtesting.

IEX (Investors Exchange):
- Free tier (no subscription needed)
- ~2.5% market volume
- Sufficient for strategy validation
- Same data source as live trading

Usage:
    python scripts/backfill-alpaca-iex.py --years 1 --symbols AAPL,MSFT
    python scripts/backfill-alpaca-iex.py --years 7 --all-symbols
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
import requests
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

# Alpaca API configuration
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = 'https://data.alpaca.markets'

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),  # 'db' when running in Docker
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'trading'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# Default symbols (30 US stocks)
DEFAULT_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD',
    'NFLX', 'INTC', 'CSCO', 'ORCL', 'CRM', 'ADBE', 'AVGO',
    'JPM', 'BAC', 'WFC', 'GS', 'MS',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK',
    'XOM', 'CVX',
    'SPY', 'QQQ', 'DIA'
]


class AlpacaIEXDownloader:
    """Download historical data from Alpaca IEX feed."""
    
    def __init__(self):
        """Initialize downloader."""
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        
        self.headers = {
            'APCA-API-KEY-ID': ALPACA_API_KEY,
            'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
        }
        
        # Connect to database
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        logger.info("Connected to database")
    
    def get_symbol_id(self, symbol: str) -> int:
        """Get or create symbol ID."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM symbols WHERE symbol = %s", (symbol,))
            result = cur.fetchone()
            
            if result:
                return result[0]
            
            # Create symbol
            cur.execute(
                "INSERT INTO symbols (symbol, name) VALUES (%s, %s) RETURNING id",
                (symbol, symbol)
            )
            symbol_id = cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"Created symbol: {symbol} (ID: {symbol_id})")
            return symbol_id
    
    def download_bars(self, symbol: str, start_date: str, end_date: str, timeframe: str = '1Min'):
        """
        Download bars from Alpaca IEX feed.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Bar timeframe (1Min, 5Min, 1Hour, 1Day)
        """
        logger.info(f"Downloading {symbol} from {start_date} to {end_date} ({timeframe})")
        
        symbol_id = self.get_symbol_id(symbol)
        
        # Alpaca API endpoint
        url = f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/bars"
        
        params = {
            'start': start_date,
            'end': end_date,
            'timeframe': timeframe,
            'limit': 10000,  # Max per request
            'feed': 'iex'  # Use IEX feed (free)
        }
        
        all_bars = []
        page_token = None
        page = 1
        
        while True:
            if page_token:
                params['page_token'] = page_token
            
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                bars = data.get('bars', [])
                if not bars:
                    break
                
                all_bars.extend(bars)
                logger.info(f"  Page {page}: {len(bars)} bars (total: {len(all_bars)})")
                
                # Check for next page
                page_token = data.get('next_page_token')
                if not page_token:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error downloading {symbol}: {e}")
                break
        
        if all_bars:
            self.insert_bars(symbol_id, all_bars)
            logger.success(f"✅ {symbol}: {len(all_bars)} bars inserted")
        else:
            logger.warning(f"⚠️  {symbol}: No data found")
    
    def insert_bars(self, symbol_id: int, bars: list):
        """Insert bars into database."""
        if not bars:
            return
        
        # Prepare data for batch insert
        data = [
            (
                symbol_id,
                bar['t'],  # timestamp (already in UTC)
                float(bar['o']),
                float(bar['h']),
                float(bar['l']),
                float(bar['c']),
                int(bar['v'])
            )
            for bar in bars
        ]
        
        # Batch insert with ON CONFLICT DO NOTHING (skip duplicates)
        with self.conn.cursor() as cur:
            execute_batch(
                cur,
                """
                INSERT INTO candles (symbol_id, time, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol_id, time) DO NOTHING
                """,
                data,
                page_size=1000
            )
        
        self.conn.commit()
    
    def download_multiple_symbols(self, symbols: list, years: int, timeframe: str = '1Min'):
        """Download data for multiple symbols."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📥 Downloading {len(symbols)} symbols")
        logger.info(f"📅 Date range: {start_str} to {end_str} ({years} years)")
        logger.info(f"⏱️  Timeframe: {timeframe}")
        logger.info(f"📡 Feed: IEX (free tier)")
        logger.info("")
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] Processing {symbol}...")
            self.download_bars(symbol, start_str, end_str, timeframe)
            logger.info("")
        
        logger.success(f"✅ Download complete! {len(symbols)} symbols processed")
    
    def get_stats(self):
        """Get database statistics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    s.symbol,
                    COUNT(*) as bar_count,
                    MIN(c.time) as first_bar,
                    MAX(c.time) as last_bar
                FROM candles c
                JOIN symbols s ON c.symbol_id = s.id
                GROUP BY s.symbol
                ORDER BY s.symbol
            """)
            
            results = cur.fetchall()
            
            if results:
                logger.info("📊 Database Statistics:")
                logger.info("")
                for symbol, count, first, last in results:
                    days = (last - first).days if first and last else 0
                    logger.info(f"  {symbol:6s}: {count:,} bars | {days} days | {first} to {last}")
                
                total_bars = sum(r[1] for r in results)
                logger.info("")
                logger.info(f"  Total: {total_bars:,} bars across {len(results)} symbols")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Download historical data from Alpaca IEX feed')
    parser.add_argument('--years', type=float, default=1.0, help='Years of history to download (default: 1)')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols (e.g., AAPL,MSFT,GOOGL)')
    parser.add_argument('--all-symbols', action='store_true', help='Download all 30 default symbols')
    parser.add_argument('--timeframe', type=str, default='1Min', choices=['1Min', '5Min', '15Min', '1Hour', '1Day'], help='Bar timeframe')
    parser.add_argument('--stats', action='store_true', help='Show database statistics only')
    
    args = parser.parse_args()
    
    downloader = AlpacaIEXDownloader()
    
    try:
        if args.stats:
            downloader.get_stats()
            return
        
        # Determine symbols
        if args.all_symbols:
            symbols = DEFAULT_SYMBOLS
        elif args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(',')]
        else:
            logger.error("Please specify --symbols or --all-symbols")
            sys.exit(1)
        
        # Download data
        downloader.download_multiple_symbols(symbols, args.years, args.timeframe)
        
        # Show stats
        logger.info("")
        downloader.get_stats()
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        downloader.close()


if __name__ == '__main__':
    main()
