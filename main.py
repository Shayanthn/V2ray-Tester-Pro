import sys
import logging
import argparse

# Import modules
from config.enterprise_config import EnterpriseConfig
from utils.logger import setup_logger
from utils.security_validator import SecurityValidator
from core.app_state import AppState
from core.xray_manager import XrayManager
from core.config_processor import ConfigProcessor
from core.test_runner import TestRunner
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager

def main():
    # 1. Initialize Configuration
    config = EnterpriseConfig()
    
    # 2. Setup Logging
    logger = setup_logger(
        name="EnterpriseApp",
        log_file=config.LOG_FILE,
        level=logging.INFO
    )
    
    # 3. Parse CLI Arguments
    parser = argparse.ArgumentParser(description=config.APP_NAME)
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('--max-configs', type=int, default=0, help='Limit number of configs to test')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        
    # 4. Initialize Core Dependencies (Dependency Injection)
    
    # Utils
    security_validator = SecurityValidator(
        max_uri_length=config.MAX_URI_LENGTH,
        protocol_whitelist=config.PROTOCOL_WHITELIST,
        banned_payloads=config.BANNED_PAYLOADS,
        ip_blacklist=config.IP_BLACKLIST,
        domain_blacklist=config.DOMAIN_BLACKLIST,
        logger=logger
    )
    
    # Core Managers
    app_state = AppState(
        adaptive_batch_min=config.ADAPTIVE_BATCH_MIN,
        adaptive_sleep_max=config.ADAPTIVE_SLEEP_MAX
    )
    
    xray_manager = XrayManager(
        xray_path=config.XRAY_PATH,
        logger=logger
    )
    
    config_processor = ConfigProcessor(
        security_validator=security_validator,
        logger=logger
    )
    
    test_runner = TestRunner(
        xray_manager=xray_manager,
        config_processor=config_processor,
        security_validator=security_validator,
        test_url_ping=config.TEST_URL_PING,
        test_url_download=config.TEST_URL_DOWNLOAD,
        test_url_upload=config.TEST_URL_UPLOAD,
        censorship_check_url=config.CENSORSHIP_CHECK_URL,
        test_timeout=config.TEST_TIMEOUT,
        logger=logger,
        test_url_telegram=config.TEST_URL_TELEGRAM,
        test_url_instagram=config.TEST_URL_INSTAGRAM,
        test_url_youtube=config.TEST_URL_YOUTUBE
    )
    
    network_manager = NetworkManager(
        app_state=app_state,
        doh_resolver_url=config.DOH_RESOLVER_URL,
        network_retry_count=config.NETWORK_RETRY_COUNT,
        app_version=config.APP_VERSION,
        logger=logger,
        geoip_db_path=config.GEOIP_DB_PATH
    )
    
    config_discoverer = ConfigDiscoverer(
        network_manager=network_manager,
        logger=logger
    )
    
    subscription_manager = SubscriptionManager(
        output_dir="subscriptions"
    )
    
    # 6. Launch Application
    if args.cli:
        logger.info("Starting in CLI mode...")
        from core.cli_runner import CLIRunner
        
        runner = CLIRunner(
            app_state=app_state,
            test_runner=test_runner,
            config_processor=config_processor,
            network_manager=network_manager,
            config_discoverer=config_discoverer,
            subscription_manager=subscription_manager,
            aggregator_links=config.AGGREGATOR_LINKS,
            direct_config_sources=config.DIRECT_CONFIG_SOURCES,
            max_concurrent_tests=config.MAX_CONCURRENT_TESTS,
            adaptive_testing=config.ADAPTIVE_TESTING,
            adaptive_batch_max=config.ADAPTIVE_BATCH_MAX,
            adaptive_batch_min=config.ADAPTIVE_BATCH_MIN,
            adaptive_sleep_min=config.ADAPTIVE_SLEEP_MIN,
            adaptive_sleep_max=config.ADAPTIVE_SLEEP_MAX,
            logger=logger
        )
        runner.run()
        
    else:
        logger.info("Starting in GUI mode...")
        # Lazy load GUI dependencies
        from PyQt6.QtWidgets import QApplication
        from gui.worker import Worker
        from gui.main_window import MainWindow

        # 5. Define Worker Factory (for GUI to create workers on demand)
        def create_worker():
            return Worker(
                app_state=app_state,
                test_runner=test_runner,
                config_processor=config_processor,
                network_manager=network_manager,
                config_discoverer=config_discoverer,
                subscription_manager=subscription_manager,
                aggregator_links=config.AGGREGATOR_LINKS,
                direct_config_sources=config.DIRECT_CONFIG_SOURCES,
                max_concurrent_tests=config.MAX_CONCURRENT_TESTS,
                adaptive_testing=config.ADAPTIVE_TESTING,
                adaptive_batch_max=config.ADAPTIVE_BATCH_MAX,
                adaptive_batch_min=config.ADAPTIVE_BATCH_MIN,
                adaptive_sleep_min=config.ADAPTIVE_SLEEP_MIN,
                adaptive_sleep_max=config.ADAPTIVE_SLEEP_MAX,
                logger=logger
            )

        app = QApplication(sys.argv)
        window = MainWindow(
            app_state=app_state,
            worker_factory=create_worker,
            config=config,
            logger=logger
        )
        window.show()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()
