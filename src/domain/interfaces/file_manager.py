"""
File manager interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path

from src.domain.models.entities import BuildInfo


class IFileManager(ABC):
    """Interface for file management operations."""
    
    @abstractmethod
    def get_branch_paths(self, branch: str) -> Tuple[str, str]:
        """Get bat directory and publish root for a branch."""
        pass
    
    @abstractmethod
    def get_latest_build_info(self, root: str, after_timestamp: Optional[float] = None) -> Tuple[bool, BuildInfo, Optional[str]]:
        """Get information about the latest build in the specified root directory."""
        pass
    
    @abstractmethod
    def get_dir_size(self, path: str) -> Tuple[str, int]:
        """Get directory size as human-readable string and bytes."""
        pass
    
    @abstractmethod
    def find_disk_log(self, path: str) -> Optional[str]:
        """Find build log file in the specified path."""
        pass
    
    @abstractmethod
    def check_disk_space(self) -> Optional[str]:
        """Check disk space and return warning message if needed."""
        pass
    
    @abstractmethod
    def validate_path(self, path: str, base_path: Optional[str] = None) -> bool:
        """Validate path for security (prevent directory traversal)."""
        pass
    
    @abstractmethod
    def create_secure_temp_file(self, suffix: str = "", prefix: str = "build_") -> str:
        """Create a secure temporary file and return its path."""
        pass
    
    @abstractmethod
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files created by this manager."""
        pass


class IFileLock(ABC):
    """Interface for file locking mechanisms."""
    
    @abstractmethod
    async def __aenter__(self):
        """Async context manager entry."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    @abstractmethod
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire the lock."""
        pass
    
    @abstractmethod
    def release(self) -> None:
        """Release the lock."""
        pass