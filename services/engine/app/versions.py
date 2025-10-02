"""
Backtest Versioning System

Tracks versions of:
- Backtest engine code
- Strategy logic
- Configuration parameters
- Results and analysis

This helps ensure reproducibility and track performance across different versions.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class VersionInfo:
    """Version information for backtest components."""
    engine_version: str
    strategy_version: str
    config_version: str
    timestamp: str
    description: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return asdict(self)


class VersionManager:
    """Manages versioning for backtest system."""

    def __init__(self, version_file: str = None):
        """Initialize version manager."""
        if version_file is None:
            # Default version file location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            version_file = os.path.join(script_dir, '.backtest_versions.json')

        self.version_file = version_file
        self.current_version = self._load_or_create_version()

    def _load_or_create_version(self) -> VersionInfo:
        """Load existing version or create new one."""
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r') as f:
                    data = json.load(f)
                    return VersionInfo(**data)
            except (json.JSONDecodeError, KeyError):
                # File corrupted or missing fields, create new
                pass

        # Create new version
        return VersionInfo(
            engine_version="1.0.0",
            strategy_version="1.0.0",
            config_version="1.0.0",
            timestamp=datetime.now().isoformat(),
            description="Initial backtest engine with portfolio simulation"
        )

    def save_version(self):
        """Save current version to file."""
        os.makedirs(os.path.dirname(self.version_file), exist_ok=True)
        with open(self.version_file, 'w') as f:
            json.dump(self.current_version.to_dict(), f, indent=2)

    def bump_engine_version(self, description: str = ""):
        """Bump engine version."""
        parts = self.current_version.engine_version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        self.current_version.engine_version = '.'.join(parts)
        self.current_version.timestamp = datetime.now().isoformat()
        if description:
            self.current_version.description = description
        self.save_version()

    def bump_strategy_version(self, description: str = ""):
        """Bump strategy version."""
        parts = self.current_version.strategy_version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        self.current_version.strategy_version = '.'.join(parts)
        self.current_version.timestamp = datetime.now().isoformat()
        if description:
            self.current_version.description = description
        self.save_version()

    def bump_config_version(self, description: str = ""):
        """Bump config version."""
        parts = self.current_version.config_version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        self.current_version.config_version = '.'.join(parts)
        self.current_version.timestamp = datetime.now().isoformat()
        if description:
            self.current_version.description = description
        self.save_version()

    def get_version_info(self) -> VersionInfo:
        """Get current version information."""
        return self.current_version

    def set_description(self, description: str):
        """Set version description."""
        self.current_version.description = description
        self.current_version.timestamp = datetime.now().isoformat()
        self.save_version()


# Global version manager instance
version_manager = VersionManager()


def get_version_info() -> VersionInfo:
    """Get current version information."""
    return version_manager.get_version_info()


def bump_engine_version(description: str = ""):
    """Bump engine version."""
    version_manager.bump_engine_version(description)


def bump_strategy_version(description: str = ""):
    """Bump strategy version."""
    version_manager.bump_strategy_version(description)


def bump_config_version(description: str = ""):
    """Bump config version."""
    version_manager.bump_config_version(description)


def set_version_description(description: str):
    """Set version description."""
    version_manager.set_description(description)
