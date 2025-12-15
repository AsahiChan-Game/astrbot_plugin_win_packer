"""
Domain exceptions and error hierarchy.
"""

from typing import Optional, Dict, Any


class BuildSystemError(Exception):
    """Base exception for build system errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class ConfigurationError(BuildSystemError):
    """Configuration related errors."""
    pass


class BuildExecutionError(BuildSystemError):
    """Build execution related errors."""
    
    def __init__(self, message: str, return_code: Optional[int] = None, 
                 log_content: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.return_code = return_code
        self.log_content = log_content


class FileSystemError(BuildSystemError):
    """File system operation errors."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.file_path = file_path


class NetworkError(BuildSystemError):
    """Network operation errors."""
    
    def __init__(self, message: str, port: Optional[int] = None, 
                 host: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.port = port
        self.host = host


class TaskQueueError(BuildSystemError):
    """Task queue operation errors."""
    pass


class AIServiceError(BuildSystemError):
    """AI service integration errors."""
    
    def __init__(self, message: str, provider: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.provider = provider


class ValidationError(BuildSystemError):
    """Data validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 value: Optional[Any] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.field = field
        self.value = value


class SecurityError(BuildSystemError):
    """Security related errors (e.g., path traversal)."""
    pass


class ProcessError(BuildSystemError):
    """Process execution errors."""
    
    def __init__(self, message: str, process_id: Optional[int] = None, 
                 command: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, context)
        self.process_id = process_id
        self.command = command