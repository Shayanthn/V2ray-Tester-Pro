import asyncio
import platform
import logging
import psutil
import subprocess
from typing import Optional
from core.proxy_core_adapter import ProxyCoreAdapter

class XrayManager(ProxyCoreAdapter):
    """
    Manages the Xray Core process lifecycle using asyncio.
    Implements the ProxyCoreAdapter interface.
    
    MULTIPLEXING ARCHITECTURE BLUEPRINT (DESIGN ONLY):
    --------------------------------------------------
    To achieve high-throughput testing without process overhead, we will move to a 
    single-process, multi-inbound architecture.
    
    1. Configuration Structure:
       - Single 'config.json' loaded into one Xray instance.
       - Multiple 'inbounds':
         - tag: "proxy_1", port: 10801
         - tag: "proxy_2", port: 10802
         ...
         - tag: "proxy_N", port: 10800+N
       - Multiple 'outbounds':
         - Each test target (node) is added as a separate outbound with a unique tag.
       - Routing Rules:
         - Rule: "inboundTag": "proxy_k" -> "outboundTag": "node_k"
         
    2. Lifecycle Control:
       - Start ONE Xray process at app launch.
       - Dynamic config reloading via API (if supported) or hot-restart.
       - For simple testing: Generate one giant config with N pairs of in/out.
       
    3. Performance Rationale:
       - Eliminates process creation overhead (approx 50-100ms per test).
       - Reduces memory footprint (shared runtime).
       - Removes OS-level process scheduling contention.
    """
    
    def __init__(self, xray_path: str, logger: logging.Logger):
        self.xray_path = xray_path
        self.logger = logger

    async def start(self, config_path: str, port: int) -> Optional[asyncio.subprocess.Process]:
        """
        Starts the Xray process asynchronously.
        """
        cmd = [self.xray_path, "run", "-c", config_path]
        startup_info = None
        
        if platform.system() == 'Windows':
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE

        try:
            # Use asyncio.create_subprocess_exec instead of subprocess.Popen
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startup_info
            )
            
            # Wait briefly to ensure it didn't crash immediately
            try:
                await asyncio.wait_for(process.wait(), timeout=0.1)
                # If we get here, the process exited immediately (likely error)
                stderr_data = await process.stderr.read()
                error_msg = stderr_data.decode('utf-8', errors='ignore')
                self.logger.error(f"Xray process exited immediately for port {port}: {error_msg}")
                return None
            except asyncio.TimeoutError:
                # Process is still running, which is good
                return process
                
        except Exception as e:
            self.logger.error(f"Failed to start Xray process: {e}")
            return None

    async def stop(self, process: asyncio.subprocess.Process) -> None:
        """
        Stops the Xray process and its children asynchronously and safely.
        """
        if not process:
            return

        try:
            if process.returncode is not None:
                return # Already exited

            process.terminate()
            
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.logger.warning(f"Process {process.pid} did not terminate gracefully, killing...")
                process.kill()
                await process.wait()
                
        except Exception as e:
            self.logger.warning(f"Error stopping Xray process: {e}")

    async def version(self) -> str:
        """Returns Xray version."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.xray_path, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().split('\n')[0]
        except Exception:
            return "Unknown"

