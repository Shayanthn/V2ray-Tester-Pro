import asyncio
import platform
import logging
import psutil
import subprocess
from typing import Optional

class XrayManager:
    """
    Manages the Xray Core process lifecycle using asyncio.
    Updated for v5.1.2 Revert verification.
    
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
            # Capture both stdout and stderr for better debugging
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startup_info
            )
            
            # Wait briefly to ensure it didn't crash immediately
            try:
                await asyncio.wait_for(process.wait(), timeout=0.2)
                # If we get here, the process exited immediately (likely error)
                stderr_data = await process.stderr.read()
                stdout_data = await process.stdout.read()
                error_msg = stderr_data.decode('utf-8', errors='ignore').strip()
                stdout_msg = stdout_data.decode('utf-8', errors='ignore').strip()
                
                # Log detailed error information
                self.logger.error(
                    f"Xray process exited immediately for port {port}:\n"
                    f"  Config: {config_path}\n"
                    f"  Return code: {process.returncode}\n"
                    f"  STDERR: {error_msg[:500]}\n"
                    f"  STDOUT: {stdout_msg[:500]}"
                )
                return None
            except asyncio.TimeoutError:
                # Process is still running, which is good
                return process
                
        except FileNotFoundError:
            self.logger.error(f"Xray executable not found at: {self.xray_path}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to start Xray process for port {port}: {e}", exc_info=True)
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

