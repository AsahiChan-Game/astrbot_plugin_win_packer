"""
Structured logging implementation.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from src.domain.interfaces.base import ILogger


class StructuredLogger:
    """Structured logger implementation with JSON formatting."""
    
    def __init__(self, name: str, level: str = "INFO", log_file: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = StructuredFormatter()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self._log(logging.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self._log(logging.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self._log(logging.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self._log(logging.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self._log(logging.CRITICAL, message, kwargs)
    
    def _log(self, level: int, message: str, context: Dict[str, Any]) -> None:
        """Internal logging method with context."""
        # Create structured log record
        extra = {
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'component': context.get('component', 'unknown')
        }
        
        self.logger.log(level, message, extra=extra)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': getattr(record, 'timestamp', datetime.now().isoformat()),
            'level': record.levelname,
            'component': getattr(record, 'component', 'unknown'),
            'message': record.getMessage(),
            'logger': record.name
        }
        
        # Add context if available
        context = getattr(record, 'context', {})
        if context:
            log_data['context'] = context
        
        # Add exception info if available
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class LoggerFactory:
    """Factory for creating loggers with consistent configuration."""
    
    @staticmethod
    def create_logger(name: str, level: str = "INFO", log_file: Optional[str] = None) -> ILogger:
        """Create a structured logger instance."""
        return StructuredLogger(name, level, log_file)
    
    @staticmethod
    def create_component_logger(component_name: str, base_config: Dict[str, Any]) -> ILogger:
        """Create a logger for a specific component."""
        log_level = base_config.get('log_level', 'INFO')
        log_dir = base_config.get('log_dir', 'logs')
        
        log_file = None
        if log_dir:
            log_file = f"{log_dir}/{component_name}.log"
        
        return StructuredLogger(f"build_system.{component_name}", log_level, log_file)