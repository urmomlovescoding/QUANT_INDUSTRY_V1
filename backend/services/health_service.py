"""
QUANT INDUSTRY - Health Monitoring Service
System health, API status, GPU monitoring, and performance monitoring
"""

import asyncio
import logging
import os
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import psutil

logger = logging.getLogger(__name__)

# ============== GPU/ML DETECTION ==============

# PyTorch/CUDA detection
HAS_TORCH = False
HAS_CUDA = False
HAS_MPS = False  # Apple Silicon
DEVICE = 'cpu'
GPU_NAME = 'N/A'
GPU_MEMORY_TOTAL = 0.0
GPU_COUNT = 0

try:
    import torch
    HAS_TORCH = True
    if torch.cuda.is_available():
        HAS_CUDA = True
        DEVICE = 'cuda'
        GPU_COUNT = torch.cuda.device_count()
        GPU_NAME = torch.cuda.get_device_name(0)
        GPU_MEMORY_TOTAL = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        # Enable cuDNN benchmark for faster training
        torch.backends.cudnn.benchmark = True
        logger.info(f"GPU detected: {GPU_NAME} with {GPU_MEMORY_TOTAL:.1f}GB VRAM")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        HAS_MPS = True
        DEVICE = 'mps'
        GPU_NAME = 'Apple Silicon MPS'
        logger.info("Apple Silicon MPS detected")
    else:
        logger.info("No GPU detected, using CPU")
except ImportError:
    logger.info("PyTorch not available, GPU features disabled")

# TensorFlow detection - LAZY LOADED to avoid slow startup
HAS_TF = None  # None = not checked yet
TF_GPU_AVAILABLE = None

def _check_tensorflow():
    """Lazy check for TensorFlow (slow to import)."""
    global HAS_TF, TF_GPU_AVAILABLE
    if HAS_TF is not None:
        return HAS_TF
    try:
        import tensorflow as tf
        HAS_TF = True
        TF_GPU_AVAILABLE = len(tf.config.list_physical_devices('GPU')) > 0
    except ImportError:
        HAS_TF = False
        TF_GPU_AVAILABLE = False
    return HAS_TF

# ML Libraries detection
HAS_SKLEARN = False
HAS_XGBOOST = False
HAS_LIGHTGBM = False
HAS_STABLE_BASELINES = False

try:
    import sklearn
    HAS_SKLEARN = True
except ImportError:
    pass

try:
    import xgboost
    HAS_XGBOOST = True
except ImportError:
    pass

try:
    import lightgbm
    HAS_LIGHTGBM = True
except ImportError:
    pass

try:
    import stable_baselines3
    HAS_STABLE_BASELINES = True
except ImportError:
    pass


def get_gpu_utilization() -> Dict[str, float]:
    """Get real-time GPU utilization using nvidia-smi"""
    result = {
        'gpu_percent': 0.0,
        'gpu_memory_used': 0.0,
        'gpu_memory_total': GPU_MEMORY_TOTAL,
        'gpu_memory_percent': 0.0,
        'gpu_temp': 0.0,
        'gpu_power': 0.0,
    }

    if HAS_CUDA:
        try:
            import torch
            # Get memory from PyTorch
            result['gpu_memory_used'] = torch.cuda.memory_allocated() / (1024**3)
            result['gpu_memory_percent'] = (result['gpu_memory_used'] / GPU_MEMORY_TOTAL * 100) if GPU_MEMORY_TOTAL > 0 else 0

            # Get utilization from nvidia-smi
            cmd = ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,power.draw', '--format=csv,noheader,nounits']
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                parts = proc.stdout.strip().split(',')
                if len(parts) >= 3:
                    result['gpu_percent'] = float(parts[0].strip())
                    result['gpu_temp'] = float(parts[1].strip())
                    try:
                        result['gpu_power'] = float(parts[2].strip())
                    except (ValueError, IndexError):
                        pass
        except Exception as e:
            logger.debug(f"GPU utilization error: {e}")

    return result


