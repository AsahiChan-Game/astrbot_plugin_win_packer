"""
Domain entities for the build system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid

from src.domain.interfaces.base import ValueObject


class BuildStrategy(Enum):
    """Available build strategies."""
    SIMPLE = "simple"
    DEVELOP = "develop"
    DEBUG = "debug"
    SPECIAL = "special"
    ALL = "all"
    
    @classmethod
    def from_string(cls, value: str) -> 'BuildStrategy':
        """Create BuildStrategy from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid build strategy: {value}. Valid options: {[s.value for s in cls]}")


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildType(Enum):
    """Build artifact types."""
    DEVELOPMENT = "Dev"
    DEBUG = "Debug"
    SHIPPING = "Shipping"
    UNKNOWN = "Unknown"


@dataclass
class BuildTask:
    """Represents a build task with validation."""
    
    # Required fields
    branch: str
    strategy: BuildStrategy
    
    # Optional fields with defaults
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    arg3: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Paths (computed from branch)
    bat_dir: Optional[str] = None
    publish_root: Optional[str] = None
    
    # Execution details
    process_id: Optional[int] = None
    return_code: Optional[int] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate task after initialization."""
        self._validate_branch()
        self._validate_strategy()
        self._validate_arg3()
    
    def _validate_branch(self) -> None:
        """Validate branch name."""
        if not self.branch or not isinstance(self.branch, str):
            raise ValueError("Branch must be a non-empty string")
        
        if not self.branch.strip():
            raise ValueError("Branch cannot be only whitespace")
        
        # Basic validation for common invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in self.branch for char in invalid_chars):
            raise ValueError(f"Branch name contains invalid characters: {invalid_chars}")
    
    def _validate_strategy(self) -> None:
        """Validate build strategy."""
        if not isinstance(self.strategy, BuildStrategy):
            raise ValueError(f"Strategy must be a BuildStrategy enum, got {type(self.strategy)}")
    
    def _validate_arg3(self) -> None:
        """Validate arg3 parameter."""
        if self.strategy == BuildStrategy.SPECIAL and not self.arg3:
            raise ValueError("arg3 is required for SPECIAL build strategy")
        
        if self.arg3 is not None and not isinstance(self.arg3, str):
            raise ValueError("arg3 must be a string if provided")
    
    def start_execution(self, process_id: int) -> None:
        """Mark task as started."""
        if self.status != TaskStatus.QUEUED:
            raise ValueError(f"Cannot start task with status {self.status}")
        
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        self.process_id = process_id
    
    def complete_execution(self, return_code: int, error_message: Optional[str] = None) -> None:
        """Mark task as completed."""
        if self.status != TaskStatus.RUNNING:
            raise ValueError(f"Cannot complete task with status {self.status}")
        
        self.completed_at = datetime.now()
        self.return_code = return_code
        self.error_message = error_message
        
        if return_code == 0 and not error_message:
            self.status = TaskStatus.COMPLETED
        else:
            self.status = TaskStatus.FAILED
    
    def cancel_execution(self, error_message: Optional[str] = None) -> None:
        """Mark task as cancelled."""
        if self.status not in [TaskStatus.QUEUED, TaskStatus.RUNNING]:
            raise ValueError(f"Cannot cancel task with status {self.status}")
        
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.error_message = error_message or "Task cancelled by user"
    
    def get_duration(self) -> Optional[float]:
        """Get task execution duration in seconds."""
        if not self.started_at or not self.completed_at:
            return None
        
        return (self.completed_at - self.started_at).total_seconds()
    
    def is_finished(self) -> bool:
        """Check if task is in a finished state."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'branch': self.branch,
            'strategy': self.strategy.value,
            'arg3': self.arg3,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'bat_dir': self.bat_dir,
            'publish_root': self.publish_root,
            'process_id': self.process_id,
            'return_code': self.return_code,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BuildTask':
        """Create task from dictionary."""
        # Parse datetime fields
        created_at = datetime.fromisoformat(data['created_at'])
        started_at = datetime.fromisoformat(data['started_at']) if data.get('started_at') else None
        completed_at = datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None
        
        return cls(
            task_id=data['task_id'],
            branch=data['branch'],
            strategy=BuildStrategy(data['strategy']),
            arg3=data.get('arg3'),
            status=TaskStatus(data['status']),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            bat_dir=data.get('bat_dir'),
            publish_root=data.get('publish_root'),
            process_id=data.get('process_id'),
            return_code=data.get('return_code'),
            error_message=data.get('error_message')
        )


