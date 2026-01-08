from abc import ABC, abstractmethod
from typing import Optional
import asyncio

class ProxyCoreAdapter(ABC):
    """
    Abstract interface for proxy core backends (Xray, Sing-box, etc.).
    Ensures interchangeability and standardized lifecycle management.
    """

    @abstractmethod
    async def start(self, config_path: str, port: int) -> Optional[asyncio.subprocess.Process]:
        """
        Starts the proxy core process asynchronously.
        
        Args:
            config_path: Path to the configuration file.
            port: The listening port for the proxy.
            
        Returns:
            The asyncio subprocess object if successful, None otherwise.
        """
        pass

    @abstractmethod
    async def stop(self, process: asyncio.subprocess.Process) -> None:
        """
        Stops the proxy core process gracefully.
        
        Args:
            process: The asyncio subprocess object to stop.
        """
        pass

    @abstractmethod
    async def version(self) -> str:
        """
        Returns the version string of the proxy core.
        """
        pass
