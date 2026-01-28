import asyncio
import logging
import aiohttp
import os
from typing import Set, List
from core.app_state import AppState
from core.test_runner import TestRunner
from core.config_processor import ConfigProcessor
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager
from core.iran_optimizer import IranOptimizer
from utils.telegram_notifier import TelegramNotifier

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
                 logger: logging.Logger,
                 max_success: int = 0):
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
        self.max_success = max_success
        self.notifier = TelegramNotifier(logger=logger)
        
        self.config_queue = asyncio.Queue()
        self.unique_uris: Set[str] = set()
        self.semaphore = None
        
        # Blacklist mechanism for repeatedly failing configs
        self.config_blacklist: Set[str] = set()
        self.config_failure_count: dict = {}  # URI -> failure count
        self.max_retries = 3  # Max failures before blacklisting 
        
        # History mechanism to prevent duplicate notifications
        self.known_configs: Set[str] = set()
        
        # Iran Network Optimizer for advanced bypass features
        self.iran_optimizer = IranOptimizer(logger=logger)

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
        
        # Load known configs from previous run
        self._load_known_configs()
        
        print("Initializing network session...")
        try:
            timeout = aiohttp.ClientTimeout(total=None) 
            connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                self.session = session
                
                # Phase 0: Network Status Check (Iran Optimizer)
                print("Phase 0: Checking network status...")
                network_status = await self.iran_optimizer.check_network_status(session)
                if network_status.get('filtering_detected'):
                    print("⚠️  Filtering detected! Enabling advanced bypass features...")
                    # Fetch clean IPs for potential use
                    try:
                        clean_ips = await self.iran_optimizer.fetch_clean_ips_from_sources(session)
                        if clean_ips:
                            print(f"   Found {len(clean_ips)} pre-tested clean IPs")
                    except Exception as e:
                        self.logger.debug(f"Clean IP fetch failed: {e}")
                elif network_status.get('domestic_ok') == False:
                    print("❌ Complete internet outage! Cannot proceed.")
                    return
                
                # Phase 1: Aggregation
                print(f"Phase 1: Fetching from {len(self.aggregator_links)} aggregators...")
                await self._fetch_and_queue_configs(self.aggregator_links)
                
                # Phase 2: Direct Sources
                print(f"Phase 2: Fetching from {len(self.direct_config_sources)} direct sources...")
                await self._fetch_and_queue_configs(self.direct_config_sources)
                
                # Phase 2.5: Sort queue by protocol priority (Reality > XTLS > TLS)
                print("Sorting configs by protocol priority (Reality/XTLS first)...")
                await self._prioritize_queue()
                
                self.app_state.total = self.config_queue.qsize()
                print(f"Phase 3: Testing {self.app_state.total} configs with {self.max_concurrent_tests} concurrent workers...")
                
                # Phase 3: Testing
                await self._run_workers()
                
                # Phase 4: Completion
                if self.app_state.results:
                    print("Phase 4: Generating subscription files...")
                    self.subscription_manager.generate_all_formats(self.app_state.results)
                    
                    # Save raw results for statistics
                    import json
                    with open('results.json', 'w', encoding='utf-8') as f:
                        json.dump(self.app_state.results, f, indent=2, ensure_ascii=False)
                    
                    # Save blacklist for debugging
                    if self.config_blacklist:
                        with open('blacklisted_configs.txt', 'w', encoding='utf-8') as f:
                            f.write(f"# Blacklisted configs (failed {self.max_retries}+ times)\n")
                            for uri in self.config_blacklist:
                                f.write(f"{uri}\n")
                        self.logger.info(f"Saved {len(self.config_blacklist)} blacklisted configs")
                        
                    print(f"Success! Generated subscriptions in '{self.subscription_manager.output_dir}'")
                    
                    # Telegram Summary DISABLED by user request
                    # if self.notifier.is_enabled:
                        # print("Sending summary to Telegram...")
                        # ...
                
                final_msg = (f"Test complete! Found {len(self.app_state.results)} working configs "
                             f"({self.app_state.failed} failed, {len(self.config_blacklist)} blacklisted).")
                print(final_msg)
                self.logger.info(final_msg)
            
        except Exception as e:
            self.logger.critical(f"Test pipeline failed: {e}", exc_info=True)
            print(f"Error: {str(e)}")
        finally:
            self.app_state.is_running = False
    
    def _load_known_configs(self):
        """Loads previously found working configs to avoid duplicate notifications."""
        import json
        if os.path.exists('results.json'):
            try:
                with open('results.json', 'r', encoding='utf-8') as f:
                    results = json.load(f)
                    for r in results:
                        if r and 'uri' in r:
                            self.known_configs.add(r['uri'])
                self.logger.info(f"Loaded {len(self.known_configs)} known configs from history.")
            except Exception as e:
                self.logger.warning(f"Failed to load history: {e}")

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
    
    async def _prioritize_queue(self):
        """Re-orders the queue to prioritize Reality/XTLS protocols."""
        # Drain the queue
        all_uris = []
        while not self.config_queue.empty():
            try:
                uri = self.config_queue.get_nowait()
                all_uris.append(uri)
                self.config_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        # Sort by protocol priority (Reality > XTLS > VLESS+TLS > VMess > others)
        sorted_uris = IranOptimizer.sort_by_priority(all_uris)
        
        # Re-queue in priority order
        for uri in sorted_uris:
            await self.config_queue.put(uri)
        
        # Log priority distribution
        reality_count = sum(1 for u in sorted_uris if 'reality' in u.lower() or 'pbk=' in u.lower())
        xtls_count = sum(1 for u in sorted_uris if 'flow=xtls' in u.lower())
        self.logger.info(f"Priority queue: {reality_count} Reality, {xtls_count} XTLS, {len(sorted_uris) - reality_count - xtls_count} others")

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
        consecutive_failures = 0
        
        while True:
            try:
                uri = await self.config_queue.get()
                
                # Check if config is blacklisted
                if uri in self.config_blacklist:
                    self.logger.debug(f"Skipping blacklisted config: {uri[:50]}...")
                    self.app_state.progress += 1
                    self.app_state.failed += 1
                    self.config_queue.task_done()
                    continue
                
                async with self.semaphore:
                    try:
                        # Process the URI
                        config_json = self.config_processor.build_config_from_uri(uri, port)
                        if not config_json:
                            self.logger.warning(f"Failed to build config from URI: {uri[:50]}...")
                            self.app_state.failed += 1
                            self.app_state.progress += 1
                            self.config_queue.task_done()
                            continue
                        
                        # Run async test with timeout
                        try:
                            test_result = await asyncio.wait_for(
                                self.test_runner.run_full_test(config_json, port, self.session),
                                timeout=30  # 30 second timeout per config
                            )
                        except asyncio.TimeoutError:
                            self.logger.warning(f"Test timeout for config on port {port}")
                            test_result = None
                            # Track failure for potential blacklisting
                            self.config_failure_count[uri] = self.config_failure_count.get(uri, 0) + 1
                            if self.config_failure_count[uri] >= self.max_retries:
                                self.config_blacklist.add(uri)
                                self.logger.info(f"Blacklisted config after {self.max_retries} failures: {uri[:50]}...")
                        
                        total_count += 1
                        
                        # Feature: Proactive Fragment Injection for TLS-based protocols
                        # Apply fragment BEFORE first test for eligible configs
                        should_fragment = IranOptimizer.should_auto_fragment(uri)
                        if should_fragment and not test_result:
                            try:
                                fragmented_config = self.config_processor.inject_fragment(config_json)
                                if len(fragmented_config.get('outbounds', [])) > len(config_json.get('outbounds', [])):
                                    # Test with fragment first
                                    fragment_result = await asyncio.wait_for(
                                        self.test_runner.run_full_test(fragmented_config, port, self.session),
                                        timeout=30
                                    )
                                    if fragment_result:
                                        test_result = fragment_result
                                        test_result['fragment_mode'] = True
                                        self.logger.info(f"🛡️ Fragment mode success for {uri[:30]}...")
                            except Exception:
                                pass
                        
                        # Feature: SNI Randomization retry if still failing
                        if not test_result and ('vless' in uri.lower() or 'vmess' in uri.lower()):
                            try:
                                random_sni = self.iran_optimizer.get_random_sni()
                                sni_config = self.iran_optimizer.inject_sni(config_json, random_sni)
                                sni_result = await asyncio.wait_for(
                                    self.test_runner.run_full_test(sni_config, port, self.session),
                                    timeout=25
                                )
                                if sni_result:
                                    test_result = sni_result
                                    test_result['custom_sni'] = random_sni
                                    self.logger.info(f"🎭 SNI bypass success with {random_sni} for {uri[:30]}...")
                            except Exception:
                                pass

                        if test_result:
                            test_result['uri'] = uri
                            
                            # GeoIP Lookup
                            ip = test_result.get('ip')
                            geoip_info = await self.network_manager.get_geoip_info(ip, self.session)
                            test_result.update(geoip_info)
                            
                            self.app_state.found += 1
                            self.app_state.progress += 1  # Bug fix: increment progress on success
                            success_count += 1
                            consecutive_failures = 0
                            self.app_state.results.append(test_result)
                            self.app_state.update_stats(test_result)
                            
                            # Real-time Telegram Notification
                            # Only notify if this is a FREAKING NEW config (not in history)
                            is_duplicate = uri in self.known_configs
                            
                            if self.notifier.is_enabled and not is_duplicate:
                                try:
                                    proto = test_result.get('protocol', 'unknown').upper()
                                    ping = test_result.get('ping', 0)
                                    dl_speed = test_result.get('download_speed', 0)
                                    country = test_result.get('country', 'Unknown')
                                    is_fragment = test_result.get('revived_with_fragment', False)
                                    
                                    feature_tags = []
                                    if is_fragment:
                                        feature_tags.append("🛡️ **Mode**: Anti-Filter (Fragment)")
                                    if dl_speed > 5:
                                        feature_tags.append("🚀 **High Speed**")
                                    
                                    tags_str = "\n".join(feature_tags) + ("\n" if feature_tags else "")

                                    # Create fire-and-forget task to avoid blocking testing
                                    
                                    msg = (
                                        f"🟢 **New Config Found**\n\n"
                                        f"🔐 **Protocol**: {proto}\n"
                                        f"📶 **Ping**: {ping} ms\n"
                                        f"⚡ **Speed**: {dl_speed} MB/s\n"
                                        f"🌍 **Location**: {country}\n"
                                        f"{tags_str}\n"
                                        f"📋 **Config** (Tap to copy):\n"
                                        f"`{uri}`\n\n"
                                        f"🤝 نشر حداکثری این کانال برای دسترسی هموطنامون به اینترنت بر عهده ماست\n"
                                        f"🕊️ اینترنت آزاد برای مردم وطنم\n"
                                        f"🆔 {self.notifier.chat_id}"
                                    )
                                    asyncio.create_task(self.notifier.send_message(msg))
                                except Exception as notify_err:
                                    self.logger.warning(f"Failed to send immediate notification: {notify_err}")
                            elif is_duplicate:
                                self.logger.info(f"Skipping Telegram notification for duplicate config: {uri[:30]}...")
                            
                            # Check if max_success limit reached
                            if self.max_success > 0 and self.app_state.found >= self.max_success:
                                self.logger.info(f"Reached maximum success limit ({self.max_success}). Stopping tests.")
                                # Drain queue to stop other workers
                                while not self.config_queue.empty():
                                    try:
                                        self.config_queue.get_nowait()
                                        self.config_queue.task_done()
                                    except asyncio.QueueEmpty:
                                        break
                                self.config_queue.task_done()
                                return

                            # Reset failure count on success
                            if uri in self.config_failure_count:
                                del self.config_failure_count[uri]
                        else:
                            self.app_state.failed += 1
                            consecutive_failures += 1
                            self.app_state.update_stats(None)
                            
                            # Track failure for potential blacklisting
                            self.config_failure_count[uri] = self.config_failure_count.get(uri, 0) + 1
                            if self.config_failure_count[uri] >= self.max_retries:
                                self.config_blacklist.add(uri)
                                self.logger.info(f"Blacklisted config after {self.max_retries} failures: {uri[:50]}...")
                    
                    except Exception as e:
                        # Resilient error handling: Log error but keep worker alive
                        self.logger.error(f"Worker unexpected error processing {uri[:30]}...: {e}")
                        self.app_state.failed += 1
                        
                        # Don't increment failure count here blindly to avoid blacklisting transient errors
                        # Just move on to the next config
                if self.adaptive_testing and total_count % 10 == 0:
                    self.app_state.update_adaptive_params(
                        success_count, total_count, 
                        self.adaptive_batch_max, self.adaptive_batch_min,
                        self.adaptive_sleep_min, self.adaptive_sleep_max
                    )
                    if self.app_state.adaptive_sleep > 0:
                        await asyncio.sleep(self.app_state.adaptive_sleep)
                
                # Add small delay if seeing too many consecutive failures
                if consecutive_failures >= 5:
                    await asyncio.sleep(1)
                    consecutive_failures = 0
                
                self.config_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} critical error: {e}", exc_info=True)
                self.app_state.progress += 1
                self.config_queue.task_done()
