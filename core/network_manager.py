import asyncio
import aiohttp
import logging
import os
import json
import re
import base64
from typing import Optional, Set, List, Dict, Any
from core.app_state import AppState
from utils.errors import NetworkError, log_error, ErrorCategory

# Try importing geoip2
try:
    import geoip2.database
    HAS_GEOIP = True
except ImportError:
    HAS_GEOIP = False

class NetworkManager:
    """Handles all network operations with retry logic and DoH support."""
    
    def __init__(self, 
                 app_state: AppState, 
                 doh_resolver_url: str, 
                 network_retry_count: int, 
                 app_version: str,
                 logger: logging.Logger,
                 geoip_db_path: str = None):
        self.app_state = app_state
        self.doh_resolver_url = doh_resolver_url
        self.network_retry_count = network_retry_count
        self.app_version = app_version
        self.logger = logger
        self.geoip_reader = None
        
        if HAS_GEOIP and geoip_db_path and os.path.exists(geoip_db_path):
            try:
                self.geoip_reader = geoip2.database.Reader(geoip_db_path)
                self.logger.info(f"Loaded GeoIP database from {geoip_db_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load GeoIP database: {e}")

    async def get_geoip_info(self, ip: str, session: aiohttp.ClientSession = None) -> Dict[str, str]:
        """Resolves IP to location using local DB with online fallback."""
        if not ip:
            return {}
            
        # Try local DB first
        if self.geoip_reader:
            try:
                # Run blocking GeoIP lookup in executor to avoid blocking event loop
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, self.geoip_reader.city, ip)
                
                return {
                    'country': response.country.name or 'Unknown',
                    'country_code': response.country.iso_code or 'XX',
                    'city': response.city.name or 'Unknown',
                    'isp': 'Unknown' # GeoLite2 City doesn't have ISP
                }
            except Exception:
                pass # Fallback to online
        
        # Fallback to online API
        return await self.fetch_geoip_online(ip, session)

    async def fetch_geoip_online(self, ip: str, session: aiohttp.ClientSession = None) -> Dict[str, str]:
        """Fallback to online GeoIP API with secure HTTPS endpoints."""
        # Use multiple HTTPS providers for reliability and security
        # ipwho.is has better rate limits than ipapi.co
        geoip_providers = [
            f"https://ipwho.is/{ip}",  # Primary: HTTPS, free, better rate limits
            f"http://ip-api.com/json/{ip}",  # Secondary: free, 45 requests/min
        ]
        
        for url in geoip_providers:
            try:
                response_text = await self.safe_get(url, session=session, retry_count=1)
                if response_text:
                    data = json.loads(response_text)
                    # Handle different API response formats
                    if 'error' not in data and data.get('success', True) != False:
                        return {
                            'country': data.get('country_name') or data.get('country') or 'Unknown',
                            'country_code': data.get('country_code') or data.get('country') or 'XX',
                            'city': data.get('city') or 'Unknown',
                            'isp': data.get('org') or data.get('isp') or data.get('connection', {}).get('isp') or 'Unknown'
                        }
            except Exception as e:
                self.logger.debug(f"GeoIP lookup failed for {ip} with {url}: {e}")
                continue
        return {}

    async def resolve_doh(self, hostname: str, session: aiohttp.ClientSession = None) -> Optional[str]:
        """Resolves a hostname using DNS-over-HTTPS."""
        if not hostname or hostname in self.app_state.ip_cache:
            return self.app_state.ip_cache.get(hostname)
            
        try:
            params = {'name': hostname, 'type': 'A'}
            headers = {'accept': 'application/dns-json'}
            
            # Use provided session or create a temporary one (fallback)
            if session:
                async with session.get(
                    self.doh_resolver_url, params=params, headers=headers, timeout=3
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'Answer' in data and data['Answer']:
                            ip = data['Answer'][0]['data']
                            self.app_state.ip_cache[hostname] = ip
                            return ip
            else:
                async with aiohttp.ClientSession() as temp_session:
                    async with temp_session.get(
                        self.doh_resolver_url, params=params, headers=headers, timeout=3
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'Answer' in data and data['Answer']:
                                ip = data['Answer'][0]['data']
                                self.app_state.ip_cache[hostname] = ip
                                return ip
        except Exception as e:
            log_error(self.logger, NetworkError(f"Failed to resolve {hostname} via DoH: {e}", original_exception=e), "DoH Resolution Failed")
        return None
    
    async def safe_get(self, url: str, session: aiohttp.ClientSession = None, retry_count: int = None, headers: dict = None, binary: bool = False) -> Optional[Any]:
        """Performs a GET request with retry logic and exponential backoff."""
        retry_count = retry_count or self.network_retry_count
        headers = headers or {
            'User-Agent': f'V2RayTester/{self.app_version}',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        for attempt in range(retry_count):
            try:
                if session:
                    async with session.get(url, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            return await response.read() if binary else await response.text()
                        elif response.status == 403 and 'github.com' in url:
                            self.app_state.api_rate_limited = True
                            self.logger.warning(f"GitHub API rate limit reached for {url}")
                            return None
                        elif response.status == 429:
                            self.logger.warning(f"Rate limited for {url}, retrying...")
                            await asyncio.sleep(2 ** attempt)
                else:
                    async with aiohttp.ClientSession() as temp_session:
                        async with temp_session.get(url, headers=headers, timeout=15) as response:
                            if response.status == 200:
                                return await response.read() if binary else await response.text()
                            elif response.status == 403 and 'github.com' in url:
                                self.app_state.api_rate_limited = True
                                self.logger.warning(f"GitHub API rate limit reached for {url}")
                                return None
                            elif response.status == 429:
                                self.logger.warning(f"Rate limited for {url}, retrying...")
                                await asyncio.sleep(2 ** attempt)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5 + attempt * 1.5)  # Exponential backoff
                else:
                    log_error(self.logger, NetworkError(f"All {retry_count} attempts failed for {url}: {e}", original_exception=e), "Network Request Failed")
        return None

class ConfigDiscoverer:
    """Discovers and manages configuration sources."""
    
    def __init__(self, network_manager: NetworkManager, logger: logging.Logger):
        self.network_manager = network_manager
        self.logger = logger

    async def fetch_configs_from_source(self, url: str, session: aiohttp.ClientSession = None) -> List[str]:
        """Fetches and extracts configs from a given URL, supporting ZIP archives."""
        import zipfile
        import io
        
        is_zip = url.lower().endswith('.zip')
        content = await self.network_manager.safe_get(url, session=session, binary=is_zip)
        
        if not content:
            return []
            
        configs = []
        contents_to_process = []

        try:
            if is_zip and isinstance(content, bytes):
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        for filename in z.namelist():
                            if not filename.endswith('/') and not filename.startswith('__'):
                                with z.open(filename) as f:
                                    try:
                                        file_content = f.read().decode('utf-8', errors='ignore')
                                        contents_to_process.append(file_content)
                                    except Exception:
                                        pass
                    self.logger.info(f"Extracted {len(contents_to_process)} files from ZIP: {url}")
                except zipfile.BadZipFile:
                    self.logger.warning(f"Invalid ZIP file: {url}")
            else:
                # Treat as single text file
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                contents_to_process.append(content)

            for text_content in contents_to_process:
                # Try decoding base64 first (common for subscriptions)
                try:
                    # Check if it looks like base64 (no spaces, length multiple of 4 usually, but loose check)
                    if ' ' not in text_content[:100] and len(text_content) > 10:
                        decoded = base64.b64decode(text_content).decode('utf-8')
                        text_content = decoded
                except Exception:
                    pass # Not base64 or mixed content
                    
                # Extract URIs using regex
                # Supported protocols: vmess, vless, trojan, ss, ssr, tuic, hysteria2
                regex_full = r"(?:vmess|vless|trojan|ss|ssr|tuic|hysteria2)://[^\s<>\"']+"
                matches = re.findall(regex_full, text_content)
                configs.extend(matches)
            
            if configs:
                self.logger.info(f"Found {len(configs)} configs from {url}")
            
        except Exception as e:
            self.logger.warning(f"Error parsing content from {url}: {e}")
            
        return configs
