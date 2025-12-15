"""
Unit tests for configuration models and management.
"""

import pytest
import tempfile
import json
from pathlib import Path

from src.domain.models.configuration import BuildConfiguration, ScriptConfiguration
from src.infrastructure.configuration.manager import ConfigurationManager
from src.infrastructure.logging.logger import StructuredLogger


class TestBuildConfiguration:
    """Test BuildConfiguration model."""
    
    def test_default_configuration_is_valid(self):
        """Test that default configuration is valid."""
        config = BuildConfiguration()
        assert config.workspace_root == r"C:\WorkSpace"
        assert config.publish_root_base == r"d:\publish"
        assert config.min_size_threshold == 2 * 1024 * 1024 * 1024
        assert config.web_port == 8090
    
    def test_configuration_validation_valid_paths(self):
        """Test configuration validation with valid paths."""
        config = BuildConfiguration(
            workspace_root=r"C:\ValidPath",
            publish_root_base=r"D:\ValidPublish"
        )
        # Should not raise any exceptions
        assert config.workspace_root == r"C:\ValidPath"
    
    def test_configuration_validation_invalid_paths(self):
        """Test configuration validation with invalid paths."""
        with pytest.raises(ValueError, match="workspace_root must be a non-empty string"):
            BuildConfiguration(workspace_root="")
        
        with pytest.raises(ValueError, match="publish_root_base must be a non-empty string"):
            BuildConfiguration(publish_root_base=None)
    
    def test_configuration_validation_invalid_thresholds(self):
        """Test configuration validation with invalid thresholds."""
        with pytest.raises(ValueError, match="min_size_threshold must be positive"):
            BuildConfiguration(min_size_threshold=0)
        
        with pytest.raises(ValueError, match="disk_warn_threshold must be positive"):
            BuildConfiguration(disk_warn_threshold=-1)
    
    def test_configuration_validation_invalid_port(self):
        """Test configuration validation with invalid port."""
        with pytest.raises(ValueError, match="web_port must be between 1 and 65535"):
            BuildConfiguration(web_port=0)
        
        with pytest.raises(ValueError, match="web_port must be between 1 and 65535"):
            BuildConfiguration(web_port=70000)
    
    def test_from_dict_creates_valid_configuration(self, sample_config_dict):
        """Test creating configuration from dictionary."""
        config = BuildConfiguration.from_dict(sample_config_dict)
        assert config.workspace_root == sample_config_dict['workspace_root']
        assert config.publish_root_base == sample_config_dict['publish_root_base']
    
    def test_to_dict_returns_complete_data(self, sample_build_config):
        """Test converting configuration to dictionary."""
        config_dict = sample_build_config.to_dict()
        assert 'workspace_root' in config_dict
        assert 'publish_root_base' in config_dict
        assert 'web_port' in config_dict
        assert config_dict['workspace_root'] == sample_build_config.workspace_root


class TestScriptConfiguration:
    """Test ScriptConfiguration model."""
    
    def test_default_script_mappings(self):
        """Test default script mappings."""
        config = ScriptConfiguration()
        assert config.get_script_name("simple") == "packsimple.bat"
        assert config.get_script_name("develop") == "packdevelop.bat"
        assert config.get_script_name("unknown") == "packet.bat"
    
    def test_progress_message_detection(self):
        """Test progress message detection."""
        config = ScriptConfiguration()
        
        message = config.get_progress_message("Running AutomationTool...")
        assert message == "⚙️ Init UAT"
        
        message = config.get_progress_message("Some random log line")
        assert message is None


class TestConfigurationManager:
    """Test ConfigurationManager implementation."""
    
    def test_configuration_manager_initialization(self, temp_dir, mock_logger):
        """Test configuration manager initialization."""
        config_file = temp_dir / "config.json"
        
        manager = ConfigurationManager(str(config_file), mock_logger)
        
        # Should create default configuration
        assert manager.get('workspace_root') is not None
        assert config_file.exists()
    
    def test_configuration_manager_load_existing(self, temp_dir, mock_logger, sample_config_dict):
        """Test loading existing configuration file."""
        config_file = temp_dir / "config.json"
        
        # Create config file
        with open(config_file, 'w') as f:
            json.dump(sample_config_dict, f)
        
        manager = ConfigurationManager(str(config_file), mock_logger)
        
        assert manager.get('workspace_root') == sample_config_dict['workspace_root']
        assert manager.get('web_port') == sample_config_dict['web_port']
    
    def test_configuration_validation(self, temp_dir, mock_logger):
        """Test configuration validation."""
        config_file = temp_dir / "config.json"
        manager = ConfigurationManager(str(config_file), mock_logger)
        
        # Valid configuration should pass
        assert manager.validate() is True
        
        # Invalid configuration should fail
        manager.set('web_port', 'invalid_port')
        assert manager.validate() is False
    
    def test_get_build_config_returns_typed_object(self, temp_dir, mock_logger):
        """Test getting typed build configuration object."""
        config_file = temp_dir / "config.json"
        manager = ConfigurationManager(str(config_file), mock_logger)
        
        build_config = manager.get_build_config()
        assert isinstance(build_config, BuildConfiguration)
        assert build_config.workspace_root is not None