"""
Web server interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IWebServer(ABC):
    """Interface for web server operations."""
    
    @abstractmethod
    async def start(self) -> bool:
        """Start the web server."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the web server."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if server is running."""
        pass
    
    @abstractmethod
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information (host, port, etc.)."""
        pass
    
    @abstractmethod
    def get_download_url(self, file_path: str) -> str:
        """Generate download URL for a file."""
        pass
    
    @abstractmethod
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        pass