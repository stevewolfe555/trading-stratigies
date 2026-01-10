"""
Provider Router

Routes symbols to appropriate data providers based on market.
Supports multiple providers simultaneously (Alpaca, IG, etc.)
"""

from typing import Optional, Dict, Any
from loguru import logger


class ProviderRouter:
    """
    Route symbols to appropriate data providers.
    
    Configuration:
    - US symbols (no suffix) → Alpaca
    - LSE symbols (.L suffix) → IG
    - European indices (^) → IG
    - Forex → IG
    
    Can be configured via database or config file.
    """
    
    def __init__(self, db_conn=None):
        """
        Initialize provider router.
        
        Args:
            db_conn: Database connection (optional)
        """
        self.conn = db_conn
        self.providers = {}
        self.symbol_routing = {}
        
        logger.info("Provider router initialized")
    
    def register_provider(self, name: str, provider_instance: Any):
        """
        Register a data provider.
        
        Args:
            name: Provider name ('alpaca', 'ig', etc.)
            provider_instance: Provider object with get_market_data() method
        """
        self.providers[name] = provider_instance
        logger.info(f"Registered provider: {name}")
    
    def load_routing_config(self):
        """
        Load symbol routing from database.
        
        Table: symbol_providers
        Columns: symbol, provider, market, level, epic
        """
        if not self.conn:
            logger.warning("No database connection, using default routing")
            return
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT symbol, provider, market, level, epic
                FROM symbol_providers
                WHERE active = true
            """)
            
            count = 0
            for row in cur.fetchall():
                symbol, provider, market, level, epic = row
                self.symbol_routing[symbol] = {
                    'provider': provider,
                    'market': market,
                    'level': level,
                    'epic': epic
                }
                count += 1
            
            logger.info(f"Loaded routing config for {count} symbols")
            
        except Exception as e:
            logger.error(f"Error loading routing config: {e}")
    
    def get_provider_for_symbol(self, symbol: str) -> Optional[Any]:
        """
        Get the provider for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Provider instance or None
        """
        # Check explicit routing first
        if symbol in self.symbol_routing:
            provider_name = self.symbol_routing[symbol]['provider']
            provider = self.providers.get(provider_name)
            if provider:
                return provider
        
        # Default routing based on symbol format
        # US symbols: no suffix (AAPL, MSFT, etc.)
        if '.' not in symbol and not symbol.startswith('^'):
            return self.providers.get('alpaca')
        
        # LSE symbols: .L suffix (VOD.L, BP.L, etc.)
        if symbol.endswith('.L'):
            return self.providers.get('ig')
        
        # European indices: ^ prefix (^FTSE, ^GDAXI, etc.)
        if symbol.startswith('^'):
            return self.providers.get('ig')
        
        # Forex: 6 characters, no dots (GBPUSD, EURUSD, etc.)
        if len(symbol) == 6 and symbol.isalpha():
            return self.providers.get('ig')

        # Polymarket binary options
        # Format: PRES2024-TRUMP, BTC-100K-Q1, etc.
        # Heuristic: Contains dash and longer than typical forex pairs
        if '-' in symbol and len(symbol) > 6:
            return self.providers.get('polymarket')

        logger.warning(f"No provider found for symbol: {symbol}")
        return None
    
    def get_epic_for_symbol(self, symbol: str) -> Optional[str]:
        """
        Get IG EPIC for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            IG EPIC or None
        """
        if symbol in self.symbol_routing:
            return self.symbol_routing[symbol].get('epic')
        
        # Try to get from common EPICs
        from .providers.ig_provider import get_epic_for_symbol
        return get_epic_for_symbol(symbol)
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data for a symbol using correct provider.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Market data dict or None
        """
        provider = self.get_provider_for_symbol(symbol)
        
        if not provider:
            logger.warning(f"No provider available for {symbol}")
            return None
        
        try:
            # For IG provider, need to convert symbol to EPIC
            if hasattr(provider, 'get_market_details'):  # IG provider
                epic = self.get_epic_for_symbol(symbol)
                if not epic:
                    logger.warning(f"No EPIC found for {symbol}")
                    return None
                
                data = provider.get_market_details(epic)
                if data:
                    data['symbol'] = symbol  # Add original symbol
                return data
            
            # For other providers (Alpaca, etc.)
            elif hasattr(provider, 'get_market_data'):
                return provider.get_market_data(symbol)
            
            else:
                logger.error(f"Provider has no get_market_data method")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def get_order_book(self, symbol: str) -> Optional[Dict]:
        """
        Get Level 2 order book data for a symbol.
        
        Only works with providers that support Level 2 (IG).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Order book dict or None
        """
        provider = self.get_provider_for_symbol(symbol)
        
        if not provider:
            logger.warning(f"No provider available for {symbol}")
            return None
        
        # Check if provider supports Level 2
        if not hasattr(provider, 'get_order_book'):
            logger.warning(f"Provider for {symbol} does not support Level 2 data")
            return None
        
        try:
            epic = self.get_epic_for_symbol(symbol)
            if not epic:
                logger.warning(f"No EPIC found for {symbol}")
                return None
            
            data = provider.get_order_book(epic)
            if data:
                data['symbol'] = symbol  # Add original symbol
            return data
            
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            return None
    
    def get_routing_info(self, symbol: str) -> Dict:
        """
        Get routing information for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Routing info dict
        """
        provider = self.get_provider_for_symbol(symbol)
        
        info = {
            'symbol': symbol,
            'provider': None,
            'market': 'UNKNOWN',
            'level': 1,
            'epic': None,
            'supports_level2': False
        }
        
        if symbol in self.symbol_routing:
            config = self.symbol_routing[symbol]
            info.update({
                'provider': config['provider'],
                'market': config['market'],
                'level': config['level'],
                'epic': config['epic']
            })
        elif provider:
            # Infer from provider
            if provider == self.providers.get('alpaca'):
                info['provider'] = 'alpaca'
                info['market'] = 'US'
            elif provider == self.providers.get('ig'):
                info['provider'] = 'ig'
                info['market'] = 'LSE' if symbol.endswith('.L') else 'OTHER'
                info['level'] = 2
                info['epic'] = self.get_epic_for_symbol(symbol)
        
        if provider and hasattr(provider, 'get_order_book'):
            info['supports_level2'] = True
        
        return info
    
    def get_all_symbols(self) -> Dict[str, str]:
        """
        Get all configured symbols and their providers.
        
        Returns:
            Dict of {symbol: provider_name}
        """
        result = {}
        for symbol, config in self.symbol_routing.items():
            result[symbol] = config['provider']
        return result
    
    def add_symbol_routing(
        self,
        symbol: str,
        provider: str,
        market: str,
        level: int = 1,
        epic: Optional[str] = None
    ):
        """
        Add or update symbol routing configuration.
        
        Args:
            symbol: Stock symbol
            provider: Provider name
            market: Market name
            level: Data level (1 or 2)
            epic: IG EPIC (for IG provider)
        """
        self.symbol_routing[symbol] = {
            'provider': provider,
            'market': market,
            'level': level,
            'epic': epic
        }
        
        # Also save to database if available
        if self.conn:
            try:
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT INTO symbol_providers (symbol, provider, market, level, epic, active)
                    VALUES (%s, %s, %s, %s, %s, true)
                    ON CONFLICT (symbol) DO UPDATE
                    SET provider = EXCLUDED.provider,
                        market = EXCLUDED.market,
                        level = EXCLUDED.level,
                        epic = EXCLUDED.epic,
                        active = true
                """, (symbol, provider, market, level, epic))
                self.conn.commit()
                logger.info(f"Added routing: {symbol} → {provider} ({market})")
            except Exception as e:
                logger.error(f"Error saving routing to database: {e}")