@dataclass(frozen=True)
class BuildInfo(ValueObject):
    """Information about a build artifact."""
    
    path: str
    folder_name: str
    ymd: str = "?"
    version: str = "?"
    build_type: BuildType = BuildType.UNKNOWN
    size_str: str = "0 MB"
    size_bytes: int = 0
    
    def __post_init__(self):
        """Validate build info after initialization."""
        if not self.path or not isinstance(self.path, str):
            raise ValueError("Path must be a non-empty string")
        
        if not self.folder_name or not isinstance(self.folder_name, str):
            raise ValueError("Folder name must be a non-empty string")
        
        if self.size_bytes < 0:
            raise ValueError("Size bytes cannot be negative")
    
    @classmethod
    def parse_from_folder_name(cls, path: str, folder_name: str, size_str: str, size_bytes: int) -> 'BuildInfo':
        """Parse build info from folder name using existing logic."""
        ymd = "?"
        version = "?"
        build_type = BuildType.UNKNOWN
        
        try:
            parts = folder_name.split('_')
            if len(parts) >= 1:
                ymd = parts[0]
            
            if "ver" in parts:
                version = parts[parts.index("ver") + 1]
            elif "main" in parts:
                version = parts[parts.index("main") + 1]
            
            if "Development" in parts:
                build_type = BuildType.DEVELOPMENT
            elif "Debug" in parts:
                build_type = BuildType.DEBUG
            elif "main" in parts:
                build_type = BuildType.SHIPPING
                
        except (IndexError, ValueError):
            # If parsing fails, use defaults
            pass
        
        return cls(
            path=path,
            folder_name=folder_name,
            ymd=ymd,
            version=version,
            build_type=build_type,
            size_str=size_str,
            size_bytes=size_bytes
        )


@dataclass(frozen=True)
class ProgressUpdate(ValueObject):
    """Progress update for build execution."""
    
    task_id: str
    stage: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate progress update."""
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("Task ID must be a non-empty string")
        
        if not self.stage or not isinstance(self.stage, str):
            raise ValueError("Stage must be a non-empty string")
        
        if not self.message or not isinstance(self.message, str):
            raise ValueError("Message must be a non-empty string")


@dataclass
class BuildResult:
    """Result of a build operation."""
    
    task: BuildTask
    success: bool
    build_info: Optional[BuildInfo] = None
    error_message: Optional[str] = None
    log_content: Optional[str] = None
    duration: Optional[float] = None
    
    def __post_init__(self):
        """Validate build result."""
        if not isinstance(self.task, BuildTask):
            raise ValueError("Task must be a BuildTask instance")
        
        if self.success and not self.build_info:
            raise ValueError("Successful builds must have build_info")
        
        if not self.success and not self.error_message:
            raise ValueError("Failed builds must have error_message")
    
    def get_user_message(self) -> str:
        """Get user-friendly message for the build result."""
        if self.success and self.build_info:
            duration_str = f"{self.duration:.1f}s" if self.duration else "unknown"
            return (f"🎉 [{self.task.branch}] 打包成功！\n"
                   f"⏱️ 耗时: {duration_str}\n"
                   f"🔢 版本: {self.build_info.version} ({self.build_info.build_type.value})\n"
                   f"💾 大小: {self.build_info.size_str}")
        else:
            return f"⚠️ [{self.task.branch}] 打包失败: {self.error_message}"