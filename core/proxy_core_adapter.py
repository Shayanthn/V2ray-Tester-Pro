"""
Proxy Core Adapter - Base class for proxy core implementations
"""
from abc import ABC, abstractmethod
from typing import Optional
import asyncio
import logging


class ProxyCoreAdapter(ABC):
    """
    Abstract base class for proxy core implementations (Xray, V2Ray, etc.).
    Defines the interface that all proxy core managers must implement.
    """
    
    def __init__(self, core_path: str, logger: logging.Logger):
        """Initialize the proxy core manager."""
        self.core_path = core_path
        self.logger = logger
    
    @abstractmethod
    async def start(self, config_path: str, port: int) -> Optional[asyncio.subprocess.Process]:
        """Start the proxy core process."""
        pass
    
    @abstractmethod
    async def stop(self, process: asyncio.subprocess.Process) -> None:
        """Stop the proxy core process."""
        pass
    
    async def version(self) -> str:
        """Get the proxy core version."""
        pass
