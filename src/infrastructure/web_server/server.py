"""
Modular web server implementation with connection management and security.
"""

import os
import socket
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from functools import partial
import http.server
import socketserver
from urllib.parse import unquote
import mimetypes

from src.domain.interfaces.base import ILogger
from src.domain.interfaces.web_server import IWebServer
from src.domain.models.configuration import BuildConfiguration
from src.domain.exceptions import NetworkError, SecurityError, FileSystemError


class SecureHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Secure HTTP request handler with access controls and logging."""
    
    def __init__(self, *args, base_directory: str, logger: ILogger, **kwargs):
        self.base_directory = Path(base_directory)
        self.logger = logger
        self.start_time = time.time()
        super().__init__(*args, directory=base_directory, **kwargs)
    
    def do_GET(self):
        """Handle GET requests with security validation."""
        try:
            # Log request
            self.logger.info(
                f"HTTP GET request: {self.path}",
                client_ip=self.client_address[0],
                user_agent=self.headers.get('User-Agent', 'Unknown')
            )
            
            # Validate path for security
            if not self._is_safe_path(self.path):
                self.send_error(403, "Access denied")
                return
            
            # Check file size for large file handling
            file_path = self._get_file_path(self.path)
            if file_path and file_path.exists():
                file_size = file_path.stat().st_size
                if file_size > 100 * 1024 * 1024:  # 100MB
                    self._handle_large_file(file_path)
                    return
            
            # Use parent implementation for normal files
            super().do_GET()
            
        except Exception as e:
            self.logger.error(f"Error handling GET request: {e}", path=self.path)
            self.send_error(500, "Internal server error")
    
    def _is_safe_path(self, path: str) -> bool:
        """Validate path for security (prevent directory traversal)."""
        try:
            # Decode URL
            decoded_path = unquote(path)
            
            # Check for directory traversal attempts
            if '..' in decoded_path or decoded_path.startswith('/..'):
                return False
            
            # Resolve path relative to base directory
            requested_path = self.base_directory / decoded_path.lstrip('/')
            resolved_path = requested_path.resolve()
            
            # Ensure path is within base directory
            return str(resolved_path).startswith(str(self.base_directory.resolve()))
            
        except Exception:
            return False
    
    def _get_file_path(self, path: str) -> Optional[Path]:
        """Get file path for the request."""
        try:
            decoded_path = unquote(path)
            file_path = self.base_directory / decoded_path.lstrip('/')
            return file_path if file_path.exists() else None
        except Exception:
            return None
    
    def _handle_large_file(self, file_path: Path) -> None:
        """Handle large file downloads with streaming."""
        try:
            file_size = file_path.stat().st_size
            
            # Send headers
            self.send_response(200)
            self.send_header("Content-Type", self._get_content_type(file_path))
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            
            # Stream file in chunks
            chunk_size = 64 * 1024  # 64KB chunks
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            
            self.logger.info(f"Large file served: {file_path.name}", size=file_size)
            
        except Exception as e:
            self.logger.error(f"Error serving large file: {e}")
            self.send_error(500, "Error serving file")
    
    def _get_content_type(self, file_path: Path) -> str:
        """Get content type for file."""
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or 'application/octet-stream'
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        self.logger.debug(f"HTTP: {format % args}")


class ModularWebServer:
    """Modular web server with connection management and security features."""
    
    def __init__(self, config: BuildConfiguration, logger: ILogger):
        self.config = config
        self.logger = logger
        
        # Server state
        self._server: Optional[socketserver.TCPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._local_ip: Optional[str] = None
        
        # Statistics
        self._start_time: Optional[float] = None
        self._request_count = 0
        self._bytes_served = 0
        
        # Connection management
        self._max_connections = 10
        self._connection_timeout = 30  # seconds
    
    async def start(self) -> bool:
        """Start the web server."""
        if self._is_running:
            self.logger.warning("Web server is already running")
            return True
        
        try:
            # Get local IP
            self._local_ip = self._get_local_ip()
            
            # Ensure publish directory exists
            publish_dir = Path(self.config.publish_root_base)
            publish_dir.mkdir(parents=True, exist_ok=True)
            
            # Create request handler with our configuration
            handler_class = partial(
                SecureHTTPRequestHandler,
                base_directory=str(publish_dir),
                logger=self.logger
            )
            
            # Create server with connection management
            self._server = self._create_server(handler_class)
            
            # Start server in background thread
            self._server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="WebServer"
            )
            self._server_thread.start()
            
            self._is_running = True
            self._start_time = time.time()
            
            self.logger.info(
                f"Web server started at http://{self._local_ip}:{self.config.web_port}",
                host=self._local_ip,
                port=self.config.web_port,
                directory=str(publish_dir)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
            raise NetworkError(f"Failed to start web server: {e}", port=self.config.web_port)
    
    async def stop(self) -> None:
        """Stop the web server."""
        if not self._is_running:
            return
        
        try:
            self._is_running = False
            
            if self._server:
                self._server.shutdown()
                self._server.server_close()
            
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5.0)
            
            self.logger.info("Web server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping web server: {e}")
        finally:
            self._server = None
            self._server_thread = None
            self._start_time = None
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._is_running and self._server is not None
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            'host': self._local_ip,
            'port': self.config.web_port,
            'is_running': self._is_running,
            'base_directory': self.config.publish_root_base,
            'start_time': self._start_time,
            'uptime': time.time() - self._start_time if self._start_time else 0
        }
    
    def get_download_url(self, file_path: str) -> str:
        """Generate download URL for a file."""
        if not self._is_running or not self._local_ip:
            return "Server not running"
        
        try:
            # Validate file path
            abs_file_path = Path(file_path).resolve()
            base_path = Path(self.config.publish_root_base).resolve()
            
            if not str(abs_file_path).startswith(str(base_path)):
                raise SecurityError(f"File path outside base directory: {file_path}")
            
            # Generate relative path for URL
            rel_path = abs_file_path.relative_to(base_path)
            url_path = str(rel_path).replace('\\', '/')
            
            return f"http://{self._local_ip}:{self.config.web_port}/{url_path}"
            
        except Exception as e:
            self.logger.error(f"Error generating download URL: {e}", file_path=file_path)
            return "URL generation failed"
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        uptime = time.time() - self._start_time if self._start_time else 0
        
        return {
            'uptime_seconds': uptime,
            'request_count': self._request_count,
            'bytes_served': self._bytes_served,
            'requests_per_minute': (self._request_count / (uptime / 60)) if uptime > 0 else 0,
            'is_running': self._is_running,
            'thread_alive': self._server_thread.is_alive() if self._server_thread else False
        }
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            # Fallback to hostname resolution
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"
    
    def _create_server(self, handler_class) -> socketserver.TCPServer:
        """Create TCP server with connection management."""
        try:
            # Enable address reuse
            socketserver.TCPServer.allow_reuse_address = True
            
            # Create server
            server = socketserver.ThreadingTCPServer(
                (self.config.web_host, self.config.web_port),
                handler_class
            )
            
            # Configure threading server
            server.daemon_threads = True
            server.max_children = self._max_connections
            
            return server
            
        except OSError as e:
            if e.errno == 10048:  # Address already in use (Windows)
                raise NetworkError(f"Port {self.config.web_port} is already in use", port=self.config.web_port)
            else:
                raise NetworkError(f"Failed to create server: {e}", port=self.config.web_port)
    
    def _run_server(self) -> None:
        """Run server in background thread."""
        try:
            if self._server:
                self.logger.info("Web server thread started")
                self._server.serve_forever()
        except Exception as e:
            self.logger.error(f"Web server thread error: {e}")
        finally:
            self.logger.info("Web server thread stopped")
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            if self._is_running:
                # Use synchronous stop for cleanup
                if self._server:
                    self._server.shutdown()
                    self._server.server_close()
        except Exception:
            pass  # Ignore errors during cleanup