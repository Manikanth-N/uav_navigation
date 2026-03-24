"""
Plugin manifest loading and parsing.

Plugins define their metadata in plugin.yaml/plugin.json files.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginManifest:
    """Parsed plugin manifest."""
    name: str
    version: str
    author: str
    description: str
    plugin_type: str
    category: str
    dependencies: Dict[str, str]
    entry_point: str
    config_schema: Dict
    features: list
    tags: list
    platforms: list
    min_memory_mb: int
    python_version: str
    
    def validate(self) -> bool:
        """Validate manifest contents.
        
        Returns:
            True if valid
            
        Raises:
            ValueError: If manifest is invalid
        """
        required = [
            'name', 'version', 'author', 'description',
            'plugin_type', 'entry_point'
        ]
        
        for field in required:
            if not getattr(self, field, None):
                raise ValueError(f"Missing required field: {field}")
        
        if not self.entry_point or ':' not in self.entry_point:
            raise ValueError(
                f"Invalid entry_point format: {self.entry_point}. "
                "Expected 'module.path:ClassName'"
            )
        
        return True


class ManifestLoader:
    """Loads and parses plugin manifests."""
    
    @staticmethod
    def load(path: Union[str, Path]) -> PluginManifest:
        """Load and parse plugin manifest.
        
        Args:
            path: Path to plugin.yaml or plugin.json
            
        Returns:
            Parsed PluginManifest
            
        Raises:
            FileNotFoundError: If manifest file not found
            ValueError: If manifest is invalid
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Plugin manifest not found: {path}")
        
        # Load based on file type
        with open(path) as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported manifest format: {path.suffix}")
        
        if not data:
            raise ValueError(f"Empty manifest: {path}")
        
        # Create manifest
        manifest = PluginManifest(
            name=data.get('name', ''),
            version=data.get('version', ''),
            author=data.get('author', ''),
            description=data.get('description', ''),
            plugin_type=data.get('type', ''),
            category=data.get('category', 'general'),
            dependencies=data.get('dependencies', {}),
            entry_point=data.get('entry_point', ''),
            config_schema=data.get('config', {}),
            features=data.get('features', []),
            tags=data.get('tags', []),
            platforms=data.get('platforms', []),
            min_memory_mb=data.get('min_memory_mb', 1),
            python_version=data.get('python_version', '>=3.8'),
        )
        
        # Validate
        manifest.validate()
        
        logger.debug(f"Loaded manifest: {manifest.name} v{manifest.version}")
        return manifest
