import asyncio
import logging
import random
from datetime import datetime, timezone
from time import perf_counter
from typing import Dict, List, Optional


class ProxyTester:
    def __init__(
        self,
        timeout_seconds: float = 4.0,
        concurrency: int = 80,
        logger: Optional[logging.Logger] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.concurrency = concurrency
        self.logger = logger or logging.getLogger(__name__)

    async def _test_single_proxy(self, proxy: Dict) -> Optional[Dict]:
        server = proxy.get("server")
        port = proxy.get("port")
        if not server or not port:
            return None

        start_time = perf_counter()
        try:
            connect_task = asyncio.open_connection(server, int(port))
            reader, writer = await asyncio.wait_for(connect_task, timeout=self.timeout_seconds)
            latency_ms = (perf_counter() - start_time) * 1000

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            tested = {
                **proxy,
                "latency_ms": round(latency_ms, 2),
                "tested_at": datetime.now(timezone.utc).isoformat(),
                "is_working": True,
            }
            return tested
        except Exception:
            return None

    async def test_proxies(self, proxies: List[Dict], limit: Optional[int] = None) -> List[Dict]:
        if limit is not None and limit > 0 and len(proxies) > limit:
            proxies = random.sample(proxies, limit)

        semaphore = asyncio.Semaphore(self.concurrency)

        async def guarded_test(proxy: Dict) -> Optional[Dict]:
            async with semaphore:
                return await self._test_single_proxy(proxy)

        results = await asyncio.gather(*(guarded_test(proxy) for proxy in proxies), return_exceptions=False)
        working = [result for result in results if result]
        working.sort(key=lambda item: item.get("latency_ms", float("inf")))

        self.logger.info(f"Proxy testing complete: {len(working)}/{len(proxies)} reachable from runner")
        return working
