import asyncio
from typing import Dict, Optional, List

class AppState:
    """Centralized application state management with enhanced monitoring."""
    def __init__(self, adaptive_batch_min: int, adaptive_sleep_max: float):
        self.is_running = False
        self.current_phase = "Idle"
        self.progress = 0
        self.total = 0
        self.found = 0
        self.failed = 0
        self.results: List[Dict] = []
        self.stop_signal = asyncio.Event()
        self.ip_cache: Dict[str, str] = {}
        self.uri_cache: set = set()
        self.start_time = None
        self.api_rate_limited = False
        self.adaptive_batch_size = adaptive_batch_min
        self.adaptive_sleep = adaptive_sleep_max
        self.success_rate = 0.0
        self.currently_testing = ""
        # CLI/Automation settings
        self.output_dir = "subscriptions"
        self.max_configs = 0 # 0 means unlimited/default
        
        self.stats = {
            "total_tested": 0,
            "total_success": 0,
            "total_failed": 0,
            "avg_ping": 0,
            "avg_download": 0,
            "top_performer": None
        }
        
    def reset(self):
        """Resets the application state for a new test run."""
        self.is_running = False
        self.current_phase = "Idle"
        self.progress = 0
        self.total = 0
        self.found = 0
        self.failed = 0
        self.results = []
        self.stop_signal.clear()
        self.uri_cache.clear()
        self.start_time = None
        self.api_rate_limited = False
        # Note: adaptive params are reset in main or by config if needed, 
        # but here we keep them or reset them if passed again.
        # For simplicity, we won't reset adaptive params to default here 
        # unless we store the defaults.
        self.success_rate = 0.0
        self.currently_testing = ""
        self.stats = {
            "total_tested": 0,
            "total_success": 0,
            "total_failed": 0,
            "avg_ping": 0,
            "avg_download": 0,
            "top_performer": None
        }

    def update_adaptive_params(self, success_count, total_count, adaptive_batch_max, adaptive_batch_min, adaptive_sleep_min, adaptive_sleep_max):
        """Updates adaptive testing parameters based on success rate."""
        if total_count == 0:
            return
            
        self.success_rate = success_count / total_count
        
        # Adjust batch size based on success rate
        if self.success_rate > 0.8:  # High success rate
            self.adaptive_batch_size = min(
                self.adaptive_batch_size + 10, adaptive_batch_max
            )
            self.adaptive_sleep = max(
                self.adaptive_sleep - 0.05, adaptive_sleep_min
            )
        elif self.success_rate < 0.2:  # Low success rate
            self.adaptive_batch_size = max(
                self.adaptive_batch_size - 10, adaptive_batch_min
            )
            self.adaptive_sleep = min(
                self.adaptive_sleep + 0.1, adaptive_sleep_max
            )

    def update_stats(self, result: Optional[Dict]):
        """Updates application statistics with a new test result."""
        self.stats["total_tested"] += 1
        if result:
            self.stats["total_success"] += 1
            
            # Update averages using incremental averaging
            total_s = self.stats["total_success"]
            self.stats["avg_ping"] = (self.stats["avg_ping"] * (total_s - 1) + result['ping']) / total_s
            self.stats["avg_download"] = (self.stats["avg_download"] * (total_s - 1) + result['download_speed']) / total_s
            
            # Update top performer
            current_top = self.stats["top_performer"]
            if not current_top or result['download_speed'] > current_top["download_speed"]:
                self.stats["top_performer"] = {
                    "protocol": result['protocol'],
                    "address": result['address'],
                    "ping": result['ping'],
                    "download_speed": result['download_speed']
                }
        else:
            self.stats["total_failed"] += 1
