"""
Build orchestrator - coordinates all build-related operations.
"""

import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable, List
from datetime import datetime

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.file_manager import IFileManager
from src.domain.interfaces.task_queue import ITaskQueue, ITaskExecutor, QueuePriority
from src.domain.interfaces.web_server import IWebServer
from src.domain.interfaces.ai_provider import IAIProvider
from src.domain.models.entities import (
    BuildTask, BuildStrategy, TaskStatus, BuildResult, 
    BuildInfo, ProgressUpdate
)
from src.domain.models.configuration import BuildConfiguration, ScriptConfiguration
from src.domain.exceptions import BuildExecutionError, ValidationError


class BuildOrchestrator:
    """Orchestrates build operations with separation of pure functions and side effects."""
    
    def __init__(
        self,
        config: BuildConfiguration,
        script_config: ScriptConfiguration,
        file_manager: IFileManager,
        task_queue: ITaskQueue,
        task_executor: ITaskExecutor,
        web_server: IWebServer,
        ai_provider: IAIProvider,
        logger: ILogger
    ):
        self.config = config
        self.script_config = script_config
        self.file_manager = file_manager
        self.task_queue = task_queue
        self.task_executor = task_executor
        self.web_server = web_server
        self.ai_provider = ai_provider
        self.logger = logger
        
        # State management
        self._is_processing = False
        self._current_task: Optional[BuildTask] = None
        
        # Callbacks
        self._progress_callbacks: List[Callable[[ProgressUpdate], Awaitable[None]]] = []
        self._result_callbacks: List[Callable[[BuildResult], Awaitable[None]]] = []
    
    async def submit_build_request(
        self, 
        branch: str, 
        strategy: str, 
        arg3: Optional[str] = None,
        priority: QueuePriority = QueuePriority.NORMAL
    ) -> Dict[str, Any]:
        """Submit build request and return status information."""
        try:
            # Validate inputs (pure function)
            validation_result = self._validate_build_request(branch, strategy, arg3)
            if not validation_result['valid']:
                raise ValidationError(validation_result['error'])
            
            # Create build task (pure function)
            task = self._create_build_task(branch, strategy, arg3)
            
            # Set up paths (side effect)
            bat_dir, publish_root = self.file_manager.get_branch_paths(branch)
            task.bat_dir = bat_dir
            task.publish_root = publish_root
            
            # Check if already processing
            if self._is_processing:
                # Add to queue
                await self.task_queue.enqueue(task, priority)
                position = await self.task_queue.get_task_position(task.task_id)
                
                return {
                    'status': 'queued',
                    'task_id': task.task_id,
                    'position': position,
                    'message': f"⏳ 当前有任务运行中。您的任务 [{branch}-{strategy}] 已加入队列 (排在第 {position} 位)"
                }
            else:
                # Start processing immediately
                self._is_processing = True
                asyncio.create_task(self._process_build_task(task))
                
                return {
                    'status': 'started',
                    'task_id': task.task_id,
                    'message': f"✅ 任务 [{branch}-{strategy}] 开始执行..."
                }
                
        except Exception as e:
            self.logger.error(f"Failed to submit build request: {e}")
            raise
    
    async def cancel_build(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel build task."""
        try:
            if task_id:
                # Cancel specific task in queue
                cancelled = await self.task_queue.cancel_task(task_id)
                if cancelled:
                    return {'status': 'cancelled', 'message': f"任务 {task_id} 已取消"}
                else:
                    return {'status': 'not_found', 'message': f"任务 {task_id} 未找到"}
            else:
                # Cancel current executing task
                if self._current_task and self.task_executor.is_executing():
                    cancelled = await self.task_executor.cancel_current_task()
                    if cancelled:
                        return {'status': 'cancelled', 'message': "当前任务已取消"}
                    else:
                        return {'status': 'failed', 'message': "取消任务失败"}
                else:
                    return {'status': 'no_task', 'message': "没有正在执行的任务"}
                    
        except Exception as e:
            self.logger.error(f"Failed to cancel build: {e}")
            return {'status': 'error', 'message': f"取消失败: {e}"}
    
    async def get_build_status(self) -> Dict[str, Any]:
        """Get current build system status."""
        try:
            queue_status = await self.task_queue.get_queue_status()
            current_task = self.task_executor.get_current_task()
            
            return {
                'is_processing': self._is_processing,
                'current_task': {
                    'task_id': current_task.task_id if current_task else None,
                    'branch': current_task.branch if current_task else None,
                    'strategy': current_task.strategy.value if current_task else None,
                    'status': current_task.status.value if current_task else None
                } if current_task else None,
                'queue': queue_status,
                'web_server': self.web_server.get_server_info(),
                'ai_provider': self.ai_provider.get_provider_info()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get build status: {e}")
            return {'error': str(e)}
    
    def add_progress_callback(self, callback: Callable[[ProgressUpdate], Awaitable[None]]) -> None:
        """Add progress update callback."""
        self._progress_callbacks.append(callback)
    
    def add_result_callback(self, callback: Callable[[BuildResult], Awaitable[None]]) -> None:
        """Add build result callback."""
        self._result_callbacks.append(callback)
    
    # Pure functions (no side effects)
    
    def _validate_build_request(self, branch: str, strategy: str, arg3: Optional[str]) -> Dict[str, Any]:
        """Validate build request parameters (pure function)."""
        try:
            # Validate strategy
            build_strategy = BuildStrategy.from_string(strategy)
            
            # Validate branch
            if not branch or not isinstance(branch, str) or not branch.strip():
                return {'valid': False, 'error': 'Branch must be a non-empty string'}
            
            # Validate arg3 for special strategy
            if build_strategy == BuildStrategy.SPECIAL and not arg3:
                return {'valid': False, 'error': 'arg3 is required for SPECIAL build strategy'}
            
            return {'valid': True, 'strategy': build_strategy}
            
        except ValueError as e:
            return {'valid': False, 'error': str(e)}
    
    def _create_build_task(self, branch: str, strategy: str, arg3: Optional[str]) -> BuildTask:
        """Create build task from parameters (pure function)."""
        build_strategy = BuildStrategy.from_string(strategy)
        return BuildTask(
            branch=branch.strip(),
            strategy=build_strategy,
            arg3=arg3
        )
    
    def _determine_build_success(self, task: BuildTask, build_info: Optional[BuildInfo], return_code: int) -> Dict[str, Any]:
        """Determine if build was successful based on criteria (pure function)."""
        if return_code != 0:
            return {
                'success': False,
                'reason': f'Process exited with code {return_code}'
            }
        
        if not build_info:
            return {
                'success': False,
                'reason': 'No build artifacts detected'
            }
        
        if build_info.size_bytes < self.config.min_size_threshold:
            return {
                'success': False,
                'reason': f'Build artifact too small ({build_info.size_str})'
            }
        
        return {'success': True}
    
    def _format_build_messages(self, task: BuildTask, build_info: Optional[BuildInfo], duration: float) -> Dict[str, str]:
        """Format build result messages (pure function)."""
        if build_info:
            download_url = self.web_server.get_download_url(build_info.path)
            
            success_message = (
                f"🎉 [{task.branch}] 打包成功！\n"
                f"⏱️ 耗时: {self._format_duration(duration)}\n"
                f"🔢 版本: {build_info.version} ({build_info.build_type.value})\n"
                f"💾 大小: {build_info.size_str}\n"
                f"🌐 下载: {download_url}\n"
                f"📂 路径: {build_info.path}"
            )
            
            return {'success': success_message}
        else:
            return {'failure': f"⚠️ [{task.branch}] 打包失败"}
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format (pure function)."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        else:
            return f"{minutes}m {secs}s"
    
    # Side effect functions
    
    async def _process_build_task(self, task: BuildTask) -> None:
        """Process build task with error handling."""
        self._current_task = task
        
        try:
            # Pre-build checks
            await self._notify_progress(ProgressUpdate(
                task_id=task.task_id,
                stage="preparation",
                message="🔍 执行预检查..."
            ))
            
            disk_warning = self.file_manager.check_disk_space()
            if disk_warning:
                await self._notify_progress(ProgressUpdate(
                    task_id=task.task_id,
                    stage="warning",
                    message=disk_warning
                ))
            
            # Execute build
            start_time = datetime.now()
            await self.task_executor.execute_task(task)
            duration = (datetime.now() - start_time).total_seconds()
            
            # Process results
            build_result = await self._process_build_results(task, duration)
            
            # Notify callbacks
            await self._notify_result(build_result)
            
        except Exception as e:
            self.logger.error(f"Build task processing failed: {e}", task_id=task.task_id)
            
            # Create failure result
            build_result = BuildResult(
                task=task,
                success=False,
                error_message=str(e)
            )
            
            await self._notify_result(build_result)
        
        finally:
            self._current_task = None
            
            # Process next task in queue
            await self._process_next_task()
    
    async def _process_build_results(self, task: BuildTask, duration: float) -> BuildResult:
        """Process build results and generate AI analysis if needed."""
        # Get build artifacts
        found_build, build_info, build_path = self.file_manager.get_latest_build_info(
            task.publish_root,
            after_timestamp=task.started_at.timestamp() if task.started_at else None
        )
        
        # Determine success
        success_check = self._determine_build_success(task, build_info if found_build else None, task.return_code or -1)
        is_success = success_check['success']
        
        if is_success:
            # Generate changelog for successful builds
            changelog = await self._generate_changelog(task)
            
            return BuildResult(
                task=task,
                success=True,
                build_info=build_info,
                duration=duration
            )
        else:
            # Generate failure analysis
            failure_analysis = await self._generate_failure_analysis(task, build_path)
            
            return BuildResult(
                task=task,
                success=False,
                error_message=success_check['reason'],
                duration=duration
            )
    
    async def _generate_changelog(self, task: BuildTask) -> Optional[str]:
        """Generate AI-powered changelog."""
        try:
            # Get P4 changes (this would be implemented in a P4 service)
            # For now, return None to indicate no changelog
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to generate changelog: {e}")
            return None
    
    async def _generate_failure_analysis(self, task: BuildTask, build_path: Optional[str]) -> Optional[str]:
        """Generate AI-powered failure analysis."""
        try:
            # Get log content
            log_content = ""
            if build_path:
                log_file = self.file_manager.find_disk_log(build_path)
                if log_file:
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
                    except Exception:
                        pass
            
            if not log_content and task.error_message:
                log_content = task.error_message
            
            # Generate AI analysis
            if log_content:
                response = await self.ai_provider.analyze_failure(log_content)
                return response.completion_text if response.success else None
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to generate failure analysis: {e}")
            return None
    
    async def _process_next_task(self) -> None:
        """Process next task in queue."""
        try:
            next_task = await self.task_queue.dequeue()
            if next_task:
                # Continue processing
                asyncio.create_task(self._process_build_task(next_task))
            else:
                # No more tasks
                self._is_processing = False
                
        except Exception as e:
            self.logger.error(f"Failed to process next task: {e}")
            self._is_processing = False
    
    async def _notify_progress(self, progress: ProgressUpdate) -> None:
        """Notify progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                await callback(progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    async def _notify_result(self, result: BuildResult) -> None:
        """Notify result callbacks."""
        for callback in self._result_callbacks:
            try:
                await callback(result)
            except Exception as e:
                self.logger.warning(f"Result callback failed: {e}")