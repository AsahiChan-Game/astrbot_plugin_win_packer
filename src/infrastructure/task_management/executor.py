"""
Task executor implementation with process management.
"""

import asyncio
import subprocess
from typing import Optional, Callable, Awaitable, Dict, Any
from datetime import datetime

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.task_queue import ITaskExecutor
from src.domain.models.entities import BuildTask, TaskStatus, ProgressUpdate
from src.domain.exceptions import ProcessError, TaskQueueError


class TaskExecutor:
    """Task executor with process management and progress tracking."""
    
    def __init__(self, logger: ILogger):
        self.logger = logger
        self._current_task: Optional[BuildTask] = None
        self._current_process: Optional[asyncio.subprocess.Process] = None
        self._is_executing = False
        self._is_cancelled = False
        self._progress_callbacks: list[Callable[[ProgressUpdate], Awaitable[None]]] = []
        
        # Process execution settings
        self._process_timeout = 5.0  # seconds for readline timeout
        self._max_log_lines = 10000
    
    async def execute_task(self, task: BuildTask) -> None:
        """Execute a single task."""
        if self._is_executing:
            raise TaskQueueError("Executor is already running a task")
        
        self._current_task = task
        self._is_executing = True
        self._is_cancelled = False
        
        try:
            self.logger.info(
                f"Starting task execution: {task.task_id}",
                task_id=task.task_id,
                branch=task.branch,
                strategy=task.strategy.value
            )
            
            # Start task execution
            process_id = await self._start_build_process(task)
            task.start_execution(process_id)
            
            # Execute the build
            return_code, log_content = await self._run_build_process(task)
            
            # Complete task
            if self._is_cancelled:
                task.cancel_execution("Task was cancelled during execution")
            else:
                error_message = None if return_code == 0 else f"Process exited with code {return_code}"
                task.complete_execution(return_code, error_message)
            
            self.logger.info(
                f"Task execution completed: {task.task_id}",
                task_id=task.task_id,
                return_code=return_code,
                status=task.status.value,
                duration=task.get_duration()
            )
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}", task_id=task.task_id)
            task.complete_execution(-1, str(e))
            raise
        
        finally:
            self._current_task = None
            self._current_process = None
            self._is_executing = False
            self._is_cancelled = False
    
    async def cancel_current_task(self) -> bool:
        """Cancel currently executing task."""
        if not self._is_executing or not self._current_process:
            return False
        
        try:
            self._is_cancelled = True
            
            # Terminate process and all children (Windows)
            if self._current_process.returncode is None:
                try:
                    # Use taskkill to terminate process tree on Windows
                    subprocess.run(
                        f"taskkill /F /T /PID {self._current_process.pid}",
                        shell=True,
                        check=False
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to use taskkill: {e}")
                    # Fallback to process.terminate()
                    self._current_process.terminate()
                    try:
                        await asyncio.wait_for(self._current_process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        self._current_process.kill()
            
            self.logger.info(f"Task cancelled: {self._current_task.task_id if self._current_task else 'unknown'}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel task: {e}")
            return False
    
    def is_executing(self) -> bool:
        """Check if executor is currently running a task."""
        return self._is_executing
    
    def get_current_task(self) -> Optional[BuildTask]:
        """Get currently executing task."""
        return self._current_task
    
    def add_progress_callback(self, callback: Callable[[ProgressUpdate], Awaitable[None]]) -> None:
        """Add progress update callback."""
        self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[ProgressUpdate], Awaitable[None]]) -> None:
        """Remove progress update callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    async def _start_build_process(self, task: BuildTask) -> int:
        """Start the build process and return process ID."""
        # Build command
        script_map = {
            "simple": "packsimple.bat",
            "develop": "packdevelop.bat",
            "debug": "packdebug.bat", 
            "special": "packspecial.bat",
            "all": "aaaaaaaaaaaaaaaaaaaalll.bat"
        }
        
        script_name = script_map.get(task.strategy.value, "packet.bat")
        script_path = f"{task.bat_dir}\\{script_name}"
        
        # Check if script exists, fallback to packet.bat
        import os
        if not os.path.exists(script_path):
            script_path = f"{task.bat_dir}\\packet.bat"
        
        # Build command list
        cmd = [script_path]
        if task.strategy.value == "special" and task.arg3:
            cmd.append(task.arg3)
        
        # Convert to command string for Windows
        cmd_str = subprocess.list2cmdline(cmd)
        
        self.logger.info(f"Executing command: {cmd_str}", task_id=task.task_id)
        
        # Start process
        try:
            self._current_process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=task.bat_dir
            )
            
            return self._current_process.pid
            
        except Exception as e:
            raise ProcessError(f"Failed to start build process: {e}", command=cmd_str)
    
    async def _run_build_process(self, task: BuildTask) -> tuple[int, str]:
        """Run build process with progress tracking."""
        if not self._current_process:
            raise ProcessError("No process to run")
        
        # Progress stage mapping
        stages = {
            "Running AutomationTool...": "⚙️ Init UAT",
            "Command: BuildCookRun": "🏗️ Start Build",
            "Cook: ": "🍳 Cooking...",
            "Stage: ": "📦 Staging...",
            "Package: ": "🚚 Packaging...",
            "BUILD SUCCESSFUL": "✅ Finalizing..."
        }
        
        triggered_stages = set()
        log_lines = []
        
        try:
            while True:
                if self._is_cancelled:
                    break
                
                try:
                    # Read line with timeout
                    line = await asyncio.wait_for(
                        self._current_process.stdout.readline(),
                        timeout=self._process_timeout
                    )
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if self._current_process.returncode is not None:
                        break
                    continue
                
                if not line:
                    break
                
                # Decode line
                try:
                    line_str = line.decode('gbk', errors='ignore').strip()
                except UnicodeDecodeError:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                
                if not line_str:
                    continue
                
                # Store log line (with limit)
                if len(log_lines) < self._max_log_lines:
                    log_lines.append(line_str)
                
                # Check for progress stages
                for trigger, message in stages.items():
                    if trigger in line_str and trigger not in triggered_stages:
                        triggered_stages.add(trigger)
                        
                        # Send progress update
                        progress = ProgressUpdate(
                            task_id=task.task_id,
                            stage=trigger,
                            message=message
                        )
                        
                        await self._notify_progress(progress)
                        break
            
            # Wait for process completion
            await self._current_process.wait()
            return_code = self._current_process.returncode
            
            return return_code, "\n".join(log_lines)
            
        except Exception as e:
            self.logger.error(f"Error during process execution: {e}", task_id=task.task_id)
            raise ProcessError(f"Process execution failed: {e}", process_id=self._current_process.pid)
    
    async def _notify_progress(self, progress: ProgressUpdate) -> None:
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                await callback(progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")