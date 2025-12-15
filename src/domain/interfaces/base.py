"""
Base interfaces and abstract classes for the domain layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, TypeVar, Generic
import asyncio

T = TypeVar('T')
TResult = TypeVar('TResult')


class ILogger(Protocol):
    """Logger interface for dependency injection."""
    
    def debug(self, message: str, **kwargs: Any) -> None: ...
    def info(self, message: str, **kwargs: Any) -> None: ...
    def warning(self, message: str, **kwargs: Any) -> None: ...
    def error(self, message: str, **kwargs: Any) -> None: ...
    def critical(self, message: str, **kwargs: Any) -> None: ...


class IConfigurationManager(Protocol):
    """Configuration management interface."""
    
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def validate(self) -> bool: ...
    def reload(self) -> bool: ...
    def get_all(self) -> Dict[str, Any]: ...


class IErrorHandler(Protocol):
    """Error handling interface."""
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> str: ...
    def log_error(self, error: Exception, context: Dict[str, Any]) -> None: ...
    def create_user_message(self, error: Exception) -> str: ...


class Repository(Generic[T], ABC):
    """Base repository interface."""
    
    @abstractmethod
    async def save(self, entity: T) -> T: ...
    
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]: ...
    
    @abstractmethod
    async def find_all(self) -> List[T]: ...
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool: ...


class DomainService(ABC):
    """Base class for domain services."""
    
    def __init__(self, logger: ILogger):
        self.logger = logger


class ValueObject(ABC):
    """Base class for value objects."""
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))