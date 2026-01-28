import os
import json
import time
import statistics
import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional
from core.xray_manager import XrayManager
from core.config_processor import ConfigProcessor
from utils.security_validator import SecurityValidator

class TestRunner:
    """Manages the execution of advanced tests against configurations."""
    
    def __init__(self, 
                 xray_manager: XrayManager, 
                 config_processor: ConfigProcessor,
                 security_validator: SecurityValidator,
                 test_url_ping: str,
                 test_url_download: str,
                 test_url_upload: str,
                 censorship_check_url: str,
                 test_timeout: int,
                 logger: logging.Logger,
                 test_url_telegram: str = "https://api.telegram.org",
                 test_url_instagram: str = "https://www.instagram.com",
                 test_url_youtube: str = "https://www.youtube.com",
                 test_url_ping_fallback: str = "https://1.1.1.1",
                 domestic_check_url: str = "https://www.aparat.com"):
        self.xray_manager = xray_manager
        self.config_processor = config_processor
        self.security_validator = security_validator
        self.test_url_ping = test_url_ping
        self.test_url_download = test_url_download
        self.test_url_upload = test_url_upload
        self.censorship_check_url = censorship_check_url
        self.test_timeout = test_timeout
        self.logger = logger
        self.test_url_telegram = test_url_telegram
        self.test_url_instagram = test_url_instagram
        self.test_url_youtube = test_url_youtube
        self.test_url_ping_fallback = test_url_ping_fallback
        self.domestic_check_url = domestic_check_url

    async def run_full_test(self, config_json: Dict[str, Any], port: int, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """
        Executes a comprehensive test suite on a given Xray configuration.
        Returns None if the test fails or the config is invalid.
        """
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        config_path = os.path.join(os.path.dirname(self.xray_manager.xray_path), f"temp_config_{port}_{unique_id}.json")
        process = None
        
        try:
            # Write config to temp file
            # Note: File I/O is blocking, but for small config files it's negligible. 
            # For strict async, we could use aiofiles, but standard open is acceptable here for now.
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump(config_json, f)

            # Start Xray process
            process = await self.xray_manager.start(config_path, port)
            if not process:
                return None
                
            # Use HTTP proxy for aiohttp (ConfigProcessor must be updated to use HTTP inbound)
            proxy_url = f"http://127.0.0.1:{port}"
            
            # 1. Latency and Jitter Test (Robust / Cloudflare Radar Compatible)
            latencies = []
            # We try the primary (e.g. Google) and if fails, the fallback (e.g. 1.1.1.1 or Cloudflare Trace)
            test_targets = [self.test_url_ping]
            if hasattr(self, 'test_url_ping_fallback'):
                test_targets.append(self.test_url_ping_fallback)
            
            check_passed = False
            for target in test_targets:
                target_latencies = []
                # Try 2 requests per target. Reduced from 3 to 2 for speed, relying on fallback if needed.
                for _ in range(2):
                    try:
                        start_time = time.monotonic()
                        # Increased timeout tolerance for "National Internet" conditions
                        async with session.get(
                            target, proxy=proxy_url, timeout=self.test_timeout + 2
                        ) as response:
                            if response.status in (200, 204):
                                latency = (time.monotonic() - start_time) * 1000
                                if latency < 10000:  # Allow up to 10s latency for extreme conditions
                                    target_latencies.append(latency)
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        continue
                
                if target_latencies:
                    latencies = target_latencies
                    check_passed = True
                    break # If one target works, we assume connectivity is established.

            if not check_passed or not latencies:
                # Optional: Domestic Check for Logging/Diagnostics (doesn't change result)
                if hasattr(self, 'domestic_check_url'):
                    try:
                        async with session.get(self.domestic_check_url, proxy=proxy_url, timeout=5) as resp:
                             pass # Domestic works
                    except:
                        pass
                return None  # Failed basic connectivity

            avg_ping = int(statistics.mean(latencies))
            jitter = int(statistics.stdev(latencies) if len(latencies) > 1 else 0)

            # 2. Speed Test
            dl_speed = await self._download_speed_test(session, proxy_url)
            ul_speed = await self._upload_speed_test(session, proxy_url)

            # 3. Real-World Connectivity Test
            connectivity = await self._check_connectivity(session, proxy_url)

            # 4. Bypass Test
            is_bypassing = await self._check_bypass(session, proxy_url)

            # 5. Get Server Info
            outbound = config_json['outbounds'][0]
            # This is complex due to TUIC/Hysteria wrappers. We need to find the real server.
            address, protocol = "N/A", "N/A"
            if 'streamSettings' in outbound and 'network' in outbound['streamSettings']:
                net = outbound['streamSettings']['network']
                if net == 'tuic':
                    protocol = 'tuic'
                    address = outbound['streamSettings']['tuicSettings']['server'].split(':')[0]
                elif net == 'hysteria2':
                    protocol = 'hysteria2'
                    address = outbound['streamSettings']['hysteriaSettings']['server'].split(':')[0]

            if protocol == "N/A": # Not a wrapped protocol
                protocol = outbound['protocol']
                if protocol in ["vmess", "vless"]:
                    server_info = outbound['settings'].get('vnext', [{}])[0]
                    address = server_info.get('address', 'N/A')
                elif protocol in ["trojan", "shadowsocks"]:
                    server_info = outbound['settings'].get('servers', [{}])[0]
                    address = server_info.get('address', 'N/A')

            # 5. Check blacklist again on final address
            if self.security_validator.is_blacklisted(address):
                self.logger.warning(f"Blacklisted server detected: {address}")
                return None

            return {
                'protocol': protocol,
                'address': address,
                'ping': avg_ping,
                'jitter': jitter,
                'download_speed': dl_speed,
                'upload_speed': ul_speed,
                'is_bypassing': is_bypassing,
                'connectivity': connectivity,
                'ip': address, # 'ip' field should be consistent
                'config_json': config_json,
                'uri': None  # Will be set by the orchestrator
            }

        except Exception as e:
            self.logger.error(f"Error in full test for port {port}: {e}", exc_info=True)
            return None
        finally:
            if process:
                await self.xray_manager.stop(process)
            
            # Clean up temp config file with retry logic
            for attempt in range(5):
                try:
                    if os.path.exists(config_path):
                        os.remove(config_path)
                    break  # Success or file doesn't exist
                except PermissionError:
                    # File may be locked by Xray process, wait and retry
                    await asyncio.sleep(0.3 * (attempt + 1))
                except Exception as e:
                    if attempt == 4:  # Last attempt
                        self.logger.warning(f"Failed to remove temp config '{config_path}': {e}")
                    break

    async def _check_connectivity(self, session: aiohttp.ClientSession, proxy_url: str) -> Dict[str, bool]:
        """Checks connectivity to specific services (Telegram, Instagram, YouTube)."""
        results = {
            'telegram': False,
            'instagram': False,
            'youtube': False
        }
        
        targets = [
            ('telegram', self.test_url_telegram),
            ('instagram', self.test_url_instagram),
            ('youtube', self.test_url_youtube)
        ]
        
        # Run checks concurrently for better performance
        async def check_target(name, url):
            try:
                async with session.get(url, proxy=proxy_url, timeout=5) as response:
                    # Accept 200-399 as success. Some sites might redirect.
                    if response.status < 400:
                        return name, True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            return name, False

        tasks = [check_target(name, url) for name, url in targets]
        check_results = await asyncio.gather(*tasks)
        
        for name, success in check_results:
            results[name] = success
            
        return results

    async def _download_speed_test(self, session: aiohttp.ClientSession, proxy_url: str) -> float:
        """Measures download speed in Mbps."""
        try:
            start_time = time.monotonic()
            async with session.get(
                self.test_url_download, proxy=proxy_url, timeout=self.test_timeout
            ) as response:
                total_downloaded = 0
                
                # Read in chunks
                async for chunk in response.content.iter_chunked(65536):
                    if time.monotonic() - start_time > self.test_timeout:
                        break
                    total_downloaded += len(chunk)
                    if total_downloaded >= 3_000_000:  # 3MB is enough for a good estimate
                        break
            
            duration = time.monotonic() - start_time
            if duration > 0:
                # Mbps = (Bytes * 8) / duration / 1,000,000
                return round((total_downloaded * 8) / duration / 1_000_000, 2)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return 0.0
        return 0.0

    async def _upload_speed_test(self, session: aiohttp.ClientSession, proxy_url: str) -> float:
        """Measures upload speed in Mbps."""
        try:
            test_data = os.urandom(2_000_000) # 2MB of random data
            
            start_time = time.monotonic()
            async with session.post(
                self.test_url_upload, data=test_data, proxy=proxy_url, timeout=self.test_timeout
            ) as response:
                duration = time.monotonic() - start_time
                if duration > 0 and response.status == 200:
                    return round((len(test_data) * 8) / duration / 1_000_000, 2)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return 0.0
        return 0.0

    async def _check_bypass(self, session: aiohttp.ClientSession, proxy_url: str) -> bool:
        """Checks if a known blocked site is accessible."""
        try:
            async with session.head(
                self.censorship_check_url, proxy=proxy_url, timeout=5, allow_redirects=True
            ) as response:
                return response.status < 400  # Success is any 2xx or 3xx
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False
