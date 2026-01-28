"""
Test Orchestrator - v5.4.0
Manages the complete test lifecycle with graceful shutdown support.
"""

import asyncio
import signal
import logging
import time
import os
import json
from typing import Optional, List, Set, Dict, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import aiohttp

from core.app_state import AppState
from core.test_runner import TestRunner
from core.config_processor import ConfigProcessor
from core.network_manager import NetworkManager, ConfigDiscoverer
from core.subscription_manager import SubscriptionManager
from core.iran_optimizer import IranOptimizer
from core.rate_limiter import RateLimiter, DomainRateLimiter, get_rate_limiter
from core.notification_service import NotificationService, get_notification_service
from core.metrics import get_metrics, MetricsRegistry


@dataclass
class OrchestratorConfig:
    """Configuration for the Test Orchestrator."""
    max_concurrent_tests: int = 50
    adaptive_testing: bool = True
    adaptive_batch_max: int = 100
    adaptive_batch_min: int = 10
    adaptive_sleep_min: float = 0.1
    adaptive_sleep_max: float = 2.0
    max_success: int = 0  # 0 = unlimited
    test_timeout: float = 30.0
    graceful_shutdown_timeout: float = 30.0
    enable_rate_limiting: bool = True
    enable_metrics: bool = True


class GracefulShutdownManager:
    """
    Manages graceful shutdown of the application.
    Ensures all resources are properly cleaned up.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._shutdown_event = asyncio.Event()
        self._cleanup_callbacks: List[callable] = []
        self._active_tasks: Set[asyncio.Task] = set()
        self._xray_pids: Set[int] = set()
        self._is_shutting_down = False
    
    def register_cleanup(self, callback: callable) -> None:
        """Register a cleanup callback to be called on shutdown."""
        self._cleanup_callbacks.append(callback)
    
    def register_task(self, task: asyncio.Task) -> None:
        """Register an active task to be cancelled on shutdown."""
        self._active_tasks.add(task)
        task.add_done_callback(lambda t: self._active_tasks.discard(t))
    
    def register_xray_process(self, pid: int) -> None:
        """Register an Xray process PID for cleanup."""
        self._xray_pids.add(pid)
    
    def unregister_xray_process(self, pid: int) -> None:
        """Unregister an Xray process PID."""
        self._xray_pids.discard(pid)
    
    @property
    def should_shutdown(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_event.is_set()
    
    def request_shutdown(self) -> None:
        """Request a graceful shutdown."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        self._shutdown_event.set()
        self.logger.info("Graceful shutdown requested")
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
    
    async def execute_shutdown(self, timeout: float = 30.0) -> None:
        """Execute the shutdown sequence."""
        self.logger.info(f"Executing shutdown sequence (timeout: {timeout}s)")
        start_time = time.time()
        
        # 1. Cancel all active tasks
        self.logger.info(f"Cancelling {len(self._active_tasks)} active tasks...")
        for task in list(self._active_tasks):
            task.cancel()
        
        if self._active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=timeout / 3
                )
            except asyncio.TimeoutError:
                self.logger.warning("Some tasks did not cancel in time")
        
        # 2. Kill all Xray processes
        self.logger.info(f"Terminating {len(self._xray_pids)} Xray processes...")
        for pid in list(self._xray_pids):
            try:
                import subprocess
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                   capture_output=True, timeout=5)
                else:
                    os.kill(pid, signal.SIGTERM)
                self._xray_pids.discard(pid)
            except Exception as e:
                self.logger.warning(f"Failed to kill Xray process {pid}: {e}")
        
        # 3. Run cleanup callbacks
        self.logger.info(f"Running {len(self._cleanup_callbacks)} cleanup callbacks...")
        for callback in self._cleanup_callbacks:
            try:
                elapsed = time.time() - start_time
                remaining = max(1, timeout - elapsed)
                
                if asyncio.iscoroutinefunction(callback):
                    await asyncio.wait_for(callback(), timeout=remaining / len(self._cleanup_callbacks))
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Cleanup callback failed: {e}")
        
        elapsed = time.time() - start_time
        self.logger.info(f"Shutdown complete in {elapsed:.1f}s")


