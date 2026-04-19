"""
Base service classes and dependency injection patterns.
Provides foundation for all application services.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.core.structured_logging import Logger


class Service(ABC):
    """
    Base service class.
    All application services should inherit from this.
    """
    
    def __init__(self):
        self.logger = Logger(self.__class__.__name__)
    
    def set_logger_context(self, **kwargs):
        """Set context for all log calls in this service."""
        self.logger.set_context(**kwargs)


class Repository(ABC):
    """Base repository for data access."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get item by key."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set item."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete item."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if item exists."""
        pass


class CacheRepository(Repository):
    """Interface for cache operations."""
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache."""
        pass
    
    @abstractmethod
    async def ping(self) -> bool:
        """Health check."""
        pass


class DependencyContainer:
    """
    Simple dependency injection container.
    Manages service lifecycle and dependencies.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register_service(self, name: str, service: Any, singleton: bool = True) -> None:
        """Register a service."""
        self._services[name] = service
        if singleton:
            self._singletons[name] = None
    
    def get_service(self, name: str) -> Any:
        """Get a service instance."""
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        service = self._services[name]
        
        # If singleton, cache and reuse
        if isinstance(service, type):  # It's a class
            if name in self._singletons and self._singletons[name] is not None:
                return self._singletons[name]
            instance = service()
            self._singletons[name] = instance
            return instance
        
        return service
    
    def clear(self) -> None:
        """Clear all cached singletons."""
        self._singletons.clear()
