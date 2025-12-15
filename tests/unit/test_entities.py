"""
Unit tests for domain entities.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from src.domain.models.entities import (
    BuildTask, BuildStrategy, TaskStatus, BuildType, 
    BuildInfo, ProgressUpdate, BuildResult
)


class TestBuildStrategy:
    """Test BuildStrategy enum."""
    
    def test_from_string_valid_strategies(self):
        """Test creating BuildStrategy from valid string values."""
        assert BuildStrategy.from_string("simple") == BuildStrategy.SIMPLE
        assert BuildStrategy.from_string("DEVELOP") == BuildStrategy.DEVELOP
        assert BuildStrategy.from_string("Debug") == BuildStrategy.DEBUG
    
    def test_from_string_invalid_strategy(self):
        """Test creating BuildStrategy from invalid string."""
        with pytest.raises(ValueError, match="Invalid build strategy"):
            BuildStrategy.from_string("invalid")


class TestBuildTask:
    """Test BuildTask entity."""
    
    def test_build_task_creation_valid(self):
        """Test creating valid BuildTask."""
        task = BuildTask(
            branch="main",
            strategy=BuildStrategy.SIMPLE
        )
        
        assert task.branch == "main"
        assert task.strategy == BuildStrategy.SIMPLE
        assert task.status == TaskStatus.PENDING
        assert task.task_id is not None
        assert isinstance(task.created_at, datetime)
    
    def test_build_task_validation_empty_branch(self):
        """Test BuildTask validation with empty branch."""
        with pytest.raises(ValueError, match="Branch must be a non-empty string"):
            BuildTask(branch="", strategy=BuildStrategy.SIMPLE)
        
        with pytest.raises(ValueError, match="Branch cannot be only whitespace"):
            BuildTask(branch="   ", strategy=BuildStrategy.SIMPLE)
    
    def test_build_task_validation_invalid_branch_chars(self):
        """Test BuildTask validation with invalid branch characters."""
        with pytest.raises(ValueError, match="Branch name contains invalid characters"):
            BuildTask(branch="main<test", strategy=BuildStrategy.SIMPLE)
    
    def test_build_task_validation_special_strategy_requires_arg3(self):
        """Test BuildTask validation for SPECIAL strategy requiring arg3."""
        with pytest.raises(ValueError, match="arg3 is required for SPECIAL build strategy"):
            BuildTask(branch="main", strategy=BuildStrategy.SPECIAL)
        
        # Should work with arg3
        task = BuildTask(branch="main", strategy=BuildStrategy.SPECIAL, arg3="test_arg")
        assert task.arg3 == "test_arg"
    
    def test_build_task_start_execution(self):
        """Test starting task execution."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        task.status = TaskStatus.QUEUED
        
        task.start_execution(process_id=1234)
        
        assert task.status == TaskStatus.RUNNING
        assert task.process_id == 1234
        assert task.started_at is not None
    
    def test_build_task_start_execution_invalid_status(self):
        """Test starting execution with invalid status."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        # Default status is PENDING, not QUEUED
        
        with pytest.raises(ValueError, match="Cannot start task with status"):
            task.start_execution(process_id=1234)
    
    def test_build_task_complete_execution_success(self):
        """Test completing task execution successfully."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        task.status = TaskStatus.RUNNING
        
        task.complete_execution(return_code=0)
        
        assert task.status == TaskStatus.COMPLETED
        assert task.return_code == 0
        assert task.completed_at is not None
    
    def test_build_task_complete_execution_failure(self):
        """Test completing task execution with failure."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        task.status = TaskStatus.RUNNING
        
        task.complete_execution(return_code=1, error_message="Build failed")
        
        assert task.status == TaskStatus.FAILED
        assert task.return_code == 1
        assert task.error_message == "Build failed"
    
    def test_build_task_cancel_execution(self):
        """Test cancelling task execution."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        task.status = TaskStatus.QUEUED
        
        task.cancel_execution("User cancelled")
        
        assert task.status == TaskStatus.CANCELLED
        assert task.error_message == "User cancelled"
        assert task.completed_at is not None
    
    def test_build_task_get_duration(self):
        """Test getting task duration."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        # No duration if not started/completed
        assert task.get_duration() is None
        
        # Set times manually for testing
        task.started_at = datetime(2023, 1, 1, 10, 0, 0)
        task.completed_at = datetime(2023, 1, 1, 10, 5, 30)
        
        duration = task.get_duration()
        assert duration == 330.0  # 5 minutes 30 seconds
    
    def test_build_task_is_finished(self):
        """Test checking if task is finished."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        assert not task.is_finished()  # PENDING
        
        task.status = TaskStatus.COMPLETED
        assert task.is_finished()
        
        task.status = TaskStatus.FAILED
        assert task.is_finished()
        
        task.status = TaskStatus.CANCELLED
        assert task.is_finished()
    
    def test_build_task_serialization(self):
        """Test BuildTask to_dict and from_dict."""
        original_task = BuildTask(
            branch="main",
            strategy=BuildStrategy.SIMPLE,
            arg3="test"
        )
        
        # Convert to dict
        task_dict = original_task.to_dict()
        
        # Convert back to object
        restored_task = BuildTask.from_dict(task_dict)
        
        assert restored_task.branch == original_task.branch
        assert restored_task.strategy == original_task.strategy
        assert restored_task.arg3 == original_task.arg3
        assert restored_task.task_id == original_task.task_id