def get_ml_capabilities() -> Dict[str, Any]:
    """Get available ML/DL/RL capabilities"""
    # Lazy check TensorFlow only when this function is called
    tf_available = _check_tensorflow()
    
    return {
        'pytorch': HAS_TORCH,
        'cuda': HAS_CUDA,
        'mps': HAS_MPS,
        'tensorflow': tf_available,
        'tf_gpu': TF_GPU_AVAILABLE if tf_available else False,
        'sklearn': HAS_SKLEARN,
        'xgboost': HAS_XGBOOST,
        'lightgbm': HAS_LIGHTGBM,
        'stable_baselines3': HAS_STABLE_BASELINES,
        'device': DEVICE,
        'gpu_name': GPU_NAME,
        'gpu_count': GPU_COUNT,
        'gpu_memory_gb': round(GPU_MEMORY_TOTAL, 2),
        'cpu_cores': psutil.cpu_count(logical=False),
        'cpu_threads': psutil.cpu_count(logical=True),
    }


class ServiceStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ConnectionStatus(Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    ERROR = "ERROR"


@dataclass
class APIHealth:
    name: str
    status: ConnectionStatus
    latency_ms: float
    last_check: datetime
    error_message: Optional[str] = None
    rate_limit_remaining: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message,
            "rate_limit_remaining": self.rate_limit_remaining,
        }


@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    uptime_seconds: float
    # GPU metrics
    gpu_available: bool = False
    gpu_name: str = "N/A"
    gpu_percent: float = 0.0
    gpu_memory_used_gb: float = 0.0
    gpu_memory_total_gb: float = 0.0
    gpu_memory_percent: float = 0.0
    gpu_temp: float = 0.0
    gpu_power: float = 0.0
    # ML capabilities
    ml_device: str = "cpu"

    def to_dict(self) -> Dict:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_gb": round(self.memory_used_gb, 2),
            "memory_total_gb": round(self.memory_total_gb, 2),
            "disk_percent": self.disk_percent,
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "network_sent_mb": round(self.network_sent_mb, 2),
            "network_recv_mb": round(self.network_recv_mb, 2),
            "process_count": self.process_count,
            "uptime_seconds": round(self.uptime_seconds, 0),
            # GPU
            "gpu_available": self.gpu_available,
            "gpu_name": self.gpu_name,
            "gpu_percent": round(self.gpu_percent, 1),
            "gpu_memory_used_gb": round(self.gpu_memory_used_gb, 2),
            "gpu_memory_total_gb": round(self.gpu_memory_total_gb, 2),
            "gpu_memory_percent": round(self.gpu_memory_percent, 1),
            "gpu_temp": round(self.gpu_temp, 1),
            "gpu_power": round(self.gpu_power, 1),
            "ml_device": self.ml_device,
        }


@dataclass
class ServiceHealth:
    name: str
    status: ServiceStatus
    uptime_seconds: float
    request_count: int
    error_count: int
    avg_response_time_ms: float
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "uptime_seconds": round(self.uptime_seconds, 0),
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "error_rate": round(self.error_count / max(1, self.request_count) * 100, 2),
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


# ============== MEMORY MONITORING ==============

@dataclass
class MemoryAlert:
    """Alert for memory usage issues."""
    timestamp: datetime
    alert_type: str  # 'warning', 'critical', 'leak_detected'
    message: str
    memory_used_gb: float
    memory_percent: float
    process_rss_mb: float
    threshold_percent: float


