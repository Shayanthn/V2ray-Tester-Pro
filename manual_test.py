import asyncio
import aiohttp
import logging
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from config.enterprise_config import EnterpriseConfig
from utils.logger import setup_logger
from core.network_manager import NetworkManager
from core.test_runner import TestRunner
from core.app_state import AppState
from core.xray_manager import XrayManager
from core.config_processor import ConfigProcessor
from utils.security_validator import SecurityValidator

async def test_geoip():
    print("\n--- Testing GeoIP ---")
    config = EnterpriseConfig()
    logger = setup_logger("Tester", "test_log.log", logging.DEBUG)
    app_state = AppState(adaptive_batch_min=10, adaptive_sleep_max=1.0)
    
    nm = NetworkManager(
        app_state=app_state,
        doh_resolver_url=config.DOH_RESOLVER_URL,
        network_retry_count=1,
        app_version="1.0",
        logger=logger,
        geoip_db_path=config.GEOIP_DB_PATH
    )
    
    # Test Google DNS IP
    ip = "8.8.8.8"
    print(f"Looking up {ip}...")
    info = await nm.get_geoip_info(ip)
    print(f"Result: {info}")
    
    if info.get('country') == 'United States':
        print("PASS: GeoIP lookup successful")
    else:
        print("FAIL: GeoIP lookup returned unexpected result")

async def test_connectivity_logic():
    print("\n--- Testing Connectivity Logic (Direct Connection) ---")
    config = EnterpriseConfig()
    logger = setup_logger("Tester", "test_log.log", logging.DEBUG)
    
    # Mock dependencies for TestRunner
    xray_manager = XrayManager(config.XRAY_PATH, logger)
    security_validator = SecurityValidator(
        max_uri_length=config.MAX_URI_LENGTH,
        protocol_whitelist=config.PROTOCOL_WHITELIST,
        banned_payloads=config.BANNED_PAYLOADS,
        ip_blacklist=config.IP_BLACKLIST,
        domain_blacklist=config.DOMAIN_BLACKLIST,
        logger=logger
    )
    config_processor = ConfigProcessor(security_validator, logger)
    
    runner = TestRunner(
        xray_manager=xray_manager,
        config_processor=config_processor,
        security_validator=security_validator,
        test_url_ping=config.TEST_URL_PING,
        test_url_download=config.TEST_URL_DOWNLOAD,
        test_url_upload=config.TEST_URL_UPLOAD,
        censorship_check_url=config.CENSORSHIP_CHECK_URL,
        test_timeout=5,
        logger=logger,
        test_url_telegram=config.TEST_URL_TELEGRAM,
        test_url_instagram=config.TEST_URL_INSTAGRAM,
        test_url_youtube=config.TEST_URL_YOUTUBE
    )
    
    # We will call _check_connectivity directly with proxy_url=None to test direct connection
    async with aiohttp.ClientSession() as session:
        print("Checking connectivity to Telegram, Instagram, YouTube...")
        results = await runner._check_connectivity(session, proxy_url=None)
        print(f"Results: {results}")
        
        if results['youtube']:
            print("PASS: YouTube reachable (Direct)")
        else:
            print("WARN: YouTube unreachable (Direct) - might be blocked in this environment")

from core.subscription_manager import SubscriptionManager

async def test_subscription_export():
    print("\n--- Testing Subscription Export ---")
    sm = SubscriptionManager(output_dir="test_subs")
    
    # Dummy results
    results = [
        {
            'protocol': 'vmess',
            'address': '1.2.3.4',
            'port': 443,
            'ping': 100,
            'download_speed': 50.0,
            'config_json': {
                "outbounds": [{
                    "protocol": "vmess",
                    "settings": {
                        "vnext": [{
                            "address": "1.2.3.4",
                            "port": 443,
                            "users": [{"id": "uuid", "alterId": 0}]
                        }]
                    },
                    "streamSettings": {"network": "ws"}
                }]
            }
        }
    ]
    
    outputs = sm.generate_all_formats(results)
    print("Generated formats:", list(outputs.keys()))
    
    if 'hiddify' in outputs and 'nekobox' in outputs:
        print("PASS: Hiddify and NekoBox formats generated")
    else:
        print("FAIL: Missing new formats")

async def main():
    await test_geoip()
    await test_connectivity_logic()
    await test_subscription_export()

if __name__ == "__main__":
    asyncio.run(main())
