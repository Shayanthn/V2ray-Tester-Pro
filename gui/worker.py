import asyncio
import logging
import re
import base64
import aiohttp
from typing import Set
from PyQt6.QtCore import QThread, pyqtSignal

from core.app_state import AppState
from core.test_runner import TestRunner
from core.config_processor import ConfigProcessor
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager
from utils.security_validator import SecurityValidator

class Worker(QThread):
    """Background worker for running tests without freezing the GUI."""
    update_progress = pyqtSignal(int)
    update_status = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    current_test = pyqtSignal(str)
    
    def __init__(self, 
                 app_state: AppState, 
                 test_runner: TestRunner, 
                 config_processor: ConfigProcessor,
                 network_manager: NetworkManager,
                 config_discoverer: ConfigDiscoverer,
                 subscription_manager: SubscriptionManager,
                 aggregator_links: list,
                 direct_config_sources: list,
                 max_concurrent_tests: int,
                 adaptive_testing: bool,
                 adaptive_batch_max: int,
                 adaptive_batch_min: int,
                 adaptive_sleep_min: float,
                 adaptive_sleep_max: float,
                 logger: logging.Logger):
        super().__init__()
        self.app_state = app_state
        self.test_runner = test_runner
        self.config_processor = config_processor
        self.network_manager = network_manager
        self.config_discoverer = config_discoverer
        self.subscription_manager = subscription_manager
        self.aggregator_links = aggregator_links

        self.direct_config_sources = direct_config_sources
        self.max_concurrent_tests = max_concurrent_tests
        self.adaptive_testing = adaptive_testing
        self.adaptive_batch_max = adaptive_batch_max
        self.adaptive_batch_min = adaptive_batch_min
        self.adaptive_sleep_min = adaptive_sleep_min
        self.adaptive_sleep_max = adaptive_sleep_max
        self.logger = logger
        
        self.config_queue = asyncio.Queue()
        self.unique_uris: Set[str] = set()
        # Semaphore for concurrency control (redundant with fixed workers but good practice)
        self.semaphore = None 

    def run(self):
        """Entry point for the QThread."""
        asyncio.run(self._async_run())

    async def _async_run(self):
        """Async wrapper for the main testing logic."""
        self.app_state.is_running = True
        self.app_state.reset()
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tests)
        
        try:
            # Create a shared ClientSession for all networking
            # Disable default timeout here, control it per request
            timeout = aiohttp.ClientTimeout(total=None) 
            connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                self.session = session
                
                # Phase 1: Aggregation
                self.update_status.emit("Phase 1: Fetching from aggregators...")
                await self._fetch_and_queue_configs(self.aggregator_links)
                
                # Phase 2: Direct Sources
                self.update_status.emit("Phase 2: Fetching from direct sources...")
                await self._fetch_and_queue_configs(self.direct_config_sources)
                
                self.app_state.total = self.config_queue.qsize()
                self.update_status.emit(f"Phase 3: Testing {self.app_state.total} configs...")
                
                # Phase 3: Testing
                await self._run_workers()
                
                # Phase 4: Completion
                if self.app_state.results:
                    self.update_status.emit("Generating subscription files...")
                    # Subscription generation is CPU bound, run in executor if needed, 
                    # but it's fast enough for now.
                    self.subscription_manager.generate_all_formats(self.app_state.results)
                
                final_msg = (f"Test complete! Found {len(self.app_state.results)} working configs "
                             f"({self.app_state.failed} failed).")
                self.update_status.emit(final_msg)
            
        except Exception as e:
            self.logger.critical(f"Test pipeline failed: {e}", exc_info=True)
            self.update_status.emit(f"Error: {str(e)}")
        finally:
            self.app_state.is_running = False
            self.finished.emit()
    
    async def _fetch_and_queue_configs(self, sources: Set[str]):
        """Fetches configs from all sources and puts them in the queue."""
        tasks = [self._process_source(url) for url in sources]
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _process_source(self, url: str):
        """Processes a single source URL and adds valid URIs to the queue."""
        try:
            configs = await self.config_discoverer.fetch_configs_from_source(url, session=self.session)
            for uri in configs:
                if uri not in self.unique_uris and self.test_runner.security_validator.validate_uri(uri):
                    self.unique_uris.add(uri)
                    await self.config_queue.put(uri)
        except Exception as e:
            self.logger.warning(f"Failed to process source {url}: {e}")
    
    async def _run_workers(self):
        """Creates and manages a pool of worker tasks."""
        num_workers = min(self.max_concurrent_tests, self.config_queue.qsize())
        if num_workers == 0:
            return

        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]
        
        await self.config_queue.join()
        
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def _worker(self, worker_id: int):
        """Worker task that processes URIs from the queue."""
        port = 10800 + worker_id
        success_count = 0
        total_count = 0
        
        while True:
            try:
                if self.app_state.stop_signal.is_set():
                    break
                    
                uri = await self.config_queue.get()
                
                # Update currently testing URI
                self.app_state.currently_testing = uri
                self.current_test.emit(uri)
                
                async with self.semaphore:
                    # Process the URI
                    config_json = self.config_processor.build_config_from_uri(uri, port)
                    if config_json:
                        # Run async test
                        test_result = await self.test_runner.run_full_test(
                            config_json, port, self.session
                        )
                        
                        total_count += 1
                        
                        if test_result:
                            test_result['uri'] = uri
                            test_result['country'] = "Unknown" 
                            
                            self.app_state.found += 1
                            success_count += 1
                            self.app_state.results.append(test_result)
                            self.app_state.update_stats(test_result)
                                
                            self.result_ready.emit(test_result)
                        else:
                            self.app_state.failed += 1
                            self.app_state.update_stats(None)
                
                # Update progress
                self.app_state.progress += 1
                self.update_progress.emit(self.app_state.progress)
                
                # Update adaptive parameters
                if self.adaptive_testing and total_count % 10 == 0:
                    self.app_state.update_adaptive_params(
                        success_count, total_count, 
                        self.adaptive_batch_max, self.adaptive_batch_min,
                        self.adaptive_sleep_min, self.adaptive_sleep_max
                    )
                    if self.app_state.adaptive_sleep > 0:
                        await asyncio.sleep(self.app_state.adaptive_sleep)
                
                self.config_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}")
                self.config_queue.task_done()
                if self.app_state.stop_signal.is_set():
                    break
                    
                uri = await self.config_queue.get()
                
                # Update currently testing URI
                self.app_state.currently_testing = uri
                self.current_test.emit(uri)
                
                # Process the URI
                config_json = self.config_processor.build_config_from_uri(uri, port)
                if config_json:
                    # Run blocking test in thread pool
                    loop = asyncio.get_event_loop()
                    test_result = await loop.run_in_executor(
                        self.thread_pool, self.test_runner.run_full_test, config_json, port
                    )
                    
                    total_count += 1
                    
                    if test_result:
                        test_result['uri'] = uri
                        
                        # Get GeoIP info (using NetworkManager logic if needed, or simple lookup)
                        # For now, we skip complex GeoIP to keep it simple or use a placeholder
                        # In original code it called self._get_country_from_ip which used aiohttp
                        # We can add that to NetworkManager if needed, but for now let's assume it's handled or skipped
                        test_result['country'] = "Unknown" 
                        
                        self.app_state.found += 1
                        success_count += 1
                        self.app_state.results.append(test_result)
                        self.app_state.update_stats(test_result)
                            
                        self.result_ready.emit(test_result)
                    else:
                        self.app_state.failed += 1
                        self.app_state.update_stats(None)
                
                # Update progress
                self.app_state.progress += 1
                self.update_progress.emit(self.app_state.progress)
                
                # Update adaptive parameters
                if self.adaptive_testing and total_count % 10 == 0:
                    self.app_state.update_adaptive_params(
                        success_count, total_count, 
                        self.adaptive_batch_max, self.adaptive_batch_min,
                        self.adaptive_sleep_min, self.adaptive_sleep_max
                    )
                    if self.app_state.adaptive_sleep > 0:
                        await asyncio.sleep(self.app_state.adaptive_sleep)
                
                self.config_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}")
                self.config_queue.task_done()
