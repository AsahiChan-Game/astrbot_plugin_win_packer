"""
AI provider implementations with timeout and retry mechanisms.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from astrbot.api.star import Context

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.ai_provider import IAIProvider, AIRequest, AIResponse, IAIProviderFactory
from src.domain.exceptions import AIServiceError


class AstrBotAIProvider:
    """AI provider implementation using AstrBot's provider system."""
    
    def __init__(self, context: Context, logger: ILogger, timeout: float = 30.0, max_retries: int = 3):
        self.context = context
        self.logger = logger
        self.timeout = timeout
        self.max_retries = max_retries
        self.provider_name = "AstrBot"
    
    async def text_chat(self, prompt: str, session_id: Optional[str] = None, **kwargs) -> AIResponse:
        """Send text chat request to AI provider."""
        request = AIRequest(
            prompt=prompt,
            session_id=session_id,
            context=kwargs
        )
        
        return await self._execute_with_retry(self._text_chat_impl, request)
    
    async def analyze_failure(self, log_content: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Analyze build failure logs and provide suggestions."""
        # Extract smart log content to reduce token usage
        smart_log = self._extract_smart_log(log_content)
        
        prompt = (
            "UE5打包失败分析。请分析以下日志并提供：\n"
            "1. 核心失败原因\n"
            "2. 具体修复建议\n"
            "3. 预防措施\n\n"
            f"日志内容:\n{smart_log}"
        )
        
        request = AIRequest(
            prompt=prompt,
            context=context or {}
        )
        
        return await self._execute_with_retry(self._text_chat_impl, request)
    
    async def generate_changelog(self, changes_text: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Generate user-friendly changelog from technical changes."""
        prompt = (
            "这是最近的 Perforce 提交记录，请总结为一份通俗易懂的'更新公告'：\n"
            "要求：\n"
            "1. 去除技术细节，使用用户友好的语言\n"
            "2. 按功能分类整理\n"
            "3. 突出重要变更\n"
            "4. 保持简洁明了\n\n"
            f"提交记录:\n{changes_text}"
        )
        
        request = AIRequest(
            prompt=prompt,
            context=context or {}
        )
        
        return await self._execute_with_retry(self._text_chat_impl, request)
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information and capabilities."""
        return {
            'name': self.provider_name,
            'type': 'astrbot',
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'capabilities': ['text_chat', 'failure_analysis', 'changelog_generation'],
            'available': self.is_available()
        }
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        try:
            provider = self.context.get_using_provider()
            return provider is not None
        except Exception:
            return False
    
    async def _execute_with_retry(self, func, request: AIRequest) -> AIResponse:
        """Execute AI request with timeout and retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                # Execute with timeout
                response = await asyncio.wait_for(
                    func(request),
                    timeout=self.timeout
                )
                
                response.response_time = time.time() - start_time
                response.provider = self.provider_name
                
                self.logger.info(
                    f"AI request successful",
                    provider=self.provider_name,
                    attempt=attempt + 1,
                    response_time=response.response_time
                )
                
                return response
                
            except asyncio.TimeoutError:
                last_error = f"Request timeout after {self.timeout}s"
                self.logger.warning(f"AI request timeout (attempt {attempt + 1})")
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"AI request failed (attempt {attempt + 1}): {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s...
                await asyncio.sleep(wait_time)
        
        # All retries failed
        error_msg = f"AI request failed after {self.max_retries} attempts: {last_error}"
        self.logger.error(error_msg)
        
        return AIResponse(
            completion_text="AI 服务暂时不可用，请稍后重试。",
            success=False,
            error_message=error_msg,
            provider=self.provider_name
        )
    
    async def _text_chat_impl(self, request: AIRequest) -> AIResponse:
        """Internal implementation of text chat."""
        try:
            provider = self.context.get_using_provider()
            if not provider:
                raise AIServiceError("No AI provider available")
            
            # Make request to AstrBot provider
            response = await provider.text_chat(request.prompt, session_id=request.session_id)
            
            return AIResponse(
                completion_text=response.completion_text,
                success=True,
                tokens_used=getattr(response, 'tokens_used', None)
            )
            
        except Exception as e:
            raise AIServiceError(f"AstrBot provider error: {e}", provider=self.provider_name)
    
    def _extract_smart_log(self, text: str, max_len: int = 4000) -> str:
        """Extract relevant parts of log for AI analysis."""
        if not text:
            return "(Empty log)"
        
        lines = text.splitlines()
        
        # Get last 30 lines (tail)
        tail_lines = lines[-30:]
        
        # Extract error lines from the rest
        error_lines = []
        error_keywords = ["Error:", "Critical:", "Fatal:", "error C", "Exception:", "Failed:"]
        
        for i, line in enumerate(lines[:-30]):  # Exclude tail lines
            if any(keyword in line for keyword in error_keywords):
                error_lines.append(f"[L{i+1}] {line.strip()}")
        
        # Limit error lines if too many
        if len(error_lines) > 20:
            error_lines = error_lines[:10] + ["..."] + error_lines[-10:]
        
        # Combine sections
        result_parts = []
        
        if error_lines:
            result_parts.append("关键错误:")
            result_parts.extend(error_lines)
        
        result_parts.append("\n最近输出:")
        result_parts.extend(tail_lines)
        
        result = "\n".join(result_parts)
        
        # Truncate if too long
        if len(result) > max_len:
            result = result[:max_len] + "\n[日志已截断]"
        
        return result


class FallbackAIProvider:
    """Fallback AI provider that returns simple responses when main provider fails."""
    
    def __init__(self, logger: ILogger):
        self.logger = logger
        self.provider_name = "Fallback"
    
    async def text_chat(self, prompt: str, session_id: Optional[str] = None, **kwargs) -> AIResponse:
        """Return simple fallback response."""
        return AIResponse(
            completion_text="AI 服务暂时不可用，无法提供智能分析。",
            success=False,
            error_message="Using fallback provider",
            provider=self.provider_name
        )
    
    async def analyze_failure(self, log_content: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Return simple failure analysis."""
        return AIResponse(
            completion_text=(
                "构建失败分析 (简化版):\n"
                "1. 请检查构建日志中的错误信息\n"
                "2. 确认所有依赖项已正确安装\n"
                "3. 检查磁盘空间是否充足\n"
                "4. 尝试清理并重新构建项目"
            ),
            success=False,
            error_message="Using fallback analysis",
            provider=self.provider_name
        )
    
    async def generate_changelog(self, changes_text: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Return simple changelog."""
        return AIResponse(
            completion_text="更新日志生成功能暂时不可用，请查看原始提交记录。",
            success=False,
            error_message="Using fallback changelog",
            provider=self.provider_name
        )
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get fallback provider info."""
        return {
            'name': self.provider_name,
            'type': 'fallback',
            'capabilities': ['basic_responses'],
            'available': True
        }
    
    def is_available(self) -> bool:
        """Fallback is always available."""
        return True


class AIProviderFactory:
    """Factory for creating AI providers with fallback support."""
    
    def __init__(self, logger: ILogger):
        self.logger = logger
        self._providers: Dict[str, type] = {
            'astrbot': AstrBotAIProvider,
            'fallback': FallbackAIProvider
        }
    
    def create_provider(self, provider_type: str, config: Dict[str, Any]) -> IAIProvider:
        """Create AI provider instance with fallback."""
        try:
            if provider_type not in self._providers:
                self.logger.warning(f"Unknown AI provider type: {provider_type}, using fallback")
                return FallbackAIProvider(self.logger)
            
            provider_class = self._providers[provider_type]
            
            if provider_type == 'astrbot':
                context = config.get('context')
                timeout = config.get('timeout', 30.0)
                max_retries = config.get('max_retries', 3)
                
                if not context:
                    raise AIServiceError("AstrBot context required for astrbot provider")
                
                return provider_class(context, self.logger, timeout, max_retries)
            
            elif provider_type == 'fallback':
                return provider_class(self.logger)
            
            else:
                raise AIServiceError(f"Unsupported provider configuration: {provider_type}")
                
        except Exception as e:
            self.logger.error(f"Failed to create AI provider {provider_type}: {e}")
            # Always fallback to simple provider
            return FallbackAIProvider(self.logger)
    
    def get_available_providers(self) -> list[str]:
        """Get list of available provider types."""
        return list(self._providers.keys())
    
    def register_provider(self, provider_type: str, provider_class: type) -> None:
        """Register custom AI provider."""
        self._providers[provider_type] = provider_class
        self.logger.info(f"Registered AI provider: {provider_type}")