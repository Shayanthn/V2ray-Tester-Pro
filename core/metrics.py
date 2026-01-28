"""
Prometheus Metrics Module - v5.4.0
Production-grade observability for monitoring and alerting.
"""

import time
import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import json
import logging


@dataclass
class MetricValue:
    """Single metric value with metadata."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metric_type: str = 'gauge'  # gauge, counter, histogram, summary


class Counter:
    """Prometheus-style Counter metric."""
    
    def __init__(self, name: str, description: str, labels: list = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def inc(self, amount: float = 1.0, **labels) -> None:
        """Increment the counter."""
        if amount < 0:
            raise ValueError("Counter can only be incremented")
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += amount
    
    def get(self, **labels) -> float:
        """Get current counter value."""
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0.0)
    
    def collect(self) -> list:
        """Collect all metric values for export."""
        results = []
        with self._lock:
            for key, value in self._values.items():
                labels = dict(key)
                results.append(MetricValue(
                    name=self.name,
                    value=value,
                    labels=labels,
                    metric_type='counter'
                ))
        return results


class Gauge:
    """Prometheus-style Gauge metric."""
    
    def __init__(self, name: str, description: str, labels: list = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def set(self, value: float, **labels) -> None:
        """Set the gauge value."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value
    
    def inc(self, amount: float = 1.0, **labels) -> None:
        """Increment the gauge."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += amount
    
    def dec(self, amount: float = 1.0, **labels) -> None:
        """Decrement the gauge."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] -= amount
    
    def get(self, **labels) -> float:
        """Get current gauge value."""
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0.0)
    
    def collect(self) -> list:
        """Collect all metric values for export."""
        results = []
        with self._lock:
            for key, value in self._values.items():
                labels = dict(key)
                results.append(MetricValue(
                    name=self.name,
                    value=value,
                    labels=labels,
                    metric_type='gauge'
                ))
        return results