class TestBuildInfo:
    """Test BuildInfo value object."""
    
    def test_build_info_creation_valid(self):
        """Test creating valid BuildInfo."""
        build_info = BuildInfo(
            path="/path/to/build",
            folder_name="build_folder",
            size_str="1.5 GB",
            size_bytes=1610612736
        )
        
        assert build_info.path == "/path/to/build"
        assert build_info.folder_name == "build_folder"
        assert build_info.size_str == "1.5 GB"
        assert build_info.size_bytes == 1610612736
    
    def test_build_info_validation_empty_path(self):
        """Test BuildInfo validation with empty path."""
        with pytest.raises(ValueError, match="Path must be a non-empty string"):
            BuildInfo(path="", folder_name="test")
    
    def test_build_info_validation_negative_size(self):
        """Test BuildInfo validation with negative size."""
        with pytest.raises(ValueError, match="Size bytes cannot be negative"):
            BuildInfo(path="/test", folder_name="test", size_bytes=-1)
    
    def test_build_info_parse_from_folder_name(self):
        """Test parsing BuildInfo from folder name."""
        build_info = BuildInfo.parse_from_folder_name(
            path="/test/path",
            folder_name="20231201_ver_1.2.3_Development_main",
            size_str="2.1 GB",
            size_bytes=2147483648
        )
        
        assert build_info.ymd == "20231201"
        assert build_info.version == "1.2.3"
        assert build_info.build_type == BuildType.DEVELOPMENT
    
    def test_build_info_parse_shipping_build(self):
        """Test parsing shipping build from folder name."""
        build_info = BuildInfo.parse_from_folder_name(
            path="/test/path",
            folder_name="20231201_main_1.0.0",
            size_str="1.8 GB",
            size_bytes=1932735283
        )
        
        assert build_info.version == "1.0.0"
        assert build_info.build_type == BuildType.SHIPPING


class TestProgressUpdate:
    """Test ProgressUpdate value object."""
    
    def test_progress_update_creation_valid(self):
        """Test creating valid ProgressUpdate."""
        update = ProgressUpdate(
            task_id="test-task-123",
            stage="building",
            message="Compiling sources..."
        )
        
        assert update.task_id == "test-task-123"
        assert update.stage == "building"
        assert update.message == "Compiling sources..."
        assert isinstance(update.timestamp, datetime)
    
    def test_progress_update_validation_empty_fields(self):
        """Test ProgressUpdate validation with empty fields."""
        with pytest.raises(ValueError, match="Task ID must be a non-empty string"):
            ProgressUpdate(task_id="", stage="test", message="test")
        
        with pytest.raises(ValueError, match="Stage must be a non-empty string"):
            ProgressUpdate(task_id="test", stage="", message="test")
        
        with pytest.raises(ValueError, match="Message must be a non-empty string"):
            ProgressUpdate(task_id="test", stage="test", message="")


class TestBuildResult:
    """Test BuildResult entity."""
    
    def test_build_result_success(self):
        """Test creating successful BuildResult."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        build_info = BuildInfo(path="/test", folder_name="test", size_str="1 GB", size_bytes=1073741824)
        
        result = BuildResult(
            task=task,
            success=True,
            build_info=build_info,
            duration=120.5
        )
        
        assert result.success is True
        assert result.build_info == build_info
        assert result.duration == 120.5
    
    def test_build_result_failure(self):
        """Test creating failed BuildResult."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        result = BuildResult(
            task=task,
            success=False,
            error_message="Build compilation failed"
        )
        
        assert result.success is False
        assert result.error_message == "Build compilation failed"
        assert result.build_info is None
    
    def test_build_result_validation_success_without_build_info(self):
        """Test BuildResult validation - success requires build_info."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        with pytest.raises(ValueError, match="Successful builds must have build_info"):
            BuildResult(task=task, success=True)
    
    def test_build_result_validation_failure_without_error_message(self):
        """Test BuildResult validation - failure requires error_message."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        with pytest.raises(ValueError, match="Failed builds must have error_message"):
            BuildResult(task=task, success=False)
    
    def test_build_result_get_user_message_success(self):
        """Test getting user message for successful build."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        build_info = BuildInfo(
            path="/test", 
            folder_name="test", 
            version="1.0.0",
            build_type=BuildType.SHIPPING,
            size_str="1.5 GB", 
            size_bytes=1610612736
        )
        
        result = BuildResult(
            task=task,
            success=True,
            build_info=build_info,
            duration=150.0
        )
        
        message = result.get_user_message()
        assert "🎉 [main] 打包成功！" in message
        assert "⏱️ 耗时: 150.0s" in message
        assert "🔢 版本: 1.0.0 (Shipping)" in message
        assert "💾 大小: 1.5 GB" in message
    
    def test_build_result_get_user_message_failure(self):
        """Test getting user message for failed build."""
        task = BuildTask(branch="main", strategy=BuildStrategy.SIMPLE)
        
        result = BuildResult(
            task=task,
            success=False,
            error_message="Compilation error"
        )
        
        message = result.get_user_message()
        assert "⚠️ [main] 打包失败: Compilation error" in message