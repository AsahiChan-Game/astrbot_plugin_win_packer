"""
AI provider interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AIRequest:
    """AI service request data."""
    prompt: str
    session_id: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class AIResponse:
    """AI service response data."""
    completion_text: str
    success: bool = True
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    response_time: Optional[float] = None
    provider: Optional[str] = None


class IAIProvider(ABC):
    """Interface for AI service providers."""
    
    @abstractmethod
    async def text_chat(self, prompt: str, session_id: Optional[str] = None, **kwargs) -> AIResponse:
        """Send text chat request to AI provider."""
        pass
    
    @abstractmethod
    async def analyze_failure(self, log_content: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Analyze build failure logs and provide suggestions."""
        pass
    
    @abstractmethod
    async def generate_changelog(self, changes_text: str, context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """Generate user-friendly changelog from technical changes."""
        pass
    
    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information and capabilities."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class IAIProviderFactory(ABC):
    """Factory interface for creating AI providers."""
    
    @abstractmethod
    def create_provider(self, provider_type: str, config: Dict[str, Any]) -> IAIProvider:
        """Create AI provider instance."""
        pass
    
    @abstractmethod
    def get_available_providers(self) -> list[str]:
        """Get list of available provider types."""
        pass