class Histogram:
    """Prometheus-style Histogram metric with configurable buckets."""
    
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf'))
    
    def __init__(self, name: str, description: str, labels: list = None, 
                 buckets: tuple = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[tuple, Dict[float, int]] = defaultdict(lambda: {b: 0 for b in self.buckets})
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._totals: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def observe(self, value: float, **labels) -> None:
        """Record an observation."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._sums[key] += value
            self._totals[key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1
    
    def time(self, **labels) -> 'HistogramTimer':
        """Context manager for timing code blocks."""
        return HistogramTimer(self, labels)
    
    def collect(self) -> list:
        """Collect all metric values for export."""
        results = []
        with self._lock:
            for key, counts in self._counts.items():
                labels = dict(key)
                # Bucket values
                for bucket, count in counts.items():
                    bucket_labels = {**labels, 'le': str(bucket)}
                    results.append(MetricValue(
                        name=f"{self.name}_bucket",
                        value=count,
                        labels=bucket_labels,
                        metric_type='histogram'
                    ))
                # Sum and count
                results.append(MetricValue(
                    name=f"{self.name}_sum",
                    value=self._sums[key],
                    labels=labels,
                    metric_type='histogram'
                ))
                results.append(MetricValue(
                    name=f"{self.name}_count",
                    value=self._totals[key],
                    labels=labels,
                    metric_type='histogram'
                ))
        return results


class HistogramTimer:
    """Context manager for timing with Histogram."""
    
    def __init__(self, histogram: Histogram, labels: dict):
        self.histogram = histogram
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start_time
        self.histogram.observe(duration, **self.labels)


class Summary:
    """Prometheus-style Summary metric with quantiles."""
    
    def __init__(self, name: str, description: str, labels: list = None,
                 max_age: float = 600.0, window_size: int = 1000):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.max_age = max_age
        self.window_size = window_size
        self._observations: Dict[tuple, list] = defaultdict(list)
        self._lock = threading.Lock()
    
    def observe(self, value: float, **labels) -> None:
        """Record an observation."""
        key = tuple(sorted(labels.items()))
        now = time.time()
        with self._lock:
            # Add observation
            self._observations[key].append((now, value))
            # Clean old observations
            cutoff = now - self.max_age
            self._observations[key] = [
                (t, v) for t, v in self._observations[key][-self.window_size:]
                if t > cutoff
            ]
    
    def _calculate_quantile(self, values: list, q: float) -> float:
        """Calculate a quantile from sorted values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = int(len(sorted_values) * q)
        return sorted_values[min(idx, len(sorted_values) - 1)]
    
    def collect(self) -> list:
        """Collect all metric values for export."""
        results = []
        with self._lock:
            for key, observations in self._observations.items():
                if not observations:
                    continue
                labels = dict(key)
                values = [v for _, v in observations]
                
                # Quantiles
                for q in [0.5, 0.9, 0.99]:
                    q_labels = {**labels, 'quantile': str(q)}
                    results.append(MetricValue(
                        name=self.name,
                        value=self._calculate_quantile(values, q),
                        labels=q_labels,
                        metric_type='summary'
                    ))
                
                # Sum and count
                results.append(MetricValue(
                    name=f"{self.name}_sum",
                    value=sum(values),
                    labels=labels,
                    metric_type='summary'
                ))
                results.append(MetricValue(
                    name=f"{self.name}_count",
                    value=len(values),
                    labels=labels,
                    metric_type='summary'
                ))
        return results


class MetricsRegistry:
    """
    Central registry for all metrics.
    Provides Prometheus-compatible export format.
    """
    
    def __init__(self, namespace: str = 'v2ray_tester'):
        self.namespace = namespace
        self._metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Pre-register common metrics
        self._register_default_metrics()
    
    def _register_default_metrics(self):
        """Register default application metrics."""
        # Test metrics
        self.register(Counter(
            'configs_tested_total',
            'Total number of configs tested',
            labels=['protocol', 'status']
        ))
        self.register(Counter(
            'configs_found_total',
            'Total number of working configs found',
            labels=['protocol', 'country']
        ))
        self.register(Gauge(
            'configs_queue_size',
            'Current size of the config queue'
        ))
        self.register(Gauge(
            'active_workers',
            'Number of active worker tasks'
        ))
        
        # Performance metrics
        self.register(Histogram(
            'test_duration_seconds',
            'Time taken to test a config',
            labels=['protocol'],
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float('inf'))
        ))
        self.register(Histogram(
            'ping_latency_ms',
            'Ping latency in milliseconds',
            labels=['country'],
            buckets=(50, 100, 200, 500, 1000, 2000, 5000, float('inf'))
        ))
        self.register(Summary(
            'download_speed_mbps',
            'Download speed in MB/s',
            labels=['protocol']
        ))
        
        # Network metrics
        self.register(Counter(
            'network_requests_total',
            'Total network requests made',
            labels=['type', 'status']
        ))
        self.register(Counter(
            'rate_limit_events_total',
            'Total rate limit events',
            labels=['type']  # delayed, rejected
        ))
        
        # Error metrics
        self.register(Counter(
            'errors_total',
            'Total errors encountered',
            labels=['type', 'component']
        ))
        
        # Iran Optimizer metrics
        self.register(Counter(
            'fragment_attempts_total',
            'Total fragment injection attempts',
            labels=['status']
        ))
        self.register(Counter(
            'sni_bypass_attempts_total',
            'Total SNI bypass attempts',
            labels=['status']
        ))
        self.register(Gauge(
            'clean_ips_available',
            'Number of clean IPs available'
        ))
    
    def register(self, metric: Any) -> None:
        """Register a metric."""
        full_name = f"{self.namespace}_{metric.name}"
        with self._lock:
            if full_name in self._metrics:
                self.logger.warning(f"Metric {full_name} already registered, overwriting")
            self._metrics[full_name] = metric
    
    def get(self, name: str) -> Optional[Any]:
        """Get a registered metric by name."""
        full_name = f"{self.namespace}_{name}"
        return self._metrics.get(full_name)
    
    def counter(self, name: str) -> Counter:
        """Get a Counter metric."""
        return self.get(name)
    
    def gauge(self, name: str) -> Gauge:
        """Get a Gauge metric."""
        return self.get(name)
    
    def histogram(self, name: str) -> Histogram:
        """Get a Histogram metric."""
        return self.get(name)
    
    def summary(self, name: str) -> Summary:
        """Get a Summary metric."""
        return self.get(name)
    
    def collect_all(self) -> list:
        """Collect all metrics for export."""
        results = []
        with self._lock:
            for name, metric in self._metrics.items():
                try:
                    results.extend(metric.collect())
                except Exception as e:
                    self.logger.error(f"Failed to collect metric {name}: {e}")
        return results
    
    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []
        metrics = self.collect_all()
        
        # Group by metric name
        grouped: Dict[str, list] = defaultdict(list)
        for m in metrics:
            grouped[m.name].append(m)
        
        for name, values in sorted(grouped.items()):
            if not values:
                continue
            
            # TYPE line
            metric_type = values[0].metric_type
            lines.append(f"# TYPE {name} {metric_type}")
            
            # Value lines
            for v in values:
                if v.labels:
                    label_str = ','.join(f'{k}="{v}"' for k, v in sorted(v.labels.items()))
                    lines.append(f"{name}{{{label_str}}} {v.value}")
                else:
                    lines.append(f"{name} {v.value}")
        
        return '\n'.join(lines)
    
    def export_json(self) -> str:
        """Export all metrics in JSON format."""
        metrics = self.collect_all()
        data = [
            {
                'name': m.name,
                'value': m.value,
                'labels': m.labels,
                'timestamp': m.timestamp,
                'type': m.metric_type
            }
            for m in metrics
        ]
        return json.dumps(data, indent=2)


# Global metrics registry
_metrics_registry: Optional[MetricsRegistry] = None

def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


# Convenience decorators for timing
def timed(metric_name: str, **labels):
    """Decorator to time function execution with a Histogram."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            histogram = get_metrics().histogram(metric_name)
            if histogram:
                with histogram.time(**labels):
                    return await func(*args, **kwargs)
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            histogram = get_metrics().histogram(metric_name)
            if histogram:
                with histogram.time(**labels):
                    return func(*args, **kwargs)
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def counted(metric_name: str, **labels):
    """Decorator to count function calls with a Counter."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            counter = get_metrics().counter(metric_name)
            if counter:
                counter.inc(**labels)
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            counter = get_metrics().counter(metric_name)
            if counter:
                counter.inc(**labels)
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
