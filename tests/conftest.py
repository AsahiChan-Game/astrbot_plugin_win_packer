"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

from src.domain.models.configuration import BuildConfiguration, ScriptConfiguration
from src.domain.interfaces.base import ILogger, IConfigurationManager, IErrorHandler


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock(spec=ILogger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture
def mock_config_manager():
    """Create a mock configuration manager for testing."""
    config_manager = Mock(spec=IConfigurationManager)
    config_manager.get = Mock()
    config_manager.set = Mock()
    config_manager.validate = Mock(return_value=True)
    config_manager.reload = Mock(return_value=True)
    config_manager.get_all = Mock(return_value={})
    return config_manager


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler for testing."""
    error_handler = Mock(spec=IErrorHandler)
    error_handler.handle_error = AsyncMock(return_value="Error handled")
    error_handler.log_error = Mock()
    error_handler.create_user_message = Mock(return_value="User friendly error")
    return error_handler


@pytest.fixture
def sample_build_config():
    """Create a sample build configuration for testing."""
    return BuildConfiguration(
        workspace_root=r"C:\TestWorkspace",
        publish_root_base=r"C:\TestPublish",
        min_size_threshold=1024 * 1024,  # 1MB for testing
        disk_warn_threshold=10 * 1024 * 1024,  # 10MB for testing
        web_port=8091,
        history_file="test_history.json",
        max_history_entries=10
    )


@pytest.fixture
def sample_script_config():
    """Create a sample script configuration for testing."""
    return ScriptConfiguration()


@pytest.fixture
def sample_config_dict():
    """Create a sample configuration dictionary for testing."""
    return {
        'workspace_root': r"C:\TestWorkspace",
        'publish_root_base': r"C:\TestPublish",
        'min_size_threshold': 1024 * 1024,
        'disk_warn_threshold': 10 * 1024 * 1024,
        'web_port': 8091,
        'history_file': "test_history.json"
    }