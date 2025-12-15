"""
Configuration manager implementation with validation and hot-reload support.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time

from src.domain.interfaces.base import ILogger, IConfigurationManager
from src.domain.models.configuration import BuildConfiguration


class ConfigurationError(Exception):
    """Configuration related errors."""
    pass


class ConfigurationFileHandler(FileSystemEventHandler):
    """File system event handler for configuration hot-reload."""
    
    def __init__(self, config_manager: 'ConfigurationManager'):
        self.config_manager = config_manager
        self.last_modified = 0
        self.debounce_seconds = 1.0  # Prevent multiple rapid reloads
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        current_time = time.time()
        if current_time - self.last_modified < self.debounce_seconds:
            return
        
        self.last_modified = current_time
        
        if event.src_path == str(self.config_manager.config_file_path):
            self.config_manager._reload_from_file()


class ConfigurationManager:
    """Configuration manager with validation and hot-reload capabilities."""
    
    def __init__(self, config_file_path: str, logger: ILogger):
        self.config_file_path = Path(config_file_path)
        self.logger = logger
        self._config_data: Dict[str, Any] = {}
        self._build_config: Optional[BuildConfiguration] = None
        self._observers: list[Observer] = []
        self._change_callbacks: list[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.RLock()
        
        # Load initial configuration
        self._load_configuration()
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        with self._lock:
            return self._config_data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        with self._lock:
            self._config_data[key] = value
            self._rebuild_config()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration data."""
        with self._lock:
            return self._config_data.copy()
    
    def validate(self) -> bool:
        """Validate current configuration."""
        try:
            with self._lock:
                BuildConfiguration.from_dict(self._config_data)
            return True
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    def reload(self) -> bool:
        """Manually reload configuration from file."""
        return self._reload_from_file()
    
    def get_build_config(self) -> BuildConfiguration:
        """Get typed build configuration object."""
        with self._lock:
            if self._build_config is None:
                self._rebuild_config()
            return self._build_config
    
    def start_hot_reload(self) -> None:
        """Start watching configuration file for changes."""
        if not self.config_file_path.exists():
            self.logger.warning(f"Configuration file {self.config_file_path} does not exist")
            return
        
        event_handler = ConfigurationFileHandler(self)
        observer = Observer()
        observer.schedule(
            event_handler, 
            str(self.config_file_path.parent), 
            recursive=False
        )
        observer.start()
        self._observers.append(observer)
        
        self.logger.info(f"Started hot-reload for configuration file: {self.config_file_path}")
    
    def stop_hot_reload(self) -> None:
        """Stop watching configuration file for changes."""
        for observer in self._observers:
            observer.stop()
            observer.join()
        self._observers.clear()
        self.logger.info("Stopped configuration hot-reload")
    
    def add_change_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add callback to be called when configuration changes."""
        self._change_callbacks.append(callback)
    
    def _load_configuration(self) -> None:
        """Load configuration from file or create default."""
        if self.config_file_path.exists():
            self._reload_from_file()
        else:
            self.logger.info(f"Configuration file {self.config_file_path} not found, using defaults")
            self._config_data = BuildConfiguration().to_dict()
            self._rebuild_config()
            self._save_configuration()
    
    def _reload_from_file(self) -> bool:
        """Reload configuration from file."""
        try:
            with self._lock:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                
                # Validate new configuration
                BuildConfiguration.from_dict(new_config)
                
                old_config = self._config_data.copy()
                self._config_data = new_config
                self._rebuild_config()
                
                self.logger.info(f"Configuration reloaded from {self.config_file_path}")
                
                # Notify callbacks of configuration change
                for callback in self._change_callbacks:
                    try:
                        callback(self._config_data)
                    except Exception as e:
                        self.logger.error(f"Configuration change callback failed: {e}")
                
                return True
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def _rebuild_config(self) -> None:
        """Rebuild typed configuration object."""
        try:
            self._build_config = BuildConfiguration.from_dict(self._config_data)
        except Exception as e:
            self.logger.error(f"Failed to rebuild configuration: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}")
    
    def _save_configuration(self) -> None:
        """Save current configuration to file."""
        try:
            # Ensure directory exists
            self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4)
            
            self.logger.info(f"Configuration saved to {self.config_file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.stop_hot_reload()