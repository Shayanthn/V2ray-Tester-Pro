"""
CLI Runner - v5.4.0
Lightweight facade for CLI mode execution.
Delegates to TestOrchestrator for actual orchestration.
"""

import asyncio
import logging
from typing import List

from core.app_state import AppState
from core.test_runner import TestRunner
from core.config_processor import ConfigProcessor
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager
from core.test_orchestrator import TestOrchestrator, OrchestratorConfig


class CLIRunner:
    """
    Lightweight facade for CLI mode execution.
    
    v5.4.0: Refactored to delegate to TestOrchestrator.
    Maintains backward compatibility with existing main.py interface.
    """
    
    def __init__(self, 
                 app_state: AppState, 
                 test_runner: TestRunner, 
                 config_processor: ConfigProcessor,
                 network_manager: NetworkManager,
                 config_discoverer: ConfigDiscoverer,
                 subscription_manager: SubscriptionManager,
                 aggregator_links: List[str],
                 direct_config_sources: List[str],
                 max_concurrent_tests: int,
                 adaptive_testing: bool,
                 adaptive_batch_max: int,
                 adaptive_batch_min: int,
                 adaptive_sleep_min: float,
                 adaptive_sleep_max: float,
                 logger: logging.Logger,
                 max_success: int = 0):
        
        self.logger = logger
        
        # Create orchestrator config
        config = OrchestratorConfig(
            max_concurrent_tests=max_concurrent_tests,
            adaptive_testing=adaptive_testing,
            adaptive_batch_max=adaptive_batch_max,
            adaptive_batch_min=adaptive_batch_min,
            adaptive_sleep_min=adaptive_sleep_min,
            adaptive_sleep_max=adaptive_sleep_max,
            max_success=max_success,
            enable_rate_limiting=True,
            enable_metrics=True
        )
        
        # Create orchestrator
        self.orchestrator = TestOrchestrator(
            app_state=app_state,
            test_runner=test_runner,
            config_processor=config_processor,
            network_manager=network_manager,
            config_discoverer=config_discoverer,
            subscription_manager=subscription_manager,
            aggregator_links=aggregator_links,
            direct_config_sources=direct_config_sources,
            config=config,
            logger=logger
        )

    def run(self):
        """Entry point for CLI execution."""
        try:
            asyncio.run(self.orchestrator.run())
        except KeyboardInterrupt:
            print("\n⚠️ Graceful shutdown initiated by user...")
            # Orchestrator handles cleanup via GracefulShutdownManager
        except Exception as e:
            self.logger.critical(f"CLI execution failed: {e}", exc_info=True)
            print(f"Critical Error: {e}")

