"""
Event system for pub/sub communication between plugins.

Allows decoupled component communication via events.
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents an event with payload."""
    name: str
    timestamp: float
    payload: Dict[str, Any]


class EventSystem:
    """Publish/Subscribe event system.
    
    Allows plugins and SDK components to communicate via events
    without direct coupling.
    """
    
    def __init__(self):
        """Initialize event system."""
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Subscribe to an event.
        
        Args:
            event_name: Event name (e.g., "sys.armed", "nav.position_updated")
            callback: Async or sync callback function to call on event
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        
        self._subscribers[event_name].append(callback)
        logger.debug(f"Subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """Unsubscribe from an event.
        
        Args:
            event_name: Event name
            callback: Callback to remove
            
        Returns:
            True if callback was subscribed
        """
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_name}")
                return True
            except ValueError:
                pass
        
        return False
    
    async def publish(self, event_name: str, **kwargs) -> None:
        """Publish an event.
        
        Calls all subscribed callbacks asynchronously.
        
        Args:
            event_name: Event name
            **kwargs: Event payload
        """
        timestamp = asyncio.get_event_loop().time()
        event = Event(
            name=event_name,
            timestamp=timestamp,
            payload=kwargs
        )
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        logger.debug(f"Published event: {event_name}")
        
        # Call subscribers
        # First check exact match subscribers
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(
                        f"Error in event callback for {event_name}: {e}",
                        exc_info=True
                    )
        
        # Then check wildcard subscribers (e.g., "sys.*" matches "sys.armed")
        await self._publish_wildcards(event_name, event)
    
    async def _publish_wildcards(self, event_name: str, event: Event) -> None:
        """Publish to wildcard subscribers.
        
        Args:
            event_name: Full event name
            event: Event object
        """
        parts = event_name.split('.')
        
        # Check each level of wildcards
        for i in range(len(parts)):
            wildcard = '.'.join(parts[:i+1]) + '.*'
            
            if wildcard in self._subscribers:
                for callback in self._subscribers[wildcard]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.error(
                            f"Error in wildcard callback for {wildcard}: {e}",
                            exc_info=True
                        )
    
    def get_history(self, event_name: Optional[str] = None,
                   count: int = 100) -> List[Event]:
        """Get event history.
        
        Args:
            event_name: Filter by event name (None = all)
            count: Number of events to return
            
        Returns:
            List of recent events
        """
        if event_name:
            events = [e for e in self._event_history if e.name == event_name]
        else:
            events = self._event_history
        
        return events[-count:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
        logger.debug("Event history cleared")
