import asyncio
import logging
import aiohttp
from typing import Set, List
from core.app_state import AppState
from core.test_runner import TestRunner
from core.config_processor import ConfigProcessor
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager
from core.realtime_saver import RealtimeConfigSaver

class CLIRunner:
    """Manages the execution of tests in CLI mode."""
    
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
                 logger: logging.Logger):
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
        
        # Real-time config saver for modular architecture
        self.realtime_saver = RealtimeConfigSaver('working_configs.json', logger)
        
        self.config_queue = asyncio.Queue()
        self.unique_uris: Set[str] = set()
        self.semaphore = None 

    def run(self):
        """Entry point for CLI execution."""
        try:
            asyncio.run(self._async_run())
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
        except Exception as e:
            self.logger.critical(f"CLI execution failed: {e}", exc_info=True)
            print(f"Critical Error: {e}")

    async def _async_run(self):
        """Async wrapper for the main testing logic."""
        self.app_state.is_running = True
        self.app_state.reset()
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tests)
        
        print("Initializing network session...")
        try:
            timeout = aiohttp.ClientTimeout(total=None) 
            connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                self.session = session
                
                # Phase 1: Aggregation
                print(f"Phase 1: Fetching from {len(self.aggregator_links)} aggregators...")
                await self._fetch_and_queue_configs(self.aggregator_links)
                
                # Phase 2: Direct Sources
                print(f"Phase 2: Fetching from {len(self.direct_config_sources)} direct sources...")
                await self._fetch_and_queue_configs(self.direct_config_sources)
                
                self.app_state.total = self.config_queue.qsize()
                print(f"Phase 3: Testing {self.app_state.total} configs with {self.max_concurrent_tests} concurrent workers...")
                
                # Phase 3: Testing
                await self._run_workers()
                
                # Phase 4: Completion
                if self.app_state.results:
                    print("Phase 4: Generating subscription files...")
                    self.subscription_manager.generate_all_formats(self.app_state.results)
                    print(f"Success! Generated subscriptions in '{self.subscription_manager.output_dir}'")
                
                final_msg = (f"Test complete! Found {len(self.app_state.results)} working configs "
                             f"({self.app_state.failed} failed).")
                print(final_msg)
            
        except Exception as e:
            self.logger.critical(f"Test pipeline failed: {e}", exc_info=True)
            print(f"Error: {str(e)}")
        finally:
            self.app_state.is_running = False
    
    async def _fetch_and_queue_configs(self, sources: List[str]):
        """Fetches configs from all sources and puts them in the queue."""
        tasks = [self._process_source(url) for url in sources]
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _process_source(self, url: str):
        """Processes a single source URL and adds valid URIs to the queue."""
        try:
            # Assuming ConfigDiscoverer has this method based on Worker usage
            configs = await self.config_discoverer.fetch_configs_from_source(url, session=self.session)
            count = 0
            for uri in configs:
                if uri not in self.unique_uris and self.test_runner.security_validator.validate_uri(uri):
                    self.unique_uris.add(uri)
                    await self.config_queue.put(uri)
                    count += 1
            # self.logger.info(f"Fetched {count} configs from {url}")
        except Exception as e:
            self.logger.warning(f"Failed to process source {url}: {e}")
    
    async def _run_workers(self):
        """Creates and manages a pool of worker tasks."""
        num_workers = min(self.max_concurrent_tests, self.config_queue.qsize())
        if num_workers == 0:
            print("No configs found to test.")
            return

        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]
        
        # Monitor progress
        monitor_task = asyncio.create_task(self._monitor_progress())
        
        await self.config_queue.join()
        
        for worker in workers:
            worker.cancel()
        
        monitor_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def _monitor_progress(self):
        """Prints progress updates to CLI."""
        while True:
            await asyncio.sleep(2)
            total = self.app_state.total
            processed = self.app_state.progress
            found = self.app_state.found
            failed = self.app_state.failed
            percent = (processed / total * 100) if total > 0 else 0
            print(f"Progress: {processed}/{total} ({percent:.1f}%) | Found: {found} | Failed: {failed}", end='\r')

    async def _worker(self, worker_id: int):
        """Worker task that processes URIs from the queue."""
        port = 10800 + worker_id
        success_count = 0
        total_count = 0
        
        while True:
            try:
                uri = await self.config_queue.get()
                
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
                            
                            # GeoIP Lookup
                            ip = test_result.get('ip')
                            geoip_info = await self.network_manager.get_geoip_info(ip, self.session)
                            test_result.update(geoip_info)
                            
                            self.app_state.found += 1
                            success_count += 1
                            self.app_state.results.append(test_result)
                            self.app_state.update_stats(test_result)
                            
                            # 🔥 REAL-TIME SAVE: Save immediately!
                            self.realtime_saver.save_config(test_result)
                        else:
                            self.app_state.failed += 1
                            self.app_state.update_stats(None)
                
                # Update progress
                self.app_state.progress += 1
                
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
