"""
Unreal Engine Build Packer Plugin - Refactored Version
完全兼容原有 AstrBot 插件接口，同时提供优化的架构和功能
"""

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, At, Image
import asyncio
import os
from pathlib import Path

# 导入重构后的组件
from src.domain.models.configuration import BuildConfiguration, ScriptConfiguration
from src.domain.models.entities import BuildStrategy, ProgressUpdate, BuildResult
from src.infrastructure.configuration.manager import ConfigurationManager
from src.infrastructure.logging.logger import LoggerFactory
from src.infrastructure.error_handling.handler import ErrorHandler
from src.infrastructure.file_system.manager import SecureFileManager
from src.infrastructure.task_management.queue import ThreadSafeTaskQueue
from src.infrastructure.task_management.executor import TaskExecutor
from src.infrastructure.web_server.server import ModularWebServer
from src.infrastructure.ai_integration.providers import AIProviderFactory
from src.application.services.build_orchestrator import BuildOrchestrator
from src.application.services.statistics_manager import StatisticsManager


@register("astrbot_plugin_Game_packer", "YourName", "Unreal打包插件", "4.0.0")
class UnrealBuilderRefactored(Star):
    """重构版本的 UnrealBuilder - 保持完全兼容性的同时提供优化架构"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        print("[GamePacker] v4.0.0 加载: 重构优化版 (模块化架构)")
        
        # 初始化组件
        self._initialize_components()
        
        # 设置回调
        self._setup_callbacks()
        
        # 启动服务
        asyncio.create_task(self._start_services())
    
    def _initialize_components(self):
        """初始化所有组件"""
        # 配置文件路径
        config_file = os.path.join(os.path.dirname(__file__), "config.json")
        
        # 创建日志器
        self.logger = LoggerFactory.create_logger("UnrealBuilder", "INFO")
        
        # 配置管理器
        self.config_manager = ConfigurationManager(config_file, self.logger)
        self.build_config = self.config_manager.get_build_config()
        self.script_config = ScriptConfiguration()
        
        # 错误处理器
        self.error_handler = ErrorHandler(self.logger)
        
        # 文件管理器
        self.file_manager = SecureFileManager(self.build_config, self.logger)
        
        # 任务队列和执行器
        queue_persistence_file = os.path.join(os.path.dirname(__file__), "task_queue.json")
        self.task_queue = ThreadSafeTaskQueue(self.logger, queue_persistence_file)
        self.task_executor = TaskExecutor(self.logger)
        
        # Web 服务器
        self.web_server = ModularWebServer(self.build_config, self.logger)
        
        # AI 提供者
        ai_factory = AIProviderFactory(self.logger)
        self.ai_provider = ai_factory.create_provider('astrbot', {
            'context': self.context,
            'timeout': self.build_config.ai_timeout,
            'max_retries': self.build_config.ai_max_retries
        })
        
        # 统计管理器
        self.stats_manager = StatisticsManager(self.build_config, self.logger)
        
        # 构建编排器
        self.build_orchestrator = BuildOrchestrator(
            config=self.build_config,
            script_config=self.script_config,
            file_manager=self.file_manager,
            task_queue=self.task_queue,
            task_executor=self.task_executor,
            web_server=self.web_server,
            ai_provider=self.ai_provider,
            logger=self.logger
        )
        
        self.logger.info("所有组件初始化完成")
    
    def _setup_callbacks(self):
        """设置回调函数"""
        # 进度更新回调
        self.build_orchestrator.add_progress_callback(self._on_progress_update)
        
        # 构建结果回调
        self.build_orchestrator.add_result_callback(self._on_build_result)
        
        # 任务执行器进度回调
        self.task_executor.add_progress_callback(self._on_executor_progress)
    
    async def _start_services(self):
        """启动后台服务"""
        try:
            # 启动 Web 服务器
            await self.web_server.start()
            
            # 启动配置热重载
            self.config_manager.start_hot_reload()
            
            self.logger.info("所有服务启动完成")
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'component': 'service_startup'})
            self.logger.error(f"服务启动失败: {error_msg}")
    
    # ================================================================
    # AstrBot 命令处理器 - 保持原有接口兼容性
    # ================================================================
    
    @filter.command("pack")
    async def pack(self, event: AstrMessageEvent, branch: str, strategy: str, arg3: str = None):
        """通用打包指令 - 兼容原有接口"""
        try:
            # 使用新的构建编排器
            result = await self.build_orchestrator.submit_build_request(
                branch=branch,
                strategy=strategy,
                arg3=arg3
            )
            
            yield event.plain_result(result['message'])
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {
                'command': 'pack',
                'branch': branch,
                'strategy': strategy
            })
            yield event.plain_result(error_msg)
    
    @filter.command("build_stats")
    async def build_stats(self, event: AstrMessageEvent):
        """查看打包耗时统计 - 兼容原有接口"""
        try:
            # 使用新的统计管理器
            report = self.stats_manager.generate_statistics_report()
            
            if isinstance(report, tuple):
                # 有图表的情况
                text_report, chart_path = report
                yield event.chain_result([
                    Plain(text_report),
                    Image.fromFileSystem(chart_path)
                ])
            else:
                # 纯文本报告
                yield event.plain_result(report)
                
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'command': 'build_stats'})
            yield event.plain_result(error_msg)
    
    @filter.command("build_stop")
    async def build_stop(self, event: AstrMessageEvent):
        """停止构建任务 - 兼容原有接口"""
        try:
            result = await self.build_orchestrator.cancel_build()
            yield event.plain_result(result['message'])
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'command': 'build_stop'})
            yield event.plain_result(error_msg)
    
    @filter.command("build_simple")
    async def build_simple(self, event: AstrMessageEvent):
        """兼容旧指令"""
        async for msg in self.pack(event, "main", "simple"):
            yield msg
    
    # ================================================================
    # 新增的高级命令
    # ================================================================
    
    @filter.command("build_status")
    async def build_status(self, event: AstrMessageEvent):
        """获取构建系统状态"""
        try:
            status = await self.build_orchestrator.get_build_status()
            
            if 'error' in status:
                yield event.plain_result(f"❌ 获取状态失败: {status['error']}")
                return
            
            # 格式化状态信息
            status_msg = "🔧 **构建系统状态**\n\n"
            
            # 当前任务
            if status['current_task']:
                task = status['current_task']
                status_msg += f"🏗️ **当前任务**: [{task['branch']}] {task['strategy']} ({task['status']})\n"
            else:
                status_msg += "🏗️ **当前任务**: 无\n"
            
            # 队列状态
            queue = status['queue']
            status_msg += f"📋 **队列**: {queue['total_size']} 个任务\n"
            
            # Web 服务器
            web = status['web_server']
            if web['is_running']:
                status_msg += f"🌐 **Web服务**: 运行中 (http://{web['host']}:{web['port']})\n"
            else:
                status_msg += "🌐 **Web服务**: 已停止\n"
            
            # AI 服务
            ai = status['ai_provider']
            status_msg += f"🤖 **AI服务**: {ai['name']} ({'可用' if ai['available'] else '不可用'})\n"
            
            yield event.plain_result(status_msg)
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'command': 'build_status'})
            yield event.plain_result(error_msg)
    
    @filter.command("build_queue")
    async def build_queue(self, event: AstrMessageEvent):
        """查看任务队列"""
        try:
            queue_status = await self.task_queue.get_queue_status()
            
            if queue_status['total_size'] == 0:
                yield event.plain_result("📋 任务队列为空")
                return
            
            msg = f"📋 **任务队列** ({queue_status['total_size']} 个任务)\n\n"
            
            # 按优先级显示
            for priority, count in queue_status['tasks_by_priority'].items():
                if count > 0:
                    msg += f"🔸 {priority}: {count} 个任务\n"
            
            # 按分支显示
            msg += "\n**按分支分组**:\n"
            for branch, count in queue_status['tasks_by_branch'].items():
                msg += f"📂 {branch}: {count} 个任务\n"
            
            if queue_status['oldest_task_age']:
                oldest_age = queue_status['oldest_task_age'] / 60  # 转换为分钟
                msg += f"\n⏰ 最早任务等待时间: {oldest_age:.1f} 分钟"
            
            yield event.plain_result(msg)
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'command': 'build_queue'})
            yield event.plain_result(error_msg)
    
    @filter.command("build_clear_queue")
    async def build_clear_queue(self, event: AstrMessageEvent):
        """清空任务队列"""
        try:
            cleared_count = await self.task_queue.clear_queue()
            yield event.plain_result(f"🗑️ 已清空队列，移除了 {cleared_count} 个任务")
            
        except Exception as e:
            error_msg = await self.error_handler.handle_error(e, {'command': 'build_clear_queue'})
            yield event.plain_result(error_msg)
    
    # ================================================================
    # 回调处理器
    # ================================================================
    
    async def _on_progress_update(self, progress: ProgressUpdate):
        """处理进度更新"""
        self.logger.info(f"Progress: {progress.stage} - {progress.message}")
        # 这里可以添加实时进度通知逻辑
    
    async def _on_build_result(self, result: BuildResult):
        """处理构建结果"""
        # 保存统计数据
        if result.success and result.duration:
            key = f"{result.task.branch}_{result.task.strategy.value}"
            self.stats_manager.save_build_time(key, result.duration)
        
        self.logger.info(f"Build completed: {result.task.task_id}, Success: {result.success}")
    
    async def _on_executor_progress(self, progress: ProgressUpdate):
        """处理执行器进度更新"""
        # 这里可以发送实时进度消息给用户
        pass
    
    # ================================================================
    # 兼容性方法 - 保持与原代码的接口一致
    # ================================================================
    
    def get_safe_user_id(self, event: AstrMessageEvent):
        """获取用户ID - 兼容原有方法"""
        try:
            if hasattr(event, "unified_msg_origin"): 
                return event.unified_msg_origin.sender_id
            if hasattr(event, "get_sender_id"): 
                return event.get_sender_id()
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "sender"): 
                return event.message_obj.sender.user_id
        except: 
            pass
        return None
    
    def get_download_link(self, local_path: str) -> str:
        """获取下载链接 - 兼容原有方法"""
        return self.web_server.get_download_url(local_path)
    
    def fmt_time(self, seconds: float) -> str:
        """格式化时间 - 兼容原有方法"""
        return self.stats_manager._format_duration(seconds)
    
    # ================================================================
    # 清理资源
    # ================================================================
    
    def __del__(self):
        """清理资源"""
        try:
            # 停止配置热重载
            if hasattr(self, 'config_manager'):
                self.config_manager.stop_hot_reload()
            
            # 清理临时文件
            if hasattr(self, 'file_manager'):
                self.file_manager.cleanup_temp_files()
                
        except Exception:
            pass  # 忽略清理时的错误