class TestOrchestrator:
    """
    Orchestrates the complete test lifecycle.
    
    Responsibilities:
    - Manages test queue and worker pool
    - Coordinates with IranOptimizer for network bypass
    - Handles rate limiting and metrics
    - Provides graceful shutdown support
    - Separates concerns from CLIRunner
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
                 config: OrchestratorConfig = None,
                 logger: Optional[logging.Logger] = None):
        
        self.app_state = app_state
        self.test_runner = test_runner
        self.config_processor = config_processor
        self.network_manager = network_manager
        self.config_discoverer = config_discoverer
        self.subscription_manager = subscription_manager
        self.aggregator_links = aggregator_links
        self.direct_config_sources = direct_config_sources
        self.config = config or OrchestratorConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Core components
        self.iran_optimizer = IranOptimizer(logger=self.logger)
        self.rate_limiter = get_rate_limiter()
        self.notification_service = get_notification_service()
        self.metrics = get_metrics() if self.config.enable_metrics else None
        self.shutdown_manager = GracefulShutdownManager(logger=self.logger)
        
        # Test state
        self.config_queue: asyncio.Queue = asyncio.Queue()
        self.unique_uris: Set[str] = set()
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Blacklist mechanism
        self.config_blacklist: Set[str] = set()
        self.config_failure_count: Dict[str, int] = {}
        self.max_retries = 3
        
        # History for deduplication
        self.known_configs: Set[str] = set()
        
        # Test timing
        self._start_time: float = 0
        self._workers: List[asyncio.Task] = []
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig):
            self.logger.info(f"Received signal {sig.name}")
            self.shutdown_manager.request_shutdown()
        
        # Handle SIGINT (Ctrl+C) and SIGTERM
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                signal.signal(sig, lambda s, f: signal_handler(signal.Signals(s)))
    
    def _load_known_configs(self) -> None:
        """Load previously found working configs for deduplication."""
        if os.path.exists('results.json'):
            try:
                with open('results.json', 'r', encoding='utf-8') as f:
                    results = json.load(f)
                    for r in results:
                        if r and 'uri' in r:
                            self.known_configs.add(r['uri'])
                self.logger.info(f"Loaded {len(self.known_configs)} known configs from history")
            except Exception as e:
                self.logger.warning(f"Failed to load history: {e}")
    
    async def run(self) -> None:
        """Execute the complete test pipeline."""
        self._start_time = time.time()
        self.app_state.is_running = True
        self.app_state.reset()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_tests)
        
        # Setup
        self._setup_signal_handlers()
        self._load_known_configs()
        
        # Start notification service
        if self.notification_service.is_enabled:
            await self.notification_service.start()
            self.shutdown_manager.register_cleanup(self.notification_service.stop)
        
        print("Initializing network session...")
        
        try:
            timeout = aiohttp.ClientTimeout(total=None)
            connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                self.session = session
                
                # Phase 0: Network Status Check
                print("Phase 0: Checking network status...")
                await self._check_network_status()
                
                if self.shutdown_manager.should_shutdown:
                    return
                
                # Phase 1: Fetch from aggregators
                print(f"Phase 1: Fetching from {len(self.aggregator_links)} aggregators...")
                await self._fetch_and_queue_configs(self.aggregator_links)
                
                if self.shutdown_manager.should_shutdown:
                    return
                
                # Phase 2: Fetch from direct sources
                print(f"Phase 2: Fetching from {len(self.direct_config_sources)} direct sources...")
                await self._fetch_and_queue_configs(self.direct_config_sources)
                
                if self.shutdown_manager.should_shutdown:
                    return
                
                # Phase 2.5: Sort by protocol priority
                print("Sorting configs by protocol priority (Reality/XTLS first)...")
                await self._prioritize_queue()
                
                self.app_state.total = self.config_queue.qsize()
                print(f"Phase 3: Testing {self.app_state.total} configs with {self.config.max_concurrent_tests} workers...")
                
                # Update metrics
                if self.metrics:
                    self.metrics.gauge('configs_queue_size').set(self.app_state.total)
                
                # Phase 3: Run workers
                await self._run_workers()
                
                # Phase 4: Generate output
                if self.app_state.results:
                    print("Phase 4: Generating subscription files...")
                    await self._generate_output()
                
                # Final summary
                duration = time.time() - self._start_time
                self._print_summary(duration)
                
        except Exception as e:
            self.logger.critical(f"Test pipeline failed: {e}", exc_info=True)
            print(f"Error: {str(e)}")
            if self.metrics:
                self.metrics.counter('errors_total').inc(type='critical', component='orchestrator')
        finally:
            await self._cleanup()
    
    async def _check_network_status(self) -> None:
        """Check network status using Iran Optimizer."""
        network_status = await self.iran_optimizer.check_network_status(self.session)
        
        if network_status.get('filtering_detected'):
            print("⚠️  Filtering detected! Enabling advanced bypass features...")
            try:
                clean_ips = await self.iran_optimizer.fetch_clean_ips_from_sources(self.session)
                if clean_ips:
                    print(f"   Found {len(clean_ips)} pre-tested clean IPs")
                    if self.metrics:
                        self.metrics.gauge('clean_ips_available').set(len(clean_ips))
            except Exception as e:
                self.logger.debug(f"Clean IP fetch failed: {e}")
        elif network_status.get('domestic_ok') == False:
            print("❌ Complete internet outage! Cannot proceed.")
            self.shutdown_manager.request_shutdown()
    
    async def _fetch_and_queue_configs(self, sources: List[str]) -> None:
        """Fetch configs from all sources and add to queue."""
        tasks = []
        for url in sources:
            # Rate limiting for fetch operations
            if self.config.enable_rate_limiting:
                await self.rate_limiter.acquire_or_wait(url, 'fetch')
            tasks.append(self._process_source(url))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _process_source(self, url: str) -> None:
        """Process a single source URL."""
        if self.shutdown_manager.should_shutdown:
            return
        
        try:
            configs = await self.config_discoverer.fetch_configs_from_source(url, session=self.session)
            count = 0
            for uri in configs:
                if uri not in self.unique_uris and self.test_runner.security_validator.validate_uri(uri):
                    self.unique_uris.add(uri)
                    await self.config_queue.put(uri)
                    count += 1
            
            if self.metrics:
                self.metrics.counter('network_requests_total').inc(type='fetch', status='success')
        except Exception as e:
            self.logger.warning(f"Failed to process source {url}: {e}")
            if self.metrics:
                self.metrics.counter('network_requests_total').inc(type='fetch', status='error')
    
    async def _prioritize_queue(self) -> None:
        """Re-order queue by protocol priority."""
        all_uris = []
        while not self.config_queue.empty():
            try:
                uri = self.config_queue.get_nowait()
                all_uris.append(uri)
                self.config_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        sorted_uris = IranOptimizer.sort_by_priority(all_uris)
        
        for uri in sorted_uris:
            await self.config_queue.put(uri)
        
        reality_count = sum(1 for u in sorted_uris if 'reality' in u.lower() or 'pbk=' in u.lower())
        xtls_count = sum(1 for u in sorted_uris if 'flow=xtls' in u.lower())
        self.logger.info(f"Priority queue: {reality_count} Reality, {xtls_count} XTLS, {len(sorted_uris) - reality_count - xtls_count} others")
    
    async def _run_workers(self) -> None:
        """Create and manage worker pool."""
        num_workers = min(self.config.max_concurrent_tests, self.config_queue.qsize())
        if num_workers == 0:
            print("No configs found to test.")
            return
        
        if self.metrics:
            self.metrics.gauge('active_workers').set(num_workers)
        
        # Create workers
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]
        
        for worker in self._workers:
            self.shutdown_manager.register_task(worker)
        
        # Monitor progress
        monitor_task = asyncio.create_task(self._monitor_progress())
        self.shutdown_manager.register_task(monitor_task)
        
        # Wait for completion or shutdown (fix: wrap coroutines in tasks)
        try:
            join_task = asyncio.create_task(self.config_queue.join())
            shutdown_task = asyncio.create_task(self.shutdown_manager.wait_for_shutdown())
            done, pending = await asyncio.wait(
                [join_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            pass
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        monitor_task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        if self.metrics:
            self.metrics.gauge('active_workers').set(0)
    
    async def _monitor_progress(self) -> None:
        """Print progress updates."""
        while not self.shutdown_manager.should_shutdown:
            await asyncio.sleep(2)
            total = self.app_state.total
            processed = self.app_state.progress
            found = self.app_state.found
            failed = self.app_state.failed
            percent = (processed / total * 100) if total > 0 else 0
            print(f"Progress: {processed}/{total} ({percent:.1f}%) | Found: {found} | Failed: {failed}", end='\r')
    
    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes configs from the queue."""
        port = 10800 + worker_id
        success_count = 0
        total_count = 0
        consecutive_failures = 0
        
        while not self.shutdown_manager.should_shutdown:
            try:
                # Get next config with timeout
                try:
                    uri = await asyncio.wait_for(self.config_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Skip blacklisted configs
                if uri in self.config_blacklist:
                    self.app_state.progress += 1
                    self.app_state.failed += 1
                    self.config_queue.task_done()
                    continue
                
                async with self.semaphore:
                    test_start = time.time()
                    result = await self._test_config(uri, port)
                    test_duration = time.time() - test_start
                    
                    total_count += 1
                    
                    if result:
                        await self._handle_success(result, uri)
                        success_count += 1
                        consecutive_failures = 0
                        
                        # Check max success limit
                        if self.config.max_success > 0 and self.app_state.found >= self.config.max_success:
                            self.logger.info(f"Reached maximum success limit ({self.config.max_success})")
                            await self._drain_queue()
                            self.config_queue.task_done()
                            return
                    else:
                        await self._handle_failure(uri)
                        consecutive_failures += 1
                    
                    # Record metrics
                    if self.metrics:
                        protocol = self._extract_protocol(uri)
                        self.metrics.histogram('test_duration_seconds').observe(
                            test_duration, protocol=protocol
                        )
                
                # Adaptive sleeping
                if consecutive_failures >= 5:
                    await asyncio.sleep(1)
                    consecutive_failures = 0
                
                self.config_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                self.app_state.failed += 1
                if self.metrics:
                    self.metrics.counter('errors_total').inc(type='worker', component='test')
                try:
                    self.config_queue.task_done()
                except ValueError:
                    pass
    
    async def _test_config(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Test a single config with all bypass strategies."""
        # Build config
        config_json = self.config_processor.build_config_from_uri(uri, port)
        if not config_json:
            return None
        
        # Rate limiting for test
        if self.config.enable_rate_limiting:
            # Extract host from config for rate limiting
            outbound = config_json.get('outbounds', [{}])[0]
            host = outbound.get('settings', {}).get('vnext', [{}])[0].get('address', 'unknown')
            await self.rate_limiter.acquire_or_wait(host, 'test')
        
        # Primary test
        try:
            result = await asyncio.wait_for(
                self.test_runner.run_full_test(config_json, port, self.session),
                timeout=self.config.test_timeout
            )
        except asyncio.TimeoutError:
            result = None
            self._record_failure(uri)
        
        # Try fragment injection
        if not result and IranOptimizer.should_auto_fragment(uri):
            result = await self._try_fragment(config_json, port, uri)
        
        # Try SNI randomization
        if not result and ('vless' in uri.lower() or 'vmess' in uri.lower()):
            result = await self._try_sni_bypass(config_json, port, uri)
        
        return result
    
    async def _try_fragment(self, config_json: dict, port: int, uri: str) -> Optional[Dict[str, Any]]:
        """Try fragment injection bypass."""
        try:
            fragmented_config = self.config_processor.inject_fragment(config_json)
            result = await asyncio.wait_for(
                self.test_runner.run_full_test(fragmented_config, port, self.session),
                timeout=self.config.test_timeout
            )
            if result:
                result['fragment_mode'] = True
                self.logger.info(f"🛡️ Fragment mode success for {uri[:30]}...")
                if self.metrics:
                    self.metrics.counter('fragment_attempts_total').inc(status='success')
            return result
        except Exception:
            if self.metrics:
                self.metrics.counter('fragment_attempts_total').inc(status='failed')
            return None
    
    async def _try_sni_bypass(self, config_json: dict, port: int, uri: str) -> Optional[Dict[str, Any]]:
        """Try SNI randomization bypass."""
        try:
            random_sni = self.iran_optimizer.get_random_sni()
            sni_config = self.iran_optimizer.inject_sni(config_json, random_sni)
            result = await asyncio.wait_for(
                self.test_runner.run_full_test(sni_config, port, self.session),
                timeout=25
            )
            if result:
                result['custom_sni'] = random_sni
                self.logger.info(f"🎭 SNI bypass success with {random_sni}")
                if self.metrics:
                    self.metrics.counter('sni_bypass_attempts_total').inc(status='success')
            return result
        except Exception:
            if self.metrics:
                self.metrics.counter('sni_bypass_attempts_total').inc(status='failed')
            return None
    
    async def _handle_success(self, result: Dict[str, Any], uri: str) -> None:
        """Handle a successful test result."""
        result['uri'] = uri
        
        # GeoIP lookup
        ip = result.get('ip')
        geoip_info = await self.network_manager.get_geoip_info(ip, self.session)
        result.update(geoip_info)
        
        # Update state
        self.app_state.found += 1
        self.app_state.progress += 1
        self.app_state.results.append(result)
        self.app_state.update_stats(result)
        
        # Record metrics
        if self.metrics:
            protocol = result.get('protocol', 'unknown')
            country = result.get('country', 'Unknown')
            self.metrics.counter('configs_tested_total').inc(protocol=protocol, status='success')
            self.metrics.counter('configs_found_total').inc(protocol=protocol, country=country)
            if 'ping' in result:
                self.metrics.histogram('ping_latency_ms').observe(result['ping'], country=country)
            if 'download_speed' in result:
                self.metrics.summary('download_speed_mbps').observe(result['download_speed'], protocol=protocol)
        
        # Reset failure count
        if uri in self.config_failure_count:
            del self.config_failure_count[uri]
        
        # Send notification
        is_new = uri not in self.known_configs
        if is_new:
            await self.notification_service.send_config_notification(result, is_new=True)
    
    async def _handle_failure(self, uri: str) -> None:
        """Handle a failed test."""
        self.app_state.failed += 1
        self.app_state.update_stats(None)
        
        # Record metrics
        if self.metrics:
            protocol = self._extract_protocol(uri)
            self.metrics.counter('configs_tested_total').inc(protocol=protocol, status='failed')
        
        # Track for blacklisting
        self._record_failure(uri)
    
    def _record_failure(self, uri: str) -> None:
        """Record a failure for potential blacklisting."""
        self.config_failure_count[uri] = self.config_failure_count.get(uri, 0) + 1
        if self.config_failure_count[uri] >= self.max_retries:
            self.config_blacklist.add(uri)
            self.logger.info(f"Blacklisted config after {self.max_retries} failures: {uri[:50]}...")
    
    def _extract_protocol(self, uri: str) -> str:
        """Extract protocol from URI."""
        if uri.startswith('vless://'):
            if 'reality' in uri.lower() or 'pbk=' in uri.lower():
                return 'vless-reality'
            return 'vless'
        elif uri.startswith('vmess://'):
            return 'vmess'
        elif uri.startswith('trojan://'):
            return 'trojan'
        elif uri.startswith('ss://'):
            return 'shadowsocks'
        return 'unknown'
    
    async def _drain_queue(self) -> None:
        """Drain the queue to stop workers."""
        while not self.config_queue.empty():
            try:
                self.config_queue.get_nowait()
                self.config_queue.task_done()
            except asyncio.QueueEmpty:
                break
    
    async def _generate_output(self) -> None:
        """Generate subscription files and save results."""
        self.subscription_manager.generate_all_formats(self.app_state.results)
        
        # Save raw results
        with open('results.json', 'w', encoding='utf-8') as f:
            json.dump(self.app_state.results, f, indent=2, ensure_ascii=False)
        
        # Save blacklist
        if self.config_blacklist:
            with open('blacklisted_configs.txt', 'w', encoding='utf-8') as f:
                f.write(f"# Blacklisted configs (failed {self.max_retries}+ times)\n")
                for uri in self.config_blacklist:
                    f.write(f"{uri}\n")
            self.logger.info(f"Saved {len(self.config_blacklist)} blacklisted configs")
        
        # Save metrics
        if self.metrics:
            with open('metrics.txt', 'w', encoding='utf-8') as f:
                f.write(self.metrics.export_prometheus())
        
        print(f"Success! Generated subscriptions in '{self.subscription_manager.output_dir}'")
    
    def _print_summary(self, duration: float) -> None:
        """Print final summary."""
        msg = (
            f"\nTest complete! Found {len(self.app_state.results)} working configs "
            f"({self.app_state.failed} failed, {len(self.config_blacklist)} blacklisted) "
            f"in {duration:.1f}s"
        )
        print(msg)
        self.logger.info(msg)
        
        # Rate limiter stats
        if self.config.enable_rate_limiting:
            stats = self.rate_limiter.get_stats()
            self.logger.info(f"Rate limiter stats: {stats}")
        
        # Metrics export
        if self.metrics:
            print(f"Metrics saved to metrics.txt")
    
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        self.app_state.is_running = False
        
        # Execute graceful shutdown if requested
        if self.shutdown_manager.should_shutdown:
            await self.shutdown_manager.execute_shutdown(
                timeout=self.config.graceful_shutdown_timeout
            )
