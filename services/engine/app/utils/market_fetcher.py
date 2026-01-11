"""
Polymarket Market Fetcher

Fetches active markets from Polymarket and populates the binary_markets table.
Focuses on political and sports markets (zero fees!) and excludes 15-minute crypto markets.

Usage:
    python -m app.utils.market_fetcher --limit 50 --categories politics sports

Features:
- Fetches markets via Polymarket public API
- Filters by category (politics, sports, etc.)
- Extracts YES/NO token IDs
- Populates symbols and binary_markets tables
- Updates existing markets if they already exist
"""

import argparse
import json
import requests
import psycopg2
from datetime import datetime, timezone
from typing import List, Dict, Optional
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()


class PolymarketMarketFetcher:
    """
    Fetches and stores Polymarket markets in database.

    Polymarket API endpoints:
    - https://gamma-api.polymarket.com/markets - Get all markets
    - https://clob.polymarket.com/markets - CLOB market data
    """

    def __init__(self, db_conn):
        """
        Initialize market fetcher.

        Args:
            db_conn: PostgreSQL database connection
        """
        self.conn = db_conn
        # Try the public Gamma API first
        self.api_base = "https://gamma-api.polymarket.com"

    def fetch_markets(
        self,
        limit: int = 50,
        categories: Optional[List[str]] = None,
        active_only: bool = True
    ) -> List[Dict]:
        """
        Fetch markets from Polymarket API.

        Args:
            limit: Maximum number of markets to fetch
            categories: Filter by categories (e.g., ['politics', 'sports'])
            active_only: Only fetch active markets

        Returns:
            List of market dicts
        """
        try:
            logger.info(f"Fetching markets from Polymarket API (limit: {limit})")

            # Try Gamma API endpoint
            url = f"{self.api_base}/markets"
            params = {
                "limit": limit,
                "offset": 0,
            }

            if active_only:
                params["active"] = "true"
                params["closed"] = "false"  # Only fetch non-closed markets

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            markets = response.json()
            logger.info(f"Fetched {len(markets)} markets")

            # Filter out closed markets
            markets = [
                m for m in markets
                if not m.get('closed', False)
            ]
            logger.info(f"After filtering closed markets: {len(markets)} markets")

            # Filter by category if specified
            if categories:
                markets = [
                    m for m in markets
                    if m.get('category', '').lower() in [c.lower() for c in categories]
                ]
                logger.info(f"Filtered to {len(markets)} markets in categories: {categories}")

            # Filter out 15-minute crypto markets (they have fees!)
            markets = [
                m for m in markets
                if not self._is_short_term_crypto(m)
            ]
            logger.info(f"After filtering short-term crypto: {len(markets)} markets")

            return markets

        except requests.RequestException as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def _is_short_term_crypto(self, market: Dict) -> bool:
        """
        Check if market is a short-term crypto market (has fees).

        Args:
            market: Market dict

        Returns:
            True if short-term crypto market
        """
        # Check if it's crypto category
        category = market.get('category', '').lower()
        if category != 'crypto':
            return False

        # Check if it's 15-minute or short duration
        # This is a heuristic - may need adjustment
        question = market.get('question', '').lower()
        if '15 min' in question or '15-min' in question:
            return True

        # Check end date - if < 1 hour from now, it's short-term
        end_date_str = market.get('endDate')
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                hours_until_end = (end_date - datetime.now(timezone.utc)).total_seconds() / 3600
                if hours_until_end < 1:
                    return True
            except:
                pass

        return False

    def populate_database(self, markets: List[Dict]) -> int:
        """
        Populate symbols and binary_markets tables with market data.

        Args:
            markets: List of market dicts from API

        Returns:
            Number of markets successfully added/updated
        """
        added_count = 0
        cur = self.conn.cursor()

        for market in markets:
            try:
                # Extract market data
                # IMPORTANT: Use conditionId (hex hash) not id (numeric)
                # WebSocket messages use conditionId in the 'market' field
                market_id = market.get('conditionId') or market.get('id')
                question = market.get('question') or market.get('title', 'Unknown')
                description = market.get('description', '')
                category = market.get('category', 'uncategorized')
                end_date_str = market.get('endDate') or market.get('end_date')

                # Get token IDs for YES and NO from clobTokenIds
                clob_token_ids_str = market.get('clobTokenIds', '[]')
                yes_token_id = None
                no_token_id = None

                try:
                    # clobTokenIds is a JSON string containing an array
                    clob_token_ids = json.loads(clob_token_ids_str)
                    if len(clob_token_ids) >= 2:
                        # First token is YES, second is NO
                        yes_token_id = clob_token_ids[0]
                        no_token_id = clob_token_ids[1]
                except (json.JSONDecodeError, IndexError, TypeError):
                    logger.warning(f"Failed to parse clobTokenIds for market: {question[:50]}")

                if not market_id or not yes_token_id or not no_token_id:
                    logger.warning(f"Skipping market with missing data: {question[:50]}")
                    continue

                # Parse end date
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except:
                    # Default to 30 days from now if can't parse
                    from datetime import timedelta
                    end_date = datetime.now(timezone.utc) + timedelta(days=30)

                # Create symbol for this market
                symbol = self._create_symbol(market_id, question)

                # Insert or update symbol
                cur.execute("""
                    INSERT INTO symbols (symbol, name, exchange, asset_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE
                    SET name = EXCLUDED.name
                    RETURNING id
                """, (symbol, question[:100], 'POLYMARKET', 'binary_option'))

                symbol_id = cur.fetchone()[0]

                # Insert or update binary_market
                cur.execute("""
                    INSERT INTO binary_markets (
                        symbol_id,
                        market_id,
                        yes_token_id,
                        no_token_id,
                        question,
                        description,
                        category,
                        end_date,
                        status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'active'
                    )
                    ON CONFLICT (market_id) DO UPDATE
                    SET question = EXCLUDED.question,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        end_date = EXCLUDED.end_date,
                        yes_token_id = EXCLUDED.yes_token_id,
                        no_token_id = EXCLUDED.no_token_id,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                """, (
                    symbol_id,
                    market_id,
                    yes_token_id,
                    no_token_id,
                    question,
                    description[:1000] if description else None,
                    category,
                    end_date
                ))

                added_count += 1
                logger.debug(f"Added market: {question[:50]}...")

            except Exception as e:
                logger.error(f"Error adding market '{question[:50]}': {e}")
                continue

        self.conn.commit()
        logger.success(f"Successfully added/updated {added_count} markets")
        return added_count

    def _create_symbol(self, market_id: str, question: str) -> str:
        """
        Create a symbol from market ID and question.

        Args:
            market_id: Polymarket market ID
            question: Market question

        Returns:
            Symbol string (e.g., "PRES2024-TRUMP")
        """
        # Extract key words from question
        words = question.upper().split()

        # Common word removals
        stop_words = {'WILL', 'THE', 'BE', 'A', 'AN', 'IN', 'ON', 'AT', 'TO', 'FOR', 'OF', 'AND', 'OR'}
        key_words = [w for w in words if w not in stop_words and len(w) > 2]

        # Take first 2-3 key words and join with dash
        if len(key_words) >= 2:
            symbol = '-'.join(key_words[:3])[:30]  # Limit to 30 chars
        else:
            # Fallback to market_id prefix
            symbol = f"PM-{market_id[:10]}"

        return symbol

    def get_token_ids_for_market(self, market_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get YES and NO token IDs for a market.

        Args:
            market_id: Polymarket market ID

        Returns:
            Tuple of (yes_token_id, no_token_id)
        """
        try:
            url = f"{self.api_base}/markets/{market_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            market = response.json()
            tokens = market.get('tokens', [])

            yes_token_id = None
            no_token_id = None

            for token in tokens:
                outcome = token.get('outcome', '').upper()
                token_id = token.get('token_id') or token.get('tokenId')
                if outcome == 'YES':
                    yes_token_id = token_id
                elif outcome == 'NO':
                    no_token_id = token_id

            return yes_token_id, no_token_id

        except Exception as e:
            logger.error(f"Failed to get token IDs for market {market_id}: {e}")
            return None, None


def main():
    """
    Main entry point for market fetcher.

    Usage:
        python -m app.utils.market_fetcher --limit 50 --categories politics sports
    """
    parser = argparse.ArgumentParser(description='Fetch Polymarket markets and populate database')
    parser.add_argument('--limit', type=int, default=50, help='Maximum markets to fetch')
    parser.add_argument('--categories', nargs='+', default=['politics', 'sports'],
                       help='Categories to fetch (e.g., politics sports)')
    parser.add_argument('--all-categories', action='store_true',
                       help='Fetch all categories (ignore --categories)')

    args = parser.parse_args()

    # Database connection
    db_conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'trading'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )

    try:
        fetcher = PolymarketMarketFetcher(db_conn)

        # Fetch markets
        categories = None if args.all_categories else args.categories
        markets = fetcher.fetch_markets(
            limit=args.limit,
            categories=categories,
            active_only=True
        )

        if not markets:
            logger.warning("No markets fetched")
            return

        # Populate database
        count = fetcher.populate_database(markets)

        logger.success(f"Market fetch complete: {count} markets added/updated")

    except Exception as e:
        logger.error(f"Market fetcher failed: {e}")
        raise
    finally:
        db_conn.close()


if __name__ == '__main__':
    main()
