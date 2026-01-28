"""
Rate Limiter Module - v5.4.0
Prevents IP blocking by controlling request rates with adaptive algorithms.
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import deque
import logging


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting with sliding window."""
    max_tokens: int
    refill_rate: float  # tokens per second
    tokens: float = field(default=0)
    last_update: float = field(default_factory=time.time)
    window_requests: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def __post_init__(self):
        self.tokens = self.max_tokens


class RateLimiter:
    """
    Adaptive Rate Limiter with multiple strategies:
    1. Token Bucket - Smooth rate limiting with burst support
    2. Sliding Window - Tracks requests over time windows
    3. Adaptive Backoff - Adjusts rates based on failure patterns
    4. Domain-specific limits - Different rates for different targets
    """
    
    # Default limits for different operation types
    DEFAULT_LIMITS = {
        'test': {'tokens': 50, 'rate': 10.0},      # 10 tests/second max
        'fetch': {'tokens': 20, 'rate': 5.0},       # 5 fetches/second
        'geoip': {'tokens': 10, 'rate': 2.0},       # 2 geoip lookups/second
        'telegram': {'tokens': 30, 'rate': 1.0},    # 1 message/second (Telegram limit)
        'default': {'tokens': 100, 'rate': 20.0}
    }
    
    # Known domains with strict rate limits
    STRICT_DOMAINS = {
        'api.telegram.org': {'tokens': 30, 'rate': 0.5},
        'ipapi.co': {'tokens': 10, 'rate': 0.5},
        'ipwho.is': {'tokens': 10, 'rate': 0.5},
        'ip-api.com': {'tokens': 5, 'rate': 0.2},
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.buckets: Dict[str, RateLimitBucket] = {}
        self.failure_counts: Dict[str, int] = {}
        self.backoff_until: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        # Global rate limiting
        self.global_bucket = RateLimitBucket(
            max_tokens=200,
            refill_rate=50.0  # 50 requests/second globally
        )
        
        # Metrics
        self.total_requests = 0
        self.total_delayed = 0
        self.total_rejected = 0
        
    def _get_bucket(self, key: str, op_type: str = 'default') -> RateLimitBucket:
        """Get or create a rate limit bucket for a key."""
        if key not in self.buckets:
            # Check if it's a known strict domain
            if key in self.STRICT_DOMAINS:
                config = self.STRICT_DOMAINS[key]
            elif op_type in self.DEFAULT_LIMITS:
                config = self.DEFAULT_LIMITS[op_type]
            else:
                config = self.DEFAULT_LIMITS['default']
            
            self.buckets[key] = RateLimitBucket(
                max_tokens=config['tokens'],
                refill_rate=config['rate']
            )
        return self.buckets[key]
    
    def _refill_bucket(self, bucket: RateLimitBucket) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_update
        bucket.tokens = min(
            bucket.max_tokens,
            bucket.tokens + elapsed * bucket.refill_rate
        )
        bucket.last_update = now
    
    async def acquire(self, key: str, op_type: str = 'default', 
                      cost: float = 1.0, timeout: float = 30.0) -> bool:
        """
        Acquire permission to make a request.
        
        Args:
            key: Identifier for the rate limit bucket (e.g., domain, operation)
            op_type: Type of operation ('test', 'fetch', 'geoip', 'telegram')
            cost: How many tokens this request costs
            timeout: Maximum time to wait for tokens
            
        Returns:
            True if request is allowed, False if rejected
        """
        async with self._lock:
            self.total_requests += 1
            
            # Check if in backoff period
            if key in self.backoff_until:
                if time.time() < self.backoff_until[key]:
                    wait_time = self.backoff_until[key] - time.time()
                    self.logger.debug(f"Rate limiter backoff for {key}: {wait_time:.1f}s remaining")
                    self.total_rejected += 1
                    return False
                else:
                    del self.backoff_until[key]
            
            bucket = self._get_bucket(key, op_type)
            self._refill_bucket(bucket)
            self._refill_bucket(self.global_bucket)
            
            # Check both specific and global buckets
            if bucket.tokens >= cost and self.global_bucket.tokens >= cost:
                bucket.tokens -= cost
                self.global_bucket.tokens -= cost
                bucket.window_requests.append(time.time())
                return True
            
            # Need to wait for tokens
            wait_time = max(
                (cost - bucket.tokens) / bucket.refill_rate,
                (cost - self.global_bucket.tokens) / self.global_bucket.refill_rate
            )
            
            if wait_time > timeout:
                self.logger.warning(f"Rate limit exceeded for {key}, would need {wait_time:.1f}s wait")
                self.total_rejected += 1
                return False
        
        # Wait outside the lock
        if wait_time > 0:
            self.total_delayed += 1
            self.logger.debug(f"Rate limiter waiting {wait_time:.2f}s for {key}")
            await asyncio.sleep(wait_time)
            
            # Re-acquire after wait
            return await self.acquire(key, op_type, cost, timeout - wait_time)
        
        return True
    
    async def acquire_or_wait(self, key: str, op_type: str = 'default', 
                               cost: float = 1.0) -> None:
        """Acquire permission, waiting indefinitely if needed."""
        while not await self.acquire(key, op_type, cost, timeout=60.0):
            await asyncio.sleep(1.0)
    
    def record_failure(self, key: str) -> None:
        """Record a failure for adaptive backoff."""
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
        failures = self.failure_counts[key]
        
        # Exponential backoff: 2^failures seconds, max 5 minutes
        if failures >= 3:
            backoff_time = min(2 ** failures, 300)
            self.backoff_until[key] = time.time() + backoff_time
            self.logger.warning(f"Rate limiter backoff for {key}: {backoff_time}s after {failures} failures")
    
    def record_success(self, key: str) -> None:
        """Record a success to reduce failure count."""
        if key in self.failure_counts:
            self.failure_counts[key] = max(0, self.failure_counts[key] - 1)
            if self.failure_counts[key] == 0:
                del self.failure_counts[key]
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            'total_requests': self.total_requests,
            'total_delayed': self.total_delayed,
            'total_rejected': self.total_rejected,
            'delay_rate': self.total_delayed / max(1, self.total_requests),
            'reject_rate': self.total_rejected / max(1, self.total_requests),
            'active_buckets': len(self.buckets),
            'active_backoffs': len(self.backoff_until),
            'global_tokens': self.global_bucket.tokens
        }
    
    def reset(self) -> None:
        """Reset all rate limiting state."""
        self.buckets.clear()
        self.failure_counts.clear()
        self.backoff_until.clear()
        self.global_bucket = RateLimitBucket(
            max_tokens=200,
            refill_rate=50.0
        )
        self.total_requests = 0
        self.total_delayed = 0
        self.total_rejected = 0


class DomainRateLimiter(RateLimiter):
    """
    Specialized rate limiter for domain-based limiting.
    Automatically extracts domain from URLs.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        
    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:
            return url
    
    async def acquire_for_url(self, url: str, op_type: str = 'fetch', 
                               cost: float = 1.0) -> bool:
        """Acquire rate limit permission for a URL."""
        domain = self.extract_domain(url)
        return await self.acquire(domain, op_type, cost)
    
    async def acquire_for_ip(self, ip: str, op_type: str = 'test',
                              cost: float = 1.0) -> bool:
        """Acquire rate limit permission for an IP address."""
        # Group IPs by /24 subnet to prevent hammering same servers
        parts = ip.split('.')
        if len(parts) == 4:
            subnet = '.'.join(parts[:3]) + '.0/24'
            return await self.acquire(subnet, op_type, cost)
        return await self.acquire(ip, op_type, cost)


# Singleton instance for global rate limiting
_global_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter
