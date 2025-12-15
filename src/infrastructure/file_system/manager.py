"""
Secure file manager implementation with validation and locking.
"""

import os
import shutil
import tempfile
import threading
import asyncio
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Set
import time
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
import stat

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.file_manager import IFileManager, IFileLock
from src.domain.models.configuration import BuildConfiguration
from src.domain.models.entities import BuildInfo, BuildType
from src.domain.exceptions import FileSystemError, SecurityError


class FileLock:
    """File locking implementation for concurrent access control."""
    
    def __init__(self, file_path: str, logger: ILogger):
        self.file_path = Path(file_path)
        self.logger = logger
        self.lock_file = None
        self._lock = threading.Lock()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await asyncio.get_event_loop().run_in_executor(None, self.acquire)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await asyncio.get_event_loop().run_in_executor(None, self.release)
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire the lock."""
        with self._lock:
            if self.lock_file is not None:
                return True  # Already acquired
            
            lock_path = self.file_path.with_suffix(self.file_path.suffix + '.lock')
            
            try:
                # Create lock file
                self.lock_file = open(lock_path, 'w')
                
                # Try to acquire exclusive lock (Windows compatible)
                if HAS_FCNTL:
                    if timeout is None:
                        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
                    else:
                        # Non-blocking lock with timeout
                        start_time = time.time()
                        while time.time() - start_time < timeout:
                            try:
                                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                                break
                            except BlockingIOError:
                                time.sleep(0.1)
                        else:
                            self.lock_file.close()
                            self.lock_file = None
                            return False
                else:
                    # Windows fallback - simple file-based locking
                    if lock_path.exists():
                        # Check if lock is stale (older than 1 hour)
                        if time.time() - lock_path.stat().st_mtime > 3600:
                            lock_path.unlink()
                        else:
                            self.lock_file.close()
                            self.lock_file = None
                            return False
                
                self.logger.debug(f"Acquired file lock: {lock_path}")
                return True
                
            except Exception as e:
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                self.logger.error(f"Failed to acquire file lock: {e}")
                return False
    
    def release(self) -> None:
        """Release the lock."""
        with self._lock:
            if self.lock_file is not None:
                try:
                    if HAS_FCNTL:
                        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                    
                    self.lock_file.close()
                    
                    # Remove lock file
                    lock_path = Path(self.lock_file.name)
                    if lock_path.exists():
                        lock_path.unlink()
                    
                    self.logger.debug(f"Released file lock: {lock_path}")
                    
                except Exception as e:
                    self.logger.error(f"Error releasing file lock: {e}")
                finally:
                    self.lock_file = None


class SecureFileManager:
    """Secure file manager with validation, locking, and efficient operations."""
    
    def __init__(self, config: BuildConfiguration, logger: ILogger):
        self.config = config
        self.logger = logger
        self._temp_files: Set[str] = set()
        self._temp_lock = threading.Lock()
        
        # Cache for directory sizes to improve performance
        self._size_cache: Dict[str, Tuple[float, Tuple[str, int]]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    def get_branch_paths(self, branch: str) -> Tuple[str, str]:
        """Get bat directory and publish root for a branch."""
        if not self._is_valid_branch_name(branch):
            raise SecurityError(f"Invalid branch name: {branch}")
        
        bat_dir = os.path.join(self.config.workspace_root, branch, "Lycoris_main", "bat")
        publish_root = os.path.join(self.config.publish_root_base, f"Lycoris_{branch}")
        
        # Validate paths are within expected directories
        if not self.validate_path(bat_dir, self.config.workspace_root):
            raise SecurityError(f"Bat directory path validation failed: {bat_dir}")
        
        if not self.validate_path(publish_root, self.config.publish_root_base):
            raise SecurityError(f"Publish root path validation failed: {publish_root}")
        
        return bat_dir, publish_root
    
    def get_latest_build_info(self, root: str, after_timestamp: Optional[float] = None) -> Tuple[bool, BuildInfo, Optional[str]]:
        """Get information about the latest build in the specified root directory."""
        if not self.validate_path(root):
            raise SecurityError(f"Root path validation failed: {root}")
        
        if not os.path.exists(root):
            return False, BuildInfo(path="", folder_name=""), None
        
        try:
            # Get subdirectories
            subdirs = []
            for item in os.listdir(root):
                item_path = os.path.join(root, item)
                if os.path.isdir(item_path):
                    subdirs.append(item_path)
            
            if not subdirs:
                return False, BuildInfo(path="", folder_name=""), None
            
            # Find latest by modification time
            latest_dir = max(subdirs, key=os.path.getmtime)
            
            # Check timestamp filter
            if after_timestamp and os.path.getmtime(latest_dir) < (after_timestamp - 5):
                return False, BuildInfo(path="", folder_name=""), None
            
            # Get directory info
            folder_name = os.path.basename(latest_dir)
            size_str, size_bytes = self.get_dir_size(latest_dir)
            
            # Parse build info from folder name
            build_info = BuildInfo.parse_from_folder_name(
                path=latest_dir,
                folder_name=folder_name,
                size_str=size_str,
                size_bytes=size_bytes
            )
            
            return True, build_info, latest_dir
            
        except Exception as e:
            self.logger.error(f"Error getting latest build info: {e}", root=root)
            return False, BuildInfo(path="", folder_name=""), None
    
    def get_dir_size(self, path: str) -> Tuple[str, int]:
        """Get directory size with caching for performance."""
        if not self.validate_path(path):
            raise SecurityError(f"Path validation failed: {path}")
        
        # Check cache first
        cache_key = os.path.abspath(path)
        current_time = time.time()
        
        if cache_key in self._size_cache:
            cache_time, cached_result = self._size_cache[cache_key]
            if current_time - cache_time < self._cache_ttl:
                return cached_result
        
        total_size = 0
        try:
            # Use os.walk for efficient directory traversal
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        # Use lstat to avoid following symlinks
                        file_stat = os.lstat(file_path)
                        if stat.S_ISREG(file_stat.st_mode):  # Only regular files
                            total_size += file_stat.st_size
                    except (OSError, IOError):
                        # Skip files that can't be accessed
                        continue
        
        except Exception as e:
            self.logger.warning(f"Error calculating directory size: {e}", path=path)
        
        # Format size
        gb = total_size / (1024**3)
        if gb >= 1:
            size_str = f"{gb:.2f} GB"
        else:
            mb = total_size / (1024**2)
            size_str = f"{mb:.2f} MB"
        
        result = (size_str, total_size)
        
        # Update cache
        self._size_cache[cache_key] = (current_time, result)
        
        return result
    
    def find_disk_log(self, path: str) -> Optional[str]:
        """Find build log file in the specified path."""
        if not self.validate_path(path):
            raise SecurityError(f"Path validation failed: {path}")
        
        log_path = os.path.join(path, "buildlog", "build.log")
        return log_path if os.path.exists(log_path) else None
    
    def check_disk_space(self) -> Optional[str]:
        """Check disk space and return warning message if needed."""
        try:
            total, used, free = shutil.disk_usage(self.config.publish_root_base)
            
            if free < self.config.disk_warn_threshold:
                free_gb = free / (1024**3)
                return f"⚠️ **注意**: 发布盘剩余空间不足 ({free_gb:.2f} GB)！请留意。"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking disk space: {e}")
            return None
    
    def validate_path(self, path: str, base_path: Optional[str] = None) -> bool:
        """Validate path for security (prevent directory traversal)."""
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(path)
            
            # Check for directory traversal attempts
            if '..' in path or path.startswith('/') or ':' in path[1:3]:  # Windows drive check
                return False
            
            # If base_path is provided, ensure path is within it
            if base_path:
                abs_base = os.path.abspath(base_path)
                if not abs_path.startswith(abs_base):
                    return False
            
            # Check for invalid characters
            invalid_chars = ['<', '>', '"', '|', '?', '*']
            if any(char in path for char in invalid_chars):
                return False
            
            return True
            
        except Exception:
            return False
    
    def create_secure_temp_file(self, suffix: str = "", prefix: str = "build_") -> str:
        """Create a secure temporary file and return its path."""
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)  # Close the file descriptor
            
            # Set secure permissions (owner read/write only)
            os.chmod(temp_path, 0o600)
            
            # Track for cleanup
            with self._temp_lock:
                self._temp_files.add(temp_path)
            
            self.logger.debug(f"Created secure temp file: {temp_path}")
            return temp_path
            
        except Exception as e:
            raise FileSystemError(f"Failed to create secure temp file: {e}")
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files created by this manager."""
        with self._temp_lock:
            for temp_file in self._temp_files.copy():
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                    self._temp_files.remove(temp_file)
                    self.logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
    
    def create_file_lock(self, file_path: str) -> IFileLock:
        """Create a file lock for the specified path."""
        return FileLock(file_path, self.logger)
    
    def _is_valid_branch_name(self, branch: str) -> bool:
        """Validate branch name for security."""
        if not branch or not isinstance(branch, str):
            return False
        
        # Check length
        if len(branch) > 100:  # Reasonable limit
            return False
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\', '\0']
        if any(char in branch for char in invalid_chars):
            return False
        
        # Check for reserved names (Windows)
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                         'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                         'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        if branch.upper() in reserved_names:
            return False
        
        return True
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.cleanup_temp_files()
        except Exception:
            pass  # Ignore errors during cleanup