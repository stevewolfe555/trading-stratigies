"""
Strategy Manager

Manages trading strategies with database-backed configuration.
Allows enabling/disabling strategies per symbol and adjusting parameters without restart.
"""

from typing import Dict, List, Optional
from loguru import logger
import json


class StrategyManager:
    """
    Manages trading strategy configurations.
    
    Features:
    - Load strategy configs from database
    - Enable/disable strategies per symbol
    - Adjust parameters dynamically
    - Cache configs for performance
    """
    
    def __init__(self, db_conn):
        """
        Initialize strategy manager.
        
        Args:
            db_conn: Database connection
        """
        self.conn = db_conn
        self.configs_cache = {}
        self.last_reload = None
        
        logger.info("Strategy Manager initialized")
    
    def load_all_configs(self) -> Dict:
        """
        Load all strategy configurations from database.
        
        Returns:
            Dict of {symbol: [strategy_configs]}
        """
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT 
                    s.symbol,
                    sc.strategy_name,
                    sc.enabled,
                    sc.parameters,
                    sc.risk_per_trade_pct,
                    sc.max_positions
                FROM strategy_configs sc
                JOIN symbols s ON sc.symbol_id = s.id
                WHERE sc.enabled = true
                ORDER BY s.symbol, sc.strategy_name
            """)
            
            configs = {}
            for row in cur.fetchall():
                symbol, strategy_name, enabled, parameters, risk_pct, max_pos = row
                
                if symbol not in configs:
                    configs[symbol] = []
                
                configs[symbol].append({
                    'strategy_name': strategy_name,
                    'enabled': enabled,
                    'parameters': parameters if isinstance(parameters, dict) else json.loads(parameters),
                    'risk_per_trade_pct': float(risk_pct),
                    'max_positions': int(max_pos)
                })
            
            self.configs_cache = configs
            logger.info(f"Loaded configs for {len(configs)} symbols")
            
            return configs
            
        except Exception as e:
            logger.error(f"Error loading strategy configs: {e}")
            return {}
    
    def get_strategy_config(self, symbol: str, strategy_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific strategy and symbol.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name (e.g., 'auction_market')
            
        Returns:
            Strategy config dict or None
        """
        # Reload if cache is empty
        if not self.configs_cache:
            self.load_all_configs()
        
        symbol_configs = self.configs_cache.get(symbol, [])
        
        for config in symbol_configs:
            if config['strategy_name'] == strategy_name:
                return config
        
        return None
    
    def is_strategy_enabled(self, symbol: str, strategy_name: str) -> bool:
        """
        Check if a strategy is enabled for a symbol.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            
        Returns:
            True if enabled, False otherwise
        """
        config = self.get_strategy_config(symbol, strategy_name)
        return config is not None and config.get('enabled', False)
    
    def get_strategy_parameter(self, symbol: str, strategy_name: str, param_name: str, default=None):
        """
        Get a specific parameter value for a strategy.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            param_name: Parameter name
            default: Default value if not found
            
        Returns:
            Parameter value or default
        """
        config = self.get_strategy_config(symbol, strategy_name)
        
        if not config:
            return default
        
        parameters = config.get('parameters', {})
        return parameters.get(param_name, default)
    
    def update_strategy_config(
        self,
        symbol: str,
        strategy_name: str,
        enabled: Optional[bool] = None,
        parameters: Optional[Dict] = None,
        risk_per_trade_pct: Optional[float] = None
    ) -> bool:
        """
        Update strategy configuration.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            enabled: Enable/disable strategy
            parameters: Strategy parameters
            risk_per_trade_pct: Risk percentage
            
        Returns:
            True if successful
        """
        try:
            cur = self.conn.cursor()
            
            # Build update query
            updates = []
            values = []
            
            if enabled is not None:
                updates.append("enabled = %s")
                values.append(enabled)
            
            if parameters is not None:
                updates.append("parameters = %s::jsonb")
                values.append(json.dumps(parameters))
            
            if risk_per_trade_pct is not None:
                updates.append("risk_per_trade_pct = %s")
                values.append(risk_per_trade_pct)
            
            if not updates:
                return False
            
            updates.append("updated_at = NOW()")
            
            # Add WHERE clause values
            values.extend([symbol, strategy_name])
            
            query = f"""
                UPDATE strategy_configs sc
                SET {', '.join(updates)}
                FROM symbols s
                WHERE sc.symbol_id = s.id
                    AND s.symbol = %s
                    AND sc.strategy_name = %s
            """
            
            cur.execute(query, values)
            self.conn.commit()
            
            # Reload cache
            self.load_all_configs()
            
            logger.info(f"Updated config for {symbol}/{strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy config: {e}")
            self.conn.rollback()
            return False
    
    def enable_strategy(self, symbol: str, strategy_name: str) -> bool:
        """
        Enable a strategy for a symbol.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            
        Returns:
            True if successful
        """
        return self.update_strategy_config(symbol, strategy_name, enabled=True)
    
    def disable_strategy(self, symbol: str, strategy_name: str) -> bool:
        """
        Disable a strategy for a symbol.
        
        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            
        Returns:
            True if successful
        """
        return self.update_strategy_config(symbol, strategy_name, enabled=False)
    
    def get_enabled_symbols(self, strategy_name: str) -> List[str]:
        """
        Get all symbols with a strategy enabled.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            List of symbols
        """
        if not self.configs_cache:
            self.load_all_configs()
        
        symbols = []
        for symbol, configs in self.configs_cache.items():
            for config in configs:
                if config['strategy_name'] == strategy_name and config.get('enabled'):
                    symbols.append(symbol)
                    break
        
        return symbols
    
    def get_all_strategies(self) -> List[str]:
        """
        Get list of all available strategies.
        
        Returns:
            List of strategy names
        """
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT strategy_name FROM strategy_parameters ORDER BY strategy_name")
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting strategies: {e}")
            return []
    
    def reload_configs(self) -> bool:
        """
        Reload configurations from database.
        
        Returns:
            True if successful
        """
        try:
            self.load_all_configs()
            logger.info("Strategy configs reloaded")
            return True
        except Exception as e:
            logger.error(f"Error reloading configs: {e}")
            return False
