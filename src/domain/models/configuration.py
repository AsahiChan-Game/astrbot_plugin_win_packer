"""
Configuration models and validation schemas.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional
import os
from src.domain.interfaces.base import ValueObject


@dataclass(frozen=True)
class BuildConfiguration(ValueObject):
    """Configuration for the build system."""
    
    # Path configurations
    workspace_root: str = r"C:\WorkSpace"
    publish_root_base: str = r"d:\publish"
    
    # Size thresholds (in bytes)
    min_size_threshold: int = 2 * 1024 * 1024 * 1024  # 2GB
    disk_warn_threshold: int = 20 * 1024 * 1024 * 1024  # 20GB
    
    # Network configuration
    web_port: int = 8090
    web_host: str = "0.0.0.0"
    
    # File configurations
    history_file: str = "build_history.json"
    max_history_entries: int = 50
    
    # Process configurations
    process_timeout: float = 5.0  # seconds for readline timeout
    max_log_lines: int = 10000
    
    # AI configurations
    ai_timeout: float = 30.0  # seconds
    ai_max_retries: int = 3
    
    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_paths()
        self._validate_thresholds()
        self._validate_network()
    
    def _validate_paths(self) -> None:
        """Validate path configurations."""
        if not self.workspace_root or not isinstance(self.workspace_root, str):
            raise ValueError("workspace_root must be a non-empty string")
        
        if not self.publish_root_base or not isinstance(self.publish_root_base, str):
            raise ValueError("publish_root_base must be a non-empty string")
    
    def _validate_thresholds(self) -> None:
        """Validate size thresholds."""
        if self.min_size_threshold <= 0:
            raise ValueError("min_size_threshold must be positive")
        
        if self.disk_warn_threshold <= 0:
            raise ValueError("disk_warn_threshold must be positive")
        
        if self.min_size_threshold >= self.disk_warn_threshold:
            raise ValueError("min_size_threshold should be less than disk_warn_threshold")
    
    def _validate_network(self) -> None:
        """Validate network configurations."""
        if not (1 <= self.web_port <= 65535):
            raise ValueError("web_port must be between 1 and 65535")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'BuildConfiguration':
        """Create configuration from dictionary with environment variable support."""
        # Support environment variable overrides
        env_overrides = {
            'workspace_root': os.getenv('BUILD_WORKSPACE_ROOT'),
            'publish_root_base': os.getenv('BUILD_PUBLISH_ROOT'),
            'web_port': os.getenv('BUILD_WEB_PORT'),
            'log_level': os.getenv('BUILD_LOG_LEVEL'),
        }
        
        # Apply environment overrides
        for key, env_value in env_overrides.items():
            if env_value is not None:
                if key == 'web_port':
                    config_dict[key] = int(env_value)
                else:
                    config_dict[key] = env_value
        
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'workspace_root': self.workspace_root,
            'publish_root_base': self.publish_root_base,
            'min_size_threshold': self.min_size_threshold,
            'disk_warn_threshold': self.disk_warn_threshold,
            'web_port': self.web_port,
            'web_host': self.web_host,
            'history_file': self.history_file,
            'max_history_entries': self.max_history_entries,
            'process_timeout': self.process_timeout,
            'max_log_lines': self.max_log_lines,
            'ai_timeout': self.ai_timeout,
            'ai_max_retries': self.ai_max_retries,
            'log_level': self.log_level,
            'log_format': self.log_format,
        }


@dataclass(frozen=True)
class ScriptConfiguration(ValueObject):
    """Configuration for build scripts."""
    
    script_mappings: Dict[str, str] = field(default_factory=lambda: {
        "simple": "packsimple.bat",
        "develop": "packdevelop.bat", 
        "debug": "packdebug.bat",
        "special": "packspecial.bat",
        "all": "aaaaaaaaaaaaaaaaaaaalll.bat"
    })
    
    fallback_script: str = "packet.bat"
    
    progress_stages: Dict[str, str] = field(default_factory=lambda: {
        "Running AutomationTool...": "⚙️ Init UAT",
        "Command: BuildCookRun": "🏗️ Start Build",
        "Cook: ": "🍳 Cooking...",
        "Stage: ": "📦 Staging...",
        "Package: ": "🚚 Packaging...",
        "BUILD SUCCESSFUL": "✅ Finalizing..."
    })
    
    def get_script_name(self, strategy: str) -> str:
        """Get script name for build strategy."""
        return self.script_mappings.get(strategy.lower(), self.fallback_script)
    
    def get_progress_message(self, log_line: str) -> Optional[str]:
        """Get progress message for log line."""
        for trigger, message in self.progress_stages.items():
            if trigger in log_line:
                return message
        return None