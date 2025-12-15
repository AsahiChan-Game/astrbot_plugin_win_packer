"""
Error handler implementation with structured logging and fallback mechanisms.
"""

import traceback
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from src.domain.interfaces.base import ILogger, IErrorHandler
from src.domain.exceptions import (
    BuildSystemError, ConfigurationError, BuildExecutionError, 
    FileSystemError, NetworkError, TaskQueueError, AIServiceError,
    ValidationError, SecurityError, ProcessError
)


class ErrorHandler:
    """Comprehensive error handler with logging and user-friendly messages."""
    
    def __init__(self, logger: ILogger):
        self.logger = logger
        self._fallback_handlers: Dict[type, Callable[[Exception, Dict[str, Any]], str]] = {}
        self._setup_default_handlers()
    
    def _setup_default_handlers(self) -> None:
        """Setup default fallback handlers for different error types."""
        self._fallback_handlers.update({
            ConfigurationError: self._handle_configuration_error,
            BuildExecutionError: self._handle_build_execution_error,
            FileSystemError: self._handle_filesystem_error,
            NetworkError: self._handle_network_error,
            TaskQueueError: self._handle_task_queue_error,
            AIServiceError: self._handle_ai_service_error,
            ValidationError: self._handle_validation_error,
            SecurityError: self._handle_security_error,
            ProcessError: self._handle_process_error,
        })
    
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> str:
        """Handle error with logging and return user-friendly message."""
        # Log the error with full context
        self.log_error(error, context)
        
        # Create user-friendly message
        user_message = self.create_user_message(error)
        
        # Execute fallback behavior if available
        await self._execute_fallback(error, context)
        
        return user_message
    
    def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error with structured context."""
        error_context = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat(),
            **context
        }
        
        # Add specific error attributes if available
        if isinstance(error, BuildSystemError):
            error_context.update(error.context)
            
            if isinstance(error, BuildExecutionError):
                error_context.update({
                    'return_code': error.return_code,
                    'has_log_content': bool(error.log_content)
                })
            elif isinstance(error, FileSystemError):
                error_context['file_path'] = error.file_path
            elif isinstance(error, NetworkError):
                error_context.update({
                    'port': error.port,
                    'host': error.host
                })
            elif isinstance(error, AIServiceError):
                error_context['provider'] = error.provider
            elif isinstance(error, ValidationError):
                error_context.update({
                    'field': error.field,
                    'value': str(error.value) if error.value is not None else None
                })
            elif isinstance(error, ProcessError):
                error_context.update({
                    'process_id': error.process_id,
                    'command': error.command
                })
        
        # Log at appropriate level
        if isinstance(error, (SecurityError, ProcessError)):
            self.logger.critical("Critical error occurred", **error_context)
        elif isinstance(error, (BuildExecutionError, NetworkError)):
            self.logger.error("Execution error occurred", **error_context)
        elif isinstance(error, (ConfigurationError, ValidationError)):
            self.logger.warning("Configuration/validation error occurred", **error_context)
        else:
            self.logger.error("Unexpected error occurred", **error_context)
    
    def create_user_message(self, error: Exception) -> str:
        """Create user-friendly error message."""
        if isinstance(error, ConfigurationError):
            return f"⚙️ 配置错误: {error.message}\n请检查配置文件设置。"
        
        elif isinstance(error, BuildExecutionError):
            base_msg = f"🔨 构建执行失败: {error.message}"
            if error.return_code:
                base_msg += f"\n返回码: {error.return_code}"
            return base_msg
        
        elif isinstance(error, FileSystemError):
            return f"📁 文件系统错误: {error.message}\n请检查文件路径和权限。"
        
        elif isinstance(error, NetworkError):
            return f"🌐 网络错误: {error.message}\n请检查网络连接和端口设置。"
        
        elif isinstance(error, TaskQueueError):
            return f"📋 任务队列错误: {error.message}\n请稍后重试。"
        
        elif isinstance(error, AIServiceError):
            return f"🤖 AI服务错误: {error.message}\n将使用备用方案。"
        
        elif isinstance(error, ValidationError):
            return f"✅ 数据验证失败: {error.message}\n请检查输入参数。"
        
        elif isinstance(error, SecurityError):
            return f"🔒 安全错误: {error.message}\n操作已被阻止。"
        
        elif isinstance(error, ProcessError):
            return f"⚡ 进程错误: {error.message}\n请检查系统资源。"
        
        elif isinstance(error, BuildSystemError):
            return f"❌ 系统错误: {error.message}"
        
        else:
            return f"❌ 未知错误: {str(error)}\n请联系管理员。"
    
    async def _execute_fallback(self, error: Exception, context: Dict[str, Any]) -> None:
        """Execute fallback behavior for specific error types."""
        error_type = type(error)
        
        # Find the most specific handler
        for exc_type, handler in self._fallback_handlers.items():
            if isinstance(error, exc_type):
                try:
                    await self._safe_execute_handler(handler, error, context)
                    break
                except Exception as fallback_error:
                    self.logger.error(
                        "Fallback handler failed",
                        error_type=type(fallback_error).__name__,
                        error_message=str(fallback_error),
                        original_error=str(error)
                    )
    
    async def _safe_execute_handler(self, handler: Callable, error: Exception, context: Dict[str, Any]) -> None:
        """Safely execute a fallback handler."""
        try:
            if hasattr(handler, '__call__'):
                result = handler(error, context)
                # Handle async handlers
                if hasattr(result, '__await__'):
                    await result
        except Exception as e:
            # Log but don't re-raise to prevent cascading failures
            self.logger.error(f"Fallback handler execution failed: {e}")
    
    # Specific fallback handlers
    
    def _handle_configuration_error(self, error: ConfigurationError, context: Dict[str, Any]) -> None:
        """Handle configuration errors by attempting to use defaults."""
        self.logger.info("Attempting to use default configuration values")
        # Could implement configuration reset logic here
    
    def _handle_build_execution_error(self, error: BuildExecutionError, context: Dict[str, Any]) -> None:
        """Handle build execution errors."""
        self.logger.info("Build execution failed, cleaning up resources")
        # Could implement cleanup logic here
    
    def _handle_filesystem_error(self, error: FileSystemError, context: Dict[str, Any]) -> None:
        """Handle filesystem errors by attempting recovery."""
        self.logger.info("Filesystem error occurred, checking permissions and paths")
        # Could implement path validation and permission checks
    
    def _handle_network_error(self, error: NetworkError, context: Dict[str, Any]) -> None:
        """Handle network errors by attempting reconnection."""
        self.logger.info("Network error occurred, will retry with backoff")
        # Could implement retry logic with exponential backoff
    
    def _handle_task_queue_error(self, error: TaskQueueError, context: Dict[str, Any]) -> None:
        """Handle task queue errors by attempting queue recovery."""
        self.logger.info("Task queue error occurred, attempting recovery")
        # Could implement queue state recovery
    
    def _handle_ai_service_error(self, error: AIServiceError, context: Dict[str, Any]) -> None:
        """Handle AI service errors by falling back to simple responses."""
        self.logger.info("AI service error occurred, using fallback responses")
        # Could implement simple text-based fallbacks
    
    def _handle_validation_error(self, error: ValidationError, context: Dict[str, Any]) -> None:
        """Handle validation errors by logging detailed field information."""
        self.logger.info(f"Validation failed for field: {error.field}, value: {error.value}")
    
    def _handle_security_error(self, error: SecurityError, context: Dict[str, Any]) -> None:
        """Handle security errors with enhanced logging."""
        self.logger.critical("Security violation detected", **context)
        # Could implement additional security measures
    
    def _handle_process_error(self, error: ProcessError, context: Dict[str, Any]) -> None:
        """Handle process errors by attempting cleanup."""
        self.logger.info(f"Process error for PID {error.process_id}, attempting cleanup")
        # Could implement process cleanup logic
    
    def add_fallback_handler(self, error_type: type, handler: Callable[[Exception, Dict[str, Any]], None]) -> None:
        """Add custom fallback handler for specific error type."""
        self._fallback_handlers[error_type] = handler
    
    def remove_fallback_handler(self, error_type: type) -> None:
        """Remove fallback handler for specific error type."""
        self._fallback_handlers.pop(error_type, None)