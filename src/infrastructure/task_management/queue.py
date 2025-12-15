"""
Thread-safe task queue implementation with priority support.
"""

import asyncio
import threading
import json
from typing import Optional, List, Dict, Any, Callable, Awaitable
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.task_queue import ITaskQueue, QueuePriority
from src.domain.models.entities import BuildTask, TaskStatus
from src.domain.exceptions import TaskQueueError


@dataclass
class QueuedTask:
    """Task wrapper with queue metadata."""
    task: BuildTask
    priority: QueuePriority
    queued_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other: 'QueuedTask') -> bool:
        """Compare tasks for priority queue ordering."""
        # Higher priority value = higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        # Same priority, use FIFO (earlier queued_at = higher priority)
        return self.queued_at < other.queued_at


class ThreadSafeTaskQueue:
    """Thread-safe task queue with priority support and persistence."""
    
    def __init__(self, logger: ILogger, persistence_file: Optional[str] = None):
        self.logger = logger
        self.persistence_file = Path(persistence_file) if persistence_file else None
        
        # Thread-safe queue using asyncio primitives
        self._queue: asyncio.PriorityQueue[QueuedTask] = asyncio.PriorityQueue()
        self._task_lookup: Dict[str, QueuedTask] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_enqueued = 0
        self._total_dequeued = 0
        
        # Load persisted tasks if file exists
        self._load_persisted_tasks()
    
    async def enqueue(self, task: BuildTask, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        """Add task to queue with specified priority."""
        try:
            async with self._lock:
                # Check if task already exists
                if task.task_id in self._task_lookup:
                    self.logger.warning(f"Task {task.task_id} already in queue")
                    return False
                
                # Create queued task wrapper
                queued_task = QueuedTask(task=task, priority=priority)
                
                # Update task status
                task.status = TaskStatus.QUEUED
                
                # Add to queue and lookup
                await self._queue.put(queued_task)
                self._task_lookup[task.task_id] = queued_task
                self._total_enqueued += 1
                
                self.logger.info(
                    f"Task enqueued: {task.task_id}",
                    task_id=task.task_id,
                    branch=task.branch,
                    strategy=task.strategy.value,
                    priority=priority.name,
                    queue_size=self._queue.qsize()
                )
                
                # Persist queue state
                await self._persist_queue()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to enqueue task: {e}", task_id=task.task_id)
            raise TaskQueueError(f"Failed to enqueue task: {e}")
    
    async def dequeue(self) -> Optional[BuildTask]:
        """Remove and return next task from queue."""
        try:
            async with self._lock:
                if self._queue.empty():
                    return None
                
                # Get highest priority task
                queued_task = await self._queue.get()
                
                # Remove from lookup
                self._task_lookup.pop(queued_task.task.task_id, None)
                self._total_dequeued += 1
                
                self.logger.info(
                    f"Task dequeued: {queued_task.task.task_id}",
                    task_id=queued_task.task.task_id,
                    wait_time=(datetime.now() - queued_task.queued_at).total_seconds(),
                    queue_size=self._queue.qsize()
                )
                
                # Persist queue state
                await self._persist_queue()
                
                return queued_task.task
                
        except Exception as e:
            self.logger.error(f"Failed to dequeue task: {e}")
            raise TaskQueueError(f"Failed to dequeue task: {e}")
    
    async def peek(self) -> Optional[BuildTask]:
        """Get next task without removing it from queue."""
        try:
            async with self._lock:
                if self._queue.empty():
                    return None
                
                # Create a temporary copy to peek
                temp_queue = asyncio.PriorityQueue()
                next_task = None
                
                # Move all items to temp queue to find the next one
                items = []
                while not self._queue.empty():
                    item = await self._queue.get()
                    items.append(item)
                
                if items:
                    # Sort to find highest priority
                    items.sort()
                    next_task = items[0].task
                    
                    # Put all items back
                    for item in items:
                        await self._queue.put(item)
                
                return next_task
                
        except Exception as e:
            self.logger.error(f"Failed to peek queue: {e}")
            return None
    
    async def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status information."""
        async with self._lock:
            tasks_by_priority = {priority.name: 0 for priority in QueuePriority}
            tasks_by_branch = {}
            
            for queued_task in self._task_lookup.values():
                # Count by priority
                tasks_by_priority[queued_task.priority.name] += 1
                
                # Count by branch
                branch = queued_task.task.branch
                tasks_by_branch[branch] = tasks_by_branch.get(branch, 0) + 1
            
            return {
                'total_size': self._queue.qsize(),
                'tasks_by_priority': tasks_by_priority,
                'tasks_by_branch': tasks_by_branch,
                'total_enqueued': self._total_enqueued,
                'total_dequeued': self._total_dequeued,
                'oldest_task_age': self._get_oldest_task_age()
            }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task in the queue."""
        try:
            async with self._lock:
                if task_id not in self._task_lookup:
                    return False
                
                queued_task = self._task_lookup[task_id]
                queued_task.task.cancel_execution("Cancelled from queue")
                
                # Remove from lookup (will be skipped when dequeued)
                del self._task_lookup[task_id]
                
                self.logger.info(f"Task cancelled: {task_id}")
                
                # Persist queue state
                await self._persist_queue()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to cancel task: {e}", task_id=task_id)
            return False
    
    async def clear_queue(self) -> int:
        """Clear all tasks from queue and return count of removed tasks."""
        try:
            async with self._lock:
                count = self._queue.qsize()
                
                # Cancel all tasks
                for queued_task in self._task_lookup.values():
                    queued_task.task.cancel_execution("Queue cleared")
                
                # Clear queue and lookup
                while not self._queue.empty():
                    await self._queue.get()
                
                self._task_lookup.clear()
                
                self.logger.info(f"Queue cleared: {count} tasks removed")
                
                # Persist empty queue state
                await self._persist_queue()
                
                return count
                
        except Exception as e:
            self.logger.error(f"Failed to clear queue: {e}")
            raise TaskQueueError(f"Failed to clear queue: {e}")
    
    async def get_task_position(self, task_id: str) -> Optional[int]:
        """Get position of task in queue (1-based)."""
        try:
            async with self._lock:
                if task_id not in self._task_lookup:
                    return None
                
                target_task = self._task_lookup[task_id]
                
                # Get all tasks and sort by priority
                all_tasks = list(self._task_lookup.values())
                all_tasks.sort()
                
                # Find position
                for i, queued_task in enumerate(all_tasks, 1):
                    if queued_task.task.task_id == task_id:
                        return i
                
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get task position: {e}", task_id=task_id)
            return None
    
    def _get_oldest_task_age(self) -> Optional[float]:
        """Get age of oldest task in seconds."""
        if not self._task_lookup:
            return None
        
        oldest_time = min(qt.queued_at for qt in self._task_lookup.values())
        return (datetime.now() - oldest_time).total_seconds()
    
    async def _persist_queue(self) -> None:
        """Persist queue state to file."""
        if not self.persistence_file:
            return
        
        try:
            # Prepare data for serialization
            queue_data = {
                'tasks': [
                    {
                        'task': qt.task.to_dict(),
                        'priority': qt.priority.name,
                        'queued_at': qt.queued_at.isoformat()
                    }
                    for qt in self._task_lookup.values()
                ],
                'statistics': {
                    'total_enqueued': self._total_enqueued,
                    'total_dequeued': self._total_dequeued
                }
            }
            
            # Ensure directory exists
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2)
                
        except Exception as e:
            self.logger.warning(f"Failed to persist queue: {e}")
    
    def _load_persisted_tasks(self) -> None:
        """Load persisted tasks from file."""
        if not self.persistence_file or not self.persistence_file.exists():
            return
        
        try:
            with open(self.persistence_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            # Restore statistics
            stats = queue_data.get('statistics', {})
            self._total_enqueued = stats.get('total_enqueued', 0)
            self._total_dequeued = stats.get('total_dequeued', 0)
            
            # Restore tasks
            for task_data in queue_data.get('tasks', []):
                try:
                    task = BuildTask.from_dict(task_data['task'])
                    priority = QueuePriority[task_data['priority']]
                    queued_at = datetime.fromisoformat(task_data['queued_at'])
                    
                    queued_task = QueuedTask(
                        task=task,
                        priority=priority,
                        queued_at=queued_at
                    )
                    
                    # Add to queue (synchronous version for initialization)
                    self._task_lookup[task.task_id] = queued_task
                    
                except Exception as e:
                    self.logger.warning(f"Failed to restore task: {e}")
            
            # Rebuild priority queue
            asyncio.create_task(self._rebuild_priority_queue())
            
            self.logger.info(f"Loaded {len(self._task_lookup)} persisted tasks")
            
        except Exception as e:
            self.logger.warning(f"Failed to load persisted tasks: {e}")
    
    async def _rebuild_priority_queue(self) -> None:
        """Rebuild priority queue from task lookup."""
        try:
            # Clear current queue
            while not self._queue.empty():
                await self._queue.get()
            
            # Re-add all tasks
            for queued_task in self._task_lookup.values():
                await self._queue.put(queued_task)
                
        except Exception as e:
            self.logger.error(f"Failed to rebuild priority queue: {e}")