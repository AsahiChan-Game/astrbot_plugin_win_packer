"""
Task queue interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum

from src.domain.models.entities import BuildTask, TaskStatus


class QueuePriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ITaskQueue(ABC):
    """Interface for task queue operations."""
    
    @abstractmethod
    async def enqueue(self, task: BuildTask, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        """Add task to queue with specified priority."""
        pass
    
    @abstractmethod
    async def dequeue(self) -> Optional[BuildTask]:
        """Remove and return next task from queue."""
        pass
    
    @abstractmethod
    async def peek(self) -> Optional[BuildTask]:
        """Get next task without removing it from queue."""
        pass
    
    @abstractmethod
    async def get_queue_size(self) -> int:
        """Get current queue size."""
        pass
    
    @abstractmethod
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status information."""
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task in the queue."""
        pass
    
    @abstractmethod
    async def clear_queue(self) -> int:
        """Clear all tasks from queue and return count of removed tasks."""
        pass
    
    @abstractmethod
    async def get_task_position(self, task_id: str) -> Optional[int]:
        """Get position of task in queue (1-based)."""
        pass


class ITaskExecutor(ABC):
    """Interface for task execution."""
    
    @abstractmethod
    async def execute_task(self, task: BuildTask) -> None:
        """Execute a single task."""
        pass
    
    @abstractmethod
    async def cancel_current_task(self) -> bool:
        """Cancel currently executing task."""
        pass
    
    @abstractmethod
    def is_executing(self) -> bool:
        """Check if executor is currently running a task."""
        pass
    
    @abstractmethod
    def get_current_task(self) -> Optional[BuildTask]:
        """Get currently executing task."""
        pass


class ITaskScheduler(ABC):
    """Interface for task scheduling and coordination."""
    
    @abstractmethod
    async def start(self) -> None:
        """Start the task scheduler."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the task scheduler."""
        pass
    
    @abstractmethod
    async def submit_task(self, task: BuildTask, priority: QueuePriority = QueuePriority.NORMAL) -> str:
        """Submit task for execution and return position info."""
        pass
    
    @abstractmethod
    def add_task_callback(self, callback: Callable[[BuildTask, TaskStatus], Awaitable[None]]) -> None:
        """Add callback for task status changes."""
        pass
    
    @abstractmethod
    def remove_task_callback(self, callback: Callable[[BuildTask, TaskStatus], Awaitable[None]]) -> None:
        """Remove task status change callback."""
        pass