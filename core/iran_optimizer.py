# -----------------------------------------------------------------------------
# Iran Network Optimizer - Advanced features for Iranian network conditions
# V2Ray Tester Pro v5.3.0
# -----------------------------------------------------------------------------
import asyncio
import aiohttp
import logging
import random
import ipaddress
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CleanIP:
    """Represents a tested clean IP with its metrics."""
    ip: str
    latency_ms: int
    provider: str  # cloudflare, gcore, fastly, etc.
    tested_at: float


class IranOptimizer:
    """
    Advanced network optimization for Iranian internet conditions.
    
    Features:
    - Clean IP Discovery for Cloudflare and other CDNs
    - Domestic vs International connectivity detection
    - SNI randomization for bypass
    - Protocol prioritization (Reality > XTLS > TLS)
    """
    
    # Cloudflare IP ranges (subset for testing)
    CLOUDFLARE_RANGES = [
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "162.158.0.0/15",
        "198.41.128.0/17",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "173.245.48.0/20",
        "131.0.72.0/22",
    ]
    
    # Known working SNIs for bypass
    BYPASS_SNIS = [
        "www.speedtest.net",
        "www.zula.ir",
        "www.digikala.com",
        "update.microsoft.com",
        "www.google.com",
        "dl.google.com",
        "www.apple.com",
        "cdn.discordapp.com",
        "gateway.discord.gg",
        "www.cloudflare.com",
    ]
    
    # Domestic test targets
    DOMESTIC_TARGETS = [
        "https://www.aparat.com",
        "https://www.digikala.com",
        "https://www.shaparak.ir",
    ]
    
    # International test targets
    INTERNATIONAL_TARGETS = [
        "https://1.1.1.1",
        "https://www.google.com/generate_204",
        "https://cp.cloudflare.com",
    ]
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.clean_ips: List[CleanIP] = []
        self.network_status = {
            "domestic_ok": None,
            "international_ok": None,
            "filtering_detected": None,
            "last_check": None
        }
    
    # =========================================================================
    # Feature 1: Clean IP Discovery
    # =========================================================================
    
    async def discover_clean_ips(self, 
                                  session: aiohttp.ClientSession,
                                  count: int = 10,
                                  timeout: int = 3) -> List[CleanIP]:
        """
        Discovers clean Cloudflare IPs by testing random IPs from CF ranges.
        
        Args:
            session: aiohttp session
            count: Number of clean IPs to find
            timeout: Timeout per IP test in seconds
            
        Returns:
            List of CleanIP objects sorted by latency
        """
        self.logger.info(f"Starting Clean IP discovery (target: {count} IPs)...")
        
        # Generate candidate IPs
        candidates = self._generate_candidate_ips(count * 10)  # Test 10x to find good ones
        
        # Test IPs concurrently
        tasks = [
            self._test_ip(session, ip, timeout)
            for ip in candidates
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        clean_ips = []
        for result in results:
            if isinstance(result, CleanIP):
                clean_ips.append(result)
                if len(clean_ips) >= count:
                    break
        
        # Sort by latency
        clean_ips.sort(key=lambda x: x.latency_ms)
        self.clean_ips = clean_ips[:count]
        
        self.logger.info(f"Found {len(self.clean_ips)} clean IPs. "
                        f"Best: {self.clean_ips[0].ip if self.clean_ips else 'None'} "
                        f"({self.clean_ips[0].latency_ms}ms)" if self.clean_ips else "")
        
        return self.clean_ips
    
    def _generate_candidate_ips(self, count: int) -> List[str]:
        """Generates random IPs from Cloudflare ranges."""
        candidates = []
        
        for _ in range(count):
            # Pick a random range
            cidr = random.choice(self.CLOUDFLARE_RANGES)
            network = ipaddress.ip_network(cidr)
            
            # Generate random IP from range
            random_ip = ipaddress.IPv4Address(
                random.randint(
                    int(network.network_address) + 1,
                    int(network.broadcast_address) - 1
                )
            )
            candidates.append(str(random_ip))
        
        return candidates
    
    async def _test_ip(self, 
                       session: aiohttp.ClientSession, 
                       ip: str, 
                       timeout: int) -> Optional[CleanIP]:
        """Tests a single IP for connectivity."""
        import time
        
        try:
            start = time.monotonic()
            
            # Use Cloudflare's trace endpoint
            url = f"https://{ip}/cdn-cgi/trace"
            headers = {"Host": "www.cloudflare.com"}
            
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as temp_session:
                async with temp_session.get(
                    url, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False
                ) as response:
                    if response.status == 200:
                        latency = int((time.monotonic() - start) * 1000)
                        return CleanIP(
                            ip=ip,
                            latency_ms=latency,
                            provider="cloudflare",
                            tested_at=time.time()
                        )
        except Exception:
            pass
        
        return None
    
    async def fetch_clean_ips_from_sources(self, session: aiohttp.ClientSession) -> List[str]:
        """Fetches pre-tested clean IPs from community sources."""
        sources = [
            "https://raw.githubusercontent.com/MortezaBashworker/CFScanner/main/cf_result.txt",
            "https://raw.githubusercontent.com/vfarid/cf-clean-ips/main/list.txt",
        ]
        
        clean_ips = []
        
        for source in sources:
            try:
                async with session.get(source, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Parse IPs (one per line)
                        for line in text.strip().split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Some files have IP:port format
                                ip = line.split(':')[0].split(',')[0].strip()
                                if self._is_valid_ip(ip):
                                    clean_ips.append(ip)
                        self.logger.info(f"Fetched {len(clean_ips)} IPs from {source}")
            except Exception as e:
                self.logger.debug(f"Failed to fetch from {source}: {e}")
        
        return list(set(clean_ips))[:50]  # Dedupe and limit
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validates IP address format."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    # =========================================================================
    # Feature 2: Domestic vs International Detection
    # =========================================================================
    
    async def check_network_status(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """
        Checks if we have domestic internet only or full international access.
        
        Returns:
            Dict with keys: domestic_ok, international_ok, filtering_detected
        """
        import time
        
        self.logger.info("Checking network status (domestic vs international)...")
        
        # Test domestic
        domestic_ok = False
        for url in self.DOMESTIC_TARGETS:
            try:
                async with session.get(url, timeout=5) as response:
                    if response.status < 400:
                        domestic_ok = True
                        break
            except Exception:
                continue
        
        # Test international
        international_ok = False
        for url in self.INTERNATIONAL_TARGETS:
            try:
                async with session.get(url, timeout=5) as response:
                    if response.status < 400:
                        international_ok = True
                        break
            except Exception:
                continue
        
        # Determine filtering status
        if domestic_ok and not international_ok:
            filtering_detected = True
            self.logger.warning("⚠️ National Internet detected! International access blocked.")
        elif not domestic_ok and not international_ok:
            filtering_detected = None  # Complete outage
            self.logger.error("❌ Complete internet outage detected!")
        else:
            filtering_detected = False
            self.logger.info("✅ Full internet access available.")
        
        self.network_status = {
            "domestic_ok": domestic_ok,
            "international_ok": international_ok,
            "filtering_detected": filtering_detected,
            "last_check": time.time()
        }
        
        return self.network_status
    
    # =========================================================================
    # Feature 3: SNI Randomization
    # =========================================================================
    
    def get_random_sni(self) -> str:
        """Returns a random SNI for bypass attempts."""
        return random.choice(self.BYPASS_SNIS)
    
    def inject_sni(self, config: Dict[str, Any], sni: str) -> Dict[str, Any]:
        """Injects a custom SNI into the config."""
        import copy
        new_config = copy.deepcopy(config)
        
        for outbound in new_config.get('outbounds', []):
            stream = outbound.get('streamSettings', {})
            
            # Update TLS settings
            if 'tlsSettings' in stream:
                stream['tlsSettings']['serverName'] = sni
            if 'realitySettings' in stream:
                stream['realitySettings']['serverName'] = sni
            if 'xtlsSettings' in stream:
                stream['xtlsSettings']['serverName'] = sni
        
        return new_config
    
    # =========================================================================
    # Feature 4: Protocol Priority
    # =========================================================================
    
    @staticmethod
    def get_protocol_priority(uri: str) -> int:
        """
        Returns priority score for a URI based on protocol.
        Higher = better for Iranian conditions.
        
        Priority order:
        1. Reality (100) - Best for Iran
        2. XTLS (90)
        3. VLESS+TLS (70)
        4. VMess+TLS (60)
        5. Trojan (50)
        6. Others (10)
        """
        uri_lower = uri.lower()
        
        if 'reality' in uri_lower or 'pbk=' in uri_lower:
            return 100
        elif 'flow=xtls' in uri_lower:
            return 90
        elif 'vless://' in uri_lower and ('tls' in uri_lower or 'security=tls' in uri_lower):
            return 70
        elif 'vmess://' in uri_lower:
            return 60
        elif 'trojan://' in uri_lower:
            return 50
        else:
            return 10
    
    @staticmethod
    def sort_by_priority(uris: List[str]) -> List[str]:
        """Sorts URIs by protocol priority for Iranian conditions."""
        return sorted(uris, key=IranOptimizer.get_protocol_priority, reverse=True)
    
    # =========================================================================
    # Feature 5: Fragment Auto-Injection Check
    # =========================================================================
    
    @staticmethod
    def should_auto_fragment(uri: str) -> bool:
        """
        Determines if Fragment should be applied proactively.
        
        Returns True for:
        - VLESS with TLS (not Reality, not XTLS)
        - VMess with TLS
        - Trojan
        """
        uri_lower = uri.lower()
        
        # Don't fragment Reality/XTLS - they have their own bypass
        if 'reality' in uri_lower or 'pbk=' in uri_lower:
            return False
        if 'flow=xtls' in uri_lower:
            return False
        
        # Fragment TLS-based protocols
        if 'vless://' in uri_lower and 'security=tls' in uri_lower:
            return True
        if 'vmess://' in uri_lower:
            return True
        if 'trojan://' in uri_lower:
            return True
        
        return False


# Utility function for quick access
def create_iran_optimizer(logger: logging.Logger) -> IranOptimizer:
    """Factory function to create an IranOptimizer instance."""
    return IranOptimizer(logger)
