"""
Logging and metrics infrastructure.

Provides structured logging and metrics collection.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json


class StructuredLogger:
    """Structured logging for SDK.
    
    Supports both human-readable and JSON output formats.
    """
    
    def __init__(self, name: str = "uav_sdk", level: str = "INFO"):
        """Initialize logger.
        
        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    def add_file_handler(self, filename: str, max_bytes: int = 10485760,
                        backup_count: int = 5) -> None:
        """Add rotating file handler.
        
        Args:
            filename: Log file path
            max_bytes: Max size before rotation
            backup_count: Number of backup files to keep
        """
        handler = logging.handlers.RotatingFileHandler(
            filename,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def debug(self, msg: str, **extra) -> None:
        """Log debug message."""
        self.logger.debug(msg, extra=extra)
    
    def info(self, msg: str, **extra) -> None:
        """Log info message."""
        self.logger.info(msg, extra=extra)
    
    def warning(self, msg: str, **extra) -> None:
        """Log warning message."""
        self.logger.warning(msg, extra=extra)
    
    def error(self, msg: str, **extra) -> None:
        """Log error message."""
        self.logger.error(msg, extra=extra)


class MetricsCollector:
    """Collects performance and health metrics.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self._metrics: Dict[str, Any] = {}
    
    def record(self, metric_name: str, value: float, tags: Optional[Dict] = None
              ) -> None:
        """Record a metric.
        
        Args:
            metric_name: Name of metric
            value: Metric value
            tags: Optional tags dict
        """
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        
        self._metrics[metric_name].append({
            "timestamp": datetime.now().isoformat(),
            "value": value,
            "tags": tags or {}
        })
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics.
        
        Returns:
            Dictionary of metrics
        """
        return self._metrics.copy()
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        for metric_name, values in self._metrics.items():
            if values:
                latest = values[-1]
                # Convert metric name to Prometheus format
                prom_name = metric_name.replace('.', '_')
                lines.append(f"{prom_name} {latest['value']}")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
