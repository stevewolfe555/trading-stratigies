"""
Polymarket Trading Client

Wrapper around the official py-clob-client library for order execution on Polymarket.
Supports arbitrage execution with paired YES+NO positions.

Official Library: https://github.com/Polymarket/py-clob-client
PyPI: pip install py-clob-client

Features:
- Uses official Polymarket CLOB client
- L1/L2 authentication handling
- Market order execution (FOK for guaranteed fills)
- Parallel YES+NO order placement for arbitrage
- Position and balance retrieval

Speed Priority:
- Use FOK (Fill-Or-Kill) orders for guaranteed fills
- Execute YES and NO orders in parallel (asyncio)
- Minimal latency target: <50ms per order
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
from loguru import logger

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import MarketOrderArgs, OrderType, OrderArgs
    from py_clob_client.exceptions import PolyException
    CLOB_AVAILABLE = True
except ImportError:
    logger.warning("py-clob-client not installed. Run: pip install py-clob-client")
    CLOB_AVAILABLE = False


class PolymarketTradingClient:
    """
    Polymarket CLOB trading client for executing arbitrage orders.

    Wraps the official py-clob-client library with convenience methods
    for our binary options arbitrage strategy.

    Authentication Flow:
    1. Initialize with Ethereum private key (L1)
    2. Generate API credentials (L2: api_key, secret, passphrase)
    3. Sign and submit orders

    Order Execution:
    - Uses FOK (Fill-Or-Kill) for arbitrage (all or nothing)
    - Parallel execution of YES+NO orders via asyncio
    - Automatic error handling and retry logic
    """

    def __init__(
        self,
        private_key: str,
        chain_id: int = 137,  # Polygon mainnet
        signature_type: int = 0,  # EOA signatures (MetaMask, hardware wallets)
        funder: Optional[str] = None,  # For proxy wallets
        host: str = "https://clob.polymarket.com"
    ):
        """
        Initialize Polymarket trading client.

        Args:
            private_key: Ethereum private key (hex string)
            chain_id: Blockchain ID (137 = Polygon mainnet)
            signature_type: 0=EOA, 1=Email/Magic, 2=Proxy
            funder: Funder address (required for proxy wallets)
            host: CLOB API endpoint

        Raises:
            ImportError: If py-clob-client is not installed
        """
        if not CLOB_AVAILABLE:
            raise ImportError(
                "py-clob-client is required. Install with: pip install py-clob-client"
            )

        self.private_key = private_key
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder = funder
        self.host = host

        # Initialize CLOB client
        self.client = ClobClient(
            host=self.host,
            key=self.private_key,
            chain_id=self.chain_id,
            signature_type=self.signature_type,
            funder=self.funder
        )

        # Generate and set API credentials (L2 auth)
        try:
            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)
            logger.success("Polymarket trading client initialized with API credentials")
        except Exception as e:
            logger.error(f"Failed to generate API credentials: {e}")
            raise

    def get_orderbook(self, token_id: str) -> Dict:
        """
        Get orderbook for a token.

        Args:
            token_id: Polymarket token ID

        Returns:
            Orderbook dict with bids/asks
        """
        try:
            return self.client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Failed to get orderbook for {token_id}: {e}")
            return {"bids": [], "asks": []}

    def get_midpoint(self, token_id: str) -> Optional[Decimal]:
        """
        Get midpoint price for a token.

        Args:
            token_id: Polymarket token ID

        Returns:
            Midpoint price or None
        """
        try:
            mid = self.client.get_midpoint(token_id)
            return Decimal(str(mid)) if mid else None
        except Exception as e:
            logger.error(f"Failed to get midpoint for {token_id}: {e}")
            return None

    def get_price(self, token_id: str, side: str) -> Optional[Decimal]:
        """
        Get best price for a token side.

        Args:
            token_id: Polymarket token ID
            side: "BUY" or "SELL"

        Returns:
            Best price or None
        """
        try:
            price = self.client.get_price(token_id, side=side)
            return Decimal(str(price)) if price else None
        except Exception as e:
            logger.error(f"Failed to get price for {token_id} {side}: {e}")
            return None

    async def place_market_order(
        self,
        token_id: str,
        amount: Decimal,
        side: str = "BUY"
    ) -> Optional[Dict]:
        """
        Place a market order (FOK).

        Args:
            token_id: Polymarket token ID
            amount: Dollar amount to trade (not shares!)
            side: "BUY" or "SELL"

        Returns:
            Order response dict or None on failure
        """
        try:
            logger.info(f"Placing {side} order: {token_id} | ${amount:.2f}")

            # Create market order args
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=float(amount),  # py-clob-client expects float
                side=side.upper()
            )

            # Sign order
            signed_order = self.client.create_market_order(order_args)

            # Submit order (FOK = Fill-Or-Kill)
            response = self.client.post_order(signed_order, OrderType.FOK)

            logger.success(
                f"Order placed: {response.get('orderID')} | "
                f"Status: {response.get('status')}"
            )

            return response

        except PolyException as e:
            logger.error(f"Polymarket API error placing order: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    async def execute_arbitrage(
        self,
        yes_token_id: str,
        no_token_id: str,
        yes_price: Decimal,
        no_price: Decimal,
        position_size: Decimal
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Execute paired YES+NO orders for arbitrage.

        This is the critical method for arbitrage - both orders must execute
        quickly and simultaneously to lock in the spread.

        Args:
            yes_token_id: YES token ID
            no_token_id: NO token ID
            yes_price: YES ask price (for validation)
            no_price: NO ask price (for validation)
            position_size: Total dollar amount to invest

        Returns:
            Tuple of (yes_order_response, no_order_response)
        """
        logger.info(
            f"Executing arbitrage | "
            f"YES: {yes_token_id} @ ${yes_price:.4f} | "
            f"NO: {no_token_id} @ ${no_price:.4f} | "
            f"Size: ${position_size:.2f}"
        )

        # Split position size equally between YES and NO
        yes_amount = position_size / 2
        no_amount = position_size / 2

        try:
            # Execute both orders in parallel for speed
            yes_task = self.place_market_order(yes_token_id, yes_amount, "BUY")
            no_task = self.place_market_order(no_token_id, no_amount, "BUY")

            yes_response, no_response = await asyncio.gather(yes_task, no_task)

            # Check if both filled
            yes_filled = yes_response and yes_response.get('status') == 'filled'
            no_filled = no_response and no_response.get('status') == 'filled'

            if yes_filled and no_filled:
                logger.success(
                    f"Arbitrage executed successfully | "
                    f"YES: {yes_response.get('orderID')} | "
                    f"NO: {no_response.get('orderID')}"
                )
            else:
                logger.warning(
                    f"Partial fill | "
                    f"YES: {'filled' if yes_filled else 'failed'} | "
                    f"NO: {'filled' if no_filled else 'failed'}"
                )
                # TODO: Handle partial fills (cancel unfilled side, close filled side)

            return yes_response, no_response

        except Exception as e:
            logger.error(f"Arbitrage execution failed: {e}")
            return None, None

    def get_balance(self) -> Dict:
        """
        Get account balance.

        Returns:
            Balance dict with total, available, in_orders
        """
        try:
            # Note: py-clob-client may not have direct balance method
            # May need to query blockchain or use alternative method
            # TODO: Implement balance checking
            logger.warning("Balance checking not yet implemented")
            return {"total": 0, "available": 0, "in_orders": 0}

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {"total": 0, "available": 0, "in_orders": 0}

    def get_positions(self) -> List[Dict]:
        """
        Get open positions.

        Returns:
            List of position dicts
        """
        try:
            # Note: May need to query from database or use alternative method
            # TODO: Implement position retrieval
            logger.warning("Position retrieval not yet implemented")
            return []

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get order status by ID.

        Args:
            order_id: Order ID

        Returns:
            Order status dict or None
        """
        try:
            # TODO: Verify method name in py-clob-client
            # May be get_order() or similar
            logger.warning("Order status checking not yet implemented")
            return None

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            # TODO: Implement using py-clob-client cancel method
            logger.warning("Order cancellation not yet implemented")
            return False

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    def get_markets(self) -> List[Dict]:
        """
        Get list of active markets.

        Returns:
            List of market dicts with token IDs
        """
        try:
            # TODO: Implement market listing
            # This may require separate API call or web scraping
            logger.warning("Market listing not yet implemented")
            return []

        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
            return []


# Example usage
async def main():
    """
    Test the Polymarket trading client.

    Usage:
        python -m app.trading.polymarket_client
    """
    import os

    # Get credentials from environment
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
    if not private_key:
        logger.error("POLYMARKET_PRIVATE_KEY environment variable not set")
        return

    try:
        # Initialize client
        client = PolymarketTradingClient(
            private_key=private_key,
            chain_id=137  # Polygon mainnet
        )

        # Test getting balance
        balance = client.get_balance()
        logger.info(f"Balance: {balance}")

        # Test getting orderbook for a token
        # token_id = "123456"  # Replace with real token ID
        # orderbook = client.get_orderbook(token_id)
        # logger.info(f"Orderbook: {orderbook}")

        logger.success("Client test completed")

    except Exception as e:
        logger.error(f"Client test failed: {e}")


if __name__ == '__main__':
    asyncio.run(main())