class MemoryMonitor:
    """
    Detailed memory monitoring with process-level tracking.
    Matches quant-platform pattern for resource monitoring.
    """

    def __init__(
        self,
        warning_threshold: float = 75.0,
        critical_threshold: float = 90.0,
        leak_detection_window: int = 60
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.leak_detection_window = leak_detection_window  # samples

        # Historical data for trend analysis
        self._memory_history: List[Dict] = []
        self._max_history = 1000
        self._alerts: List[MemoryAlert] = []
        self._max_alerts = 100
        self._lock = threading.Lock()

        # Process tracking
        self._process = psutil.Process()

    def record_sample(self) -> Dict[str, Any]:
        """Record a memory usage sample."""
        mem = psutil.virtual_memory()
        proc = self._process.memory_info()

        sample = {
            'timestamp': datetime.now(),
            'system_percent': mem.percent,
            'system_used_gb': mem.used / (1024 ** 3),
            'system_total_gb': mem.total / (1024 ** 3),
            'system_available_gb': mem.available / (1024 ** 3),
            'process_rss_mb': proc.rss / (1024 ** 2),
            'process_vms_mb': proc.vms / (1024 ** 2),
        }

        # Add swap info if available
        try:
            swap = psutil.swap_memory()
            sample['swap_percent'] = swap.percent
            sample['swap_used_gb'] = swap.used / (1024 ** 3)
        except Exception:
            sample['swap_percent'] = 0
            sample['swap_used_gb'] = 0

        with self._lock:
            self._memory_history.append(sample)
            if len(self._memory_history) > self._max_history:
                self._memory_history.pop(0)

        # Check for alerts
        self._check_alerts(sample)

        return sample

    def _check_alerts(self, sample: Dict):
        """Check for memory-related alerts."""
        # Critical threshold
        if sample['system_percent'] >= self.critical_threshold:
            self._add_alert(MemoryAlert(
                timestamp=sample['timestamp'],
                alert_type='critical',
                message=f"CRITICAL: System memory at {sample['system_percent']:.1f}%",
                memory_used_gb=sample['system_used_gb'],
                memory_percent=sample['system_percent'],
                process_rss_mb=sample['process_rss_mb'],
                threshold_percent=self.critical_threshold
            ))
        elif sample['system_percent'] >= self.warning_threshold:
            self._add_alert(MemoryAlert(
                timestamp=sample['timestamp'],
                alert_type='warning',
                message=f"Warning: System memory at {sample['system_percent']:.1f}%",
                memory_used_gb=sample['system_used_gb'],
                memory_percent=sample['system_percent'],
                process_rss_mb=sample['process_rss_mb'],
                threshold_percent=self.warning_threshold
            ))

        # Memory leak detection
        with self._lock:
            if len(self._memory_history) >= self.leak_detection_window:
                self._check_memory_leak()

    def _check_memory_leak(self):
        """Detect potential memory leaks using trend analysis."""
        recent = self._memory_history[-self.leak_detection_window:]
        rss_values = [s['process_rss_mb'] for s in recent]

        if len(rss_values) < 10:
            return

        # Calculate trend (simple linear regression slope)
        n = len(rss_values)
        x_mean = (n - 1) / 2
        y_mean = sum(rss_values) / n

        numerator = sum((i - x_mean) * (rss_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return

        slope = numerator / denominator  # MB per sample

        # If memory is consistently increasing > 1MB per sample, flag as potential leak
        if slope > 1.0:
            growth_per_hour = slope * (3600 / 60)  # Assuming 1 sample/minute
            self._add_alert(MemoryAlert(
                timestamp=datetime.now(),
                alert_type='leak_detected',
                message=f"Potential memory leak: Process growing ~{growth_per_hour:.1f}MB/hour",
                memory_used_gb=recent[-1]['system_used_gb'],
                memory_percent=recent[-1]['system_percent'],
                process_rss_mb=recent[-1]['process_rss_mb'],
                threshold_percent=self.warning_threshold
            ))

    def _add_alert(self, alert: MemoryAlert):
        """Add an alert to the history."""
        with self._lock:
            # Avoid duplicate alerts within 5 minutes
            recent_same = [a for a in self._alerts[-10:]
                          if a.alert_type == alert.alert_type
                          and (alert.timestamp - a.timestamp).total_seconds() < 300]
            if not recent_same:
                self._alerts.append(alert)
                if len(self._alerts) > self._max_alerts:
                    self._alerts.pop(0)
                logger.warning(f"[MEMORY] {alert.message}")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current memory status."""
        sample = self.record_sample()

        with self._lock:
            recent_alerts = [
                {
                    'timestamp': a.timestamp.isoformat(),
                    'type': a.alert_type,
                    'message': a.message,
                    'memory_percent': a.memory_percent
                }
                for a in self._alerts[-10:]
            ]

        # Determine health status
        status = 'healthy'
        if sample['system_percent'] >= self.critical_threshold:
            status = 'critical'
        elif sample['system_percent'] >= self.warning_threshold:
            status = 'warning'

        return {
            'status': status,
            'system': {
                'percent': round(sample['system_percent'], 1),
                'used_gb': round(sample['system_used_gb'], 2),
                'total_gb': round(sample['system_total_gb'], 2),
                'available_gb': round(sample['system_available_gb'], 2)
            },
            'process': {
                'rss_mb': round(sample['process_rss_mb'], 2),
                'vms_mb': round(sample['process_vms_mb'], 2)
            },
            'swap': {
                'percent': round(sample['swap_percent'], 1),
                'used_gb': round(sample['swap_used_gb'], 2)
            },
            'alerts': recent_alerts,
            'thresholds': {
                'warning': self.warning_threshold,
                'critical': self.critical_threshold
            }
        }

    def get_memory_trend(self, samples: int = 60) -> Dict[str, Any]:
        """Get memory usage trend over time."""
        with self._lock:
            history = self._memory_history[-samples:]

        if not history:
            return {'samples': 0, 'trend': 'unknown'}

        system_pcts = [s['system_percent'] for s in history]
        process_rss = [s['process_rss_mb'] for s in history]

        # Calculate trends
        if len(system_pcts) > 1:
            system_change = system_pcts[-1] - system_pcts[0]
            process_change = process_rss[-1] - process_rss[0]
        else:
            system_change = 0
            process_change = 0

        trend = 'stable'
        if system_change > 5:
            trend = 'increasing'
        elif system_change < -5:
            trend = 'decreasing'

        return {
            'samples': len(history),
            'trend': trend,
            'system_change_pct': round(system_change, 1),
            'process_change_mb': round(process_change, 1),
            'avg_system_percent': round(sum(system_pcts) / len(system_pcts), 1),
            'max_system_percent': round(max(system_pcts), 1),
            'avg_process_rss_mb': round(sum(process_rss) / len(process_rss), 1),
            'max_process_rss_mb': round(max(process_rss), 1)
        }


# Global memory monitor instance
_memory_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get global memory monitor instance."""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


class HealthService:
    """
    Health monitoring service for system and API status
    """

    def __init__(self, db_path: str = None):
        self.start_time = datetime.now()
        self.api_health: Dict[str, APIHealth] = {}
        self.service_stats: Dict[str, Dict] = {}
        self.lock = threading.Lock()

        # Initialize service stats
        self._init_service_stats()

        # Database
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "health.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        # API endpoints to monitor
        self.api_endpoints = {
            "alpaca": {
                "url": "https://api.alpaca.markets/v2/account",
                "auth_required": True,
            },
            "yahoo": {
                "url": "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
                "auth_required": False,
            },
            "finnhub": {
                "url": "https://finnhub.io/api/v1/quote?symbol=AAPL",
                "auth_required": True,
            },
            "polygon": {
                "url": "https://api.polygon.io/v2/aggs/ticker/AAPL/prev",
                "auth_required": True,
            },
        }

        logger.info("HealthService initialized")

    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                api_status TEXT,
                overall_status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_latency (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                api_name TEXT NOT NULL,
                latency_ms REAL,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                service_name TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT,
                stack_trace TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _init_service_stats(self):
        """Initialize service statistics"""
        services = [
            "data_service", "trading_service", "risk_service",
            "options_service", "backtest_service", "brain_service",
            "research_service", "portfolio_service"
        ]

        for service in services:
            self.service_stats[service] = {
                "request_count": 0,
                "error_count": 0,
                "total_response_time": 0,
                "last_error": None,
                "last_error_time": None,
            }

    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics including GPU"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            uptime = (datetime.now() - self.start_time).total_seconds()

            # Get GPU metrics
            gpu_info = get_gpu_utilization()

            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=memory.used / (1024 ** 3),
                memory_total_gb=memory.total / (1024 ** 3),
                disk_percent=disk.percent,
                disk_used_gb=disk.used / (1024 ** 3),
                disk_total_gb=disk.total / (1024 ** 3),
                network_sent_mb=network.bytes_sent / (1024 ** 2),
                network_recv_mb=network.bytes_recv / (1024 ** 2),
                process_count=len(psutil.pids()),
                uptime_seconds=uptime,
                # GPU
                gpu_available=HAS_CUDA or HAS_MPS,
                gpu_name=GPU_NAME,
                gpu_percent=gpu_info['gpu_percent'],
                gpu_memory_used_gb=gpu_info['gpu_memory_used'],
                gpu_memory_total_gb=gpu_info['gpu_memory_total'],
                gpu_memory_percent=gpu_info['gpu_memory_percent'],
                gpu_temp=gpu_info['gpu_temp'],
                gpu_power=gpu_info['gpu_power'],
                ml_device=DEVICE,
            )
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0, memory_percent=0, memory_used_gb=0,
                memory_total_gb=0, disk_percent=0, disk_used_gb=0,
                disk_total_gb=0, network_sent_mb=0, network_recv_mb=0,
                process_count=0, uptime_seconds=0
            )

    async def check_api_health(self, api_name: str) -> APIHealth:
        """Check health of a specific API"""
        if api_name not in self.api_endpoints:
            return APIHealth(
                name=api_name,
                status=ConnectionStatus.UNKNOWN,
                latency_ms=0,
                last_check=datetime.now(),
                error_message="Unknown API"
            )

        endpoint = self.api_endpoints[api_name]
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {}

                # Add auth headers based on API
                if endpoint["auth_required"]:
                    if api_name == "alpaca":
                        api_key = os.environ.get("ALPACA_API_KEY", "")
                        api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
                        headers["APCA-API-KEY-ID"] = api_key
                        headers["APCA-API-SECRET-KEY"] = api_secret
                    elif api_name == "finnhub":
                        api_key = os.environ.get("FINNHUB_API_KEY", "")
                        endpoint["url"] = f"{endpoint['url']}&token={api_key}"
                    elif api_name == "polygon":
                        api_key = os.environ.get("POLYGON_API_KEY", "")
                        endpoint["url"] = f"{endpoint['url']}?apiKey={api_key}"

                async with session.get(
                    endpoint["url"],
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    latency = (time.time() - start_time) * 1000

                    if response.status == 200:
                        status = ConnectionStatus.CONNECTED
                        error_msg = None
                    elif response.status == 401:
                        status = ConnectionStatus.ERROR
                        error_msg = "Authentication failed"
                    elif response.status == 429:
                        status = ConnectionStatus.DEGRADED
                        error_msg = "Rate limited"
                    else:
                        status = ConnectionStatus.ERROR
                        error_msg = f"HTTP {response.status}"

                    health = APIHealth(
                        name=api_name,
                        status=status,
                        latency_ms=latency,
                        last_check=datetime.now(),
                        error_message=error_msg
                    )

        except asyncio.TimeoutError:
            health = APIHealth(
                name=api_name,
                status=ConnectionStatus.ERROR,
                latency_ms=10000,
                last_check=datetime.now(),
                error_message="Connection timeout"
            )
        except Exception as e:
            health = APIHealth(
                name=api_name,
                status=ConnectionStatus.ERROR,
                latency_ms=0,
                last_check=datetime.now(),
                error_message=str(e)
            )

        with self.lock:
            self.api_health[api_name] = health

        self._save_api_latency(health)
        return health

    async def check_all_apis(self) -> Dict[str, APIHealth]:
        """Check health of all APIs"""
        tasks = [
            self.check_api_health(api_name)
            for api_name in self.api_endpoints
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        health_dict = {}
        for i, api_name in enumerate(self.api_endpoints):
            if isinstance(results[i], Exception):
                health_dict[api_name] = APIHealth(
                    name=api_name,
                    status=ConnectionStatus.ERROR,
                    latency_ms=0,
                    last_check=datetime.now(),
                    error_message=str(results[i])
                )
            else:
                health_dict[api_name] = results[i]

        return health_dict

    def get_service_health(self, service_name: str) -> ServiceHealth:
        """Get health status of a service"""
        with self.lock:
            stats = self.service_stats.get(service_name, {})

        request_count = stats.get("request_count", 0)
        error_count = stats.get("error_count", 0)
        total_time = stats.get("total_response_time", 0)

        avg_response_time = total_time / max(1, request_count)
        error_rate = error_count / max(1, request_count)

        # Determine status
        if error_rate > 0.1:
            status = ServiceStatus.UNHEALTHY
        elif error_rate > 0.01 or avg_response_time > 1000:
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.HEALTHY

        uptime = (datetime.now() - self.start_time).total_seconds()

        return ServiceHealth(
            name=service_name,
            status=status,
            uptime_seconds=uptime,
            request_count=request_count,
            error_count=error_count,
            avg_response_time_ms=avg_response_time,
            last_error=stats.get("last_error"),
            last_error_time=stats.get("last_error_time"),
        )

    def get_all_services_health(self) -> List[ServiceHealth]:
        """Get health of all services"""
        return [
            self.get_service_health(name)
            for name in self.service_stats
        ]

    def record_request(self, service_name: str, response_time_ms: float, error: str = None):
        """Record a service request"""
        with self.lock:
            if service_name not in self.service_stats:
                self.service_stats[service_name] = {
                    "request_count": 0,
                    "error_count": 0,
                    "total_response_time": 0,
                    "last_error": None,
                    "last_error_time": None,
                }

            stats = self.service_stats[service_name]
            stats["request_count"] += 1
            stats["total_response_time"] += response_time_ms

            if error:
                stats["error_count"] += 1
                stats["last_error"] = error
                stats["last_error_time"] = datetime.now()
                self._save_error(service_name, error)

    def get_overall_status(self) -> Dict:
        """Get overall system health status"""
        system = self.get_system_metrics()
        services = self.get_all_services_health()

        # Determine overall status
        unhealthy_count = sum(1 for s in services if s.status == ServiceStatus.UNHEALTHY)
        degraded_count = sum(1 for s in services if s.status == ServiceStatus.DEGRADED)

        if unhealthy_count > 0 or system.cpu_percent > 90 or system.memory_percent > 95:
            overall = ServiceStatus.UNHEALTHY
        elif degraded_count > 0 or system.cpu_percent > 75 or system.memory_percent > 85:
            overall = ServiceStatus.DEGRADED
        else:
            overall = ServiceStatus.HEALTHY

        # Count API statuses
        api_connected = sum(
            1 for h in self.api_health.values()
            if h.status == ConnectionStatus.CONNECTED
        )

        return {
            "status": overall.value,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "system": system.to_dict(),
            "services": {
                "total": len(services),
                "healthy": sum(1 for s in services if s.status == ServiceStatus.HEALTHY),
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
            },
            "apis": {
                "total": len(self.api_endpoints),
                "connected": api_connected,
                "disconnected": len(self.api_endpoints) - api_connected,
            },
        }

    def get_detailed_status(self) -> Dict:
        """Get detailed health status"""
        return {
            "overall": self.get_overall_status(),
            "system": self.get_system_metrics().to_dict(),
            "services": [s.to_dict() for s in self.get_all_services_health()],
            "apis": {name: h.to_dict() for name, h in self.api_health.items()},
        }

    def _save_api_latency(self, health: APIHealth):
        """Save API latency to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_latency (timestamp, api_name, latency_ms, status)
                VALUES (?, ?, ?, ?)
            """, (
                health.last_check.isoformat(),
                health.name,
                health.latency_ms,
                health.status.value
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving API latency: {e}")

    def _save_error(self, service_name: str, error_message: str):
        """Save service error to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO service_errors (timestamp, service_name, error_type, error_message)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                service_name,
                "ERROR",
                error_message
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving service error: {e}")

    def save_snapshot(self):
        """Save current health snapshot to database"""
        try:
            system = self.get_system_metrics()
            overall = self.get_overall_status()

            api_status = ",".join([
                f"{name}:{h.status.value}"
                for name, h in self.api_health.items()
            ])

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO health_snapshots
                (timestamp, cpu_percent, memory_percent, disk_percent, api_status, overall_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                system.cpu_percent,
                system.memory_percent,
                system.disk_percent,
                api_status,
                overall["status"]
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving health snapshot: {e}")

    def get_health_history(self, hours: int = 24) -> List[Dict]:
        """Get health history for the past N hours"""
        try:
            since = (datetime.now() - timedelta(hours=hours)).isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, cpu_percent, memory_percent, disk_percent, overall_status
                FROM health_snapshots
                WHERE timestamp > ?
                ORDER BY timestamp
            """, (since,))

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "timestamp": row[0],
                    "cpu_percent": row[1],
                    "memory_percent": row[2],
                    "disk_percent": row[3],
                    "status": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting health history: {e}")
            return []


# Singleton instance
_health_service: Optional[HealthService] = None

def get_health_service() -> HealthService:
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


# ============== COMPONENT MONITORING ==============

class ComponentStatus(Enum):
    """Component health status"""
    HEALTHY = "healthy"
    STARTING = "starting"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health information for a system component"""
    name: str
    status: ComponentStatus
    last_heartbeat: datetime
    uptime_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "metadata": self.metadata,
            "dependencies": self.dependencies,
            "error": self.error,
            "is_healthy": self.status in (ComponentStatus.HEALTHY, ComponentStatus.STARTING)
        }


class ComponentMonitor:
    """
    Centralized component health monitoring.
    Matches quant-platform pattern for microservice health tracking.

    Features:
    - Component registration with dependencies
    - Heartbeat tracking with configurable timeouts
    - Dependency health propagation
    - Health check callbacks

    Example:
        monitor = ComponentMonitor()
        monitor.register("brain", dependencies=["data_service", "risk_service"])
        monitor.heartbeat("brain", metadata={"signals_generated": 100})

        status = monitor.get_status("brain")
    """

    def __init__(
        self,
        heartbeat_timeout: float = 60.0,
        check_interval: float = 10.0
    ):
        """
        Initialize component monitor.

        Args:
            heartbeat_timeout: Seconds without heartbeat before component is unhealthy
            check_interval: Seconds between health check cycles
        """
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval

        self._components: Dict[str, ComponentHealth] = {}
        self._start_times: Dict[str, datetime] = {}
        self._health_checks: Dict[str, List[Callable[[], bool]]] = {}
        self._lock = threading.Lock()

        self._running = False
        self._check_thread: Optional[threading.Thread] = None

    def register(
        self,
        name: str,
        dependencies: List[str] = None,
        health_check: Callable[[], bool] = None
    ) -> None:
        """
        Register a component for monitoring.

        Args:
            name: Unique component name
            dependencies: List of component names this depends on
            health_check: Optional callback that returns True if healthy
        """
        with self._lock:
            now = datetime.now()
            self._start_times[name] = now

            self._components[name] = ComponentHealth(
                name=name,
                status=ComponentStatus.STARTING,
                last_heartbeat=now,
                uptime_seconds=0,
                dependencies=dependencies or [],
            )

            if health_check:
                if name not in self._health_checks:
                    self._health_checks[name] = []
                self._health_checks[name].append(health_check)

        logger.info(f"Component registered: {name}")

    def unregister(self, name: str) -> None:
        """Unregister a component"""
        with self._lock:
            self._components.pop(name, None)
            self._start_times.pop(name, None)
            self._health_checks.pop(name, None)

        logger.info(f"Component unregistered: {name}")

    def heartbeat(
        self,
        name: str,
        status: ComponentStatus = None,
        metadata: Dict[str, Any] = None,
        error: str = None
    ) -> None:
        """
        Send a heartbeat for a component.

        Args:
            name: Component name
            status: Optional status override
            metadata: Optional metadata to update
            error: Optional error message
        """
        with self._lock:
            if name not in self._components:
                # Auto-register if not registered
                self._start_times[name] = datetime.now()
                self._components[name] = ComponentHealth(
                    name=name,
                    status=ComponentStatus.STARTING,
                    last_heartbeat=datetime.now(),
                    uptime_seconds=0,
                )

            component = self._components[name]
            now = datetime.now()

            component.last_heartbeat = now
            component.uptime_seconds = (now - self._start_times[name]).total_seconds()

            if status is not None:
                component.status = status
            elif component.status == ComponentStatus.STARTING:
                component.status = ComponentStatus.HEALTHY

            if metadata:
                component.metadata.update(metadata)

            component.error = error
            if error:
                component.status = ComponentStatus.DEGRADED

    def get_status(self, name: str) -> Optional[ComponentHealth]:
        """Get health status of a component"""
        with self._lock:
            component = self._components.get(name)
            if component is None:
                return None

            # Check for stale heartbeat
            now = datetime.now()
            seconds_since_heartbeat = (now - component.last_heartbeat).total_seconds()

            if seconds_since_heartbeat > self.heartbeat_timeout:
                if component.status != ComponentStatus.STOPPED:
                    component.status = ComponentStatus.UNHEALTHY
                    component.error = f"No heartbeat for {seconds_since_heartbeat:.1f}s"

            # Check dependencies
            if component.status == ComponentStatus.HEALTHY:
                for dep_name in component.dependencies:
                    dep = self._components.get(dep_name)
                    if dep and dep.status not in (ComponentStatus.HEALTHY, ComponentStatus.STARTING):
                        component.status = ComponentStatus.DEGRADED
                        component.error = f"Dependency {dep_name} is {dep.status.value}"
                        break

            return component

    def get_all_status(self) -> Dict[str, ComponentHealth]:
        """Get health status of all components"""
        return {
            name: self.get_status(name)
            for name in self._components
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        all_status = self.get_all_status()

        healthy = sum(1 for c in all_status.values() if c and c.status == ComponentStatus.HEALTHY)
        degraded = sum(1 for c in all_status.values() if c and c.status == ComponentStatus.DEGRADED)
        unhealthy = sum(1 for c in all_status.values() if c and c.status == ComponentStatus.UNHEALTHY)
        total = len(all_status)

        if unhealthy > 0:
            overall = "unhealthy"
        elif degraded > 0:
            overall = "degraded"
        elif healthy == total:
            overall = "healthy"
        else:
            overall = "partial"

        return {
            "overall_status": overall,
            "total_components": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "components": {
                name: c.to_dict() if c else {"status": "unknown"}
                for name, c in all_status.items()
            }
        }

    def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks"""
        results = {}

        for name, checks in self._health_checks.items():
            try:
                # All checks must pass
                all_passed = all(check() for check in checks)
                results[name] = all_passed

                if not all_passed:
                    self.heartbeat(name, status=ComponentStatus.UNHEALTHY, error="Health check failed")
            except Exception as e:
                results[name] = False
                self.heartbeat(name, status=ComponentStatus.UNHEALTHY, error=str(e))

        return results

    def start_monitoring(self) -> None:
        """Start the background monitoring thread"""
        if self._running:
            return

        self._running = True
        self._check_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._check_thread.start()
        logger.info("Component monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread"""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5.0)
        logger.info("Component monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Background monitoring loop"""
        while self._running:
            try:
                # Check for stale components
                self.get_all_status()

                # Run health checks
                self.run_health_checks()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            time.sleep(self.check_interval)

    def mark_stopped(self, name: str) -> None:
        """Mark a component as intentionally stopped"""
        with self._lock:
            if name in self._components:
                self._components[name].status = ComponentStatus.STOPPED
                self._components[name].error = None


# Global component monitor instance
_component_monitor: Optional[ComponentMonitor] = None


def get_component_monitor() -> ComponentMonitor:
    """Get or create the global component monitor"""
    global _component_monitor

    if _component_monitor is None:
        _component_monitor = ComponentMonitor()

    return _component_monitor
