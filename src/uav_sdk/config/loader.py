"""
Configuration management for SDK.

Handles loading configurations, schema validation, and defaults.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Configuration management.
    
    Loads and manages SDK configuration from YAML/JSON files.
    """
    
    def __init__(self):
        """Initialize config manager."""
        self._config: Dict[str, Any] = {}
    
    def load_file(self, path: Union[str, Path]) -> bool:
        """Load configuration from file.
        
        Args:
            path: Path to YAML or JSON config file
            
        Returns:
            True if successful
        """
        path = Path(path)
        
        if not path.exists():
            logger.error(f"Config file not found: {path}")
            return False
        
        try:
            with open(path) as f:
                if path.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix == '.json':
                    config = json.load(f)
                else:
                    logger.error(f"Unsupported config format: {path.suffix}")
                    return False
            
            if config:
                self._config.update(config)
                logger.info(f"Loaded config from {path}")
                return True
            else:
                logger.warning(f"Config file is empty: {path}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation path.
        
        Args:
            key: Config key (e.g., "plugins.flight_controller.rate")
            default: Default value if not found
            
        Returns:
            Config value or default
        """
        parts = key.split('.')
        value = self._config
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """Set config value by dot-notation path.
        
        Args:
            key: Config key
            value: Value to set
        """
        parts = key.split('.')
        config = self._config
        
        # Navigate/create path
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        
        # Set final value
        config[parts[-1]] = value
        logger.debug(f"Config set: {key} = {value}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire config dictionary.
        
        Returns:
            Full config
        """
        return self._config.copy()
    
    def merge(self, other: Dict[str, Any]) -> None:
        """Merge another config dict into current.
        
        Args:
            other: Config dict to merge
        """
        self._config.update(other)
        logger.debug(f"Merged config with {len(other)} keys")
    
    def clear(self) -> None:
        """Clear all configuration."""
        self._config.clear()
        logger.debug("Config cleared")


def get_default_config() -> Dict[str, Any]:
    """Get default SDK configuration.
    
    Returns:
        Default config dictionary
    """
    return {
        "sdk": {
            "debug": False,
            "log_level": "INFO",
        },
        "plugins": {
            "event_system": {
                "enabled": True,
            },
            "state_manager": {
                "enabled": True,
                "max_history": 100,
            }
        },
        "logging": {
            "level": "INFO",
            "format": "human",  # or "json"
            "file": None,
            "max_size_mb": 100,
            "backup_count": 5,
        }
    }
