"""
Backtest Configuration Module

Handles database connections, configuration loading, and basic setup.
Separated from main engine for better organization.
"""

import os
import psycopg2
from typing import Dict, Optional
from loguru import logger

# Import versioning
from .versions import get_version_info


class BacktestConfig:
    """Configuration and database management for backtest engine."""

    def __init__(self, parameters: Optional[Dict] = None):
        """Initialize configuration."""
        self.params = parameters or {}
        self.db_config = self._get_db_config()
        self.conn = None

        # Log version info
        version = get_version_info()
        logger.info(f"Backtest Engine v{version.engine_version} | Strategy v{version.strategy_version}")

    def _get_db_config(self) -> Dict:
        """Get database configuration from environment."""
        return {
            'host': os.getenv('DB_HOST', 'db'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'trading'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }

    def connect_db(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = False
            logger.debug("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect_db(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")

    def get_connection(self):
        """Get database connection."""
        if not self.conn:
            self.connect_db()
        return self.conn

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def get_parameter(self, key: str, default=None):
        """Get configuration parameter."""
        return self.params.get(key, default)

    def get_strategy_parameters(self) -> Dict:
        """Get strategy-specific parameters."""
        return {
            'min_aggression_score': self.params.get('min_aggression_score', 70),
            'atr_stop_multiplier': self.params.get('atr_stop_multiplier', 1.5),
            'atr_target_multiplier': self.params.get('atr_target_multiplier', 3.0),
            'risk_per_trade_pct': self.params.get('risk_per_trade_pct', 1.0),
            'max_positions': self.params.get('max_positions', 3)
        }

    def get_test_mode(self) -> str:
        """Get test mode."""
        return self.params.get('test_mode', 'portfolio')

    def __enter__(self):
        """Context manager entry."""
        self.connect_db()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect_db()
