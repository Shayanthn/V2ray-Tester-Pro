import asyncio
import aiohttp
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.enterprise_config import EnterpriseConfig
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.app_state import AppState
import logging

async def test_integration():
    print("--- Starting Integration Test ---")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("TestLogger")
    
    config = EnterpriseConfig()
    
    # Setup AppState
    app_state = AppState(adaptive_batch_min=20, adaptive_sleep_max=1.0)
    
    # Setup NetworkManager
    network_manager = NetworkManager(
        app_state=app_state,
        doh_resolver_url="https://cloudflare-dns.com/dns-query",
        network_retry_count=3,
        app_version="1.0.0",
        logger=logger
    )
    
    # Setup ConfigDiscoverer
    discoverer = ConfigDiscoverer(network_manager, logger)
    
    # Use a known working source from the new list
    test_url = "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub1.txt"
    print(f"Fetching config from: {test_url}")
    
    async with aiohttp.ClientSession() as session:
        configs = await discoverer.fetch_configs_from_source(test_url, session)
        
        print(f"Successfully parsed {len(configs)} configurations.")
        
        if configs:
            print("Sample Config 1:", configs[0])
            print("Integration Test PASSED")
        else:
            print("Integration Test FAILED: No configs parsed")

if __name__ == "__main__":
    asyncio.run(test_integration())

if __name__ == "__main__":
    asyncio.run(test_integration())
