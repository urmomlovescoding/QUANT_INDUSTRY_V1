"""
Deprecation Middleware for QUANT INDUSTRY V1 -> V2 Migration
============================================================
Handles API deprecation headers, metrics tracking, and optional redirects.

Features:
- Adds RFC 8594 compliant deprecation headers
- Tracks deprecated endpoint usage for monitoring
- Optional 307 redirect capability for soft migration
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Deprecation Mapping - Old endpoints -> New v2 endpoints
# =============================================================================

DEPRECATION_MAP: Dict[str, Dict[str, str]] = {
    # -------------------------------------------------------------------------
    # Market Data (15 -> 8)
    # -------------------------------------------------------------------------
    "/api/market/status": {
        "successor": "/api/v2/market/status",
        "sunset": "2025-04-01",
    },
    "/api/market/tickers": {
        "successor": "/api/v2/market/quotes",
        "sunset": "2025-04-01",
    },
    "/api/market/quote/{symbol}": {
        "successor": "/api/v2/market/quotes/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/market/bars/{symbol}": {
        "successor": "/api/v2/market/bars/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/market/snapshot/{symbol}": {
        "successor": "/api/v2/market/snapshot/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/market/sectors": {
        "successor": "/api/v2/market/sectors",
        "sunset": "2025-04-01",
    },
    "/api/market/movers": {
        "successor": "/api/v2/market/movers",
        "sunset": "2025-04-01",
    },
    "/api/charts/ohlcv/{symbol}": {
        "successor": "/api/v2/market/bars/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/charts/indicators/{symbol}": {
        "successor": "/api/v2/market/indicators/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/live/quote/{symbol}": {
        "successor": "/api/v2/market/quotes/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/live/historical/{symbol}": {
        "successor": "/api/v2/market/bars/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/quotes": {
        "successor": "/api/v2/market/quotes",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # Trading/Signals (42 -> 15)
    # -------------------------------------------------------------------------
    "/api/signals": {
        "successor": "/api/v2/trading/signals",
        "sunset": "2025-04-01",
    },
    "/api/signals/active": {
        "successor": "/api/v2/trading/signals?status=active",
        "sunset": "2025-04-01",
    },
    "/api/signals/{id}/execute": {
        "successor": "/api/v2/trading/signals/{id}/execute",
        "sunset": "2025-04-01",
    },
    "/api/signals/{id}/dismiss": {
        "successor": "/api/v2/trading/signals/{id}/dismiss",
        "sunset": "2025-04-01",
    },
    "/api/brain-v6/signals": {
        "successor": "/api/v2/brain/signals",
        "sunset": "2025-04-01",
    },
    "/api/brain-v6/generate-signal": {
        "successor": "/api/v2/brain/signals/generate",
        "sunset": "2025-04-01",
    },
    "/api/orders": {
        "successor": "/api/v2/trading/orders",
        "sunset": "2025-04-01",
    },
    "/api/orders/{id}": {
        "successor": "/api/v2/trading/orders/{id}",
        "sunset": "2025-04-01",
    },
    "/api/positions": {
        "successor": "/api/v2/trading/positions",
        "sunset": "2025-04-01",
    },
    "/api/portfolio/positions": {
        "successor": "/api/v2/trading/positions",
        "sunset": "2025-04-01",
    },
    "/api/portfolio/position/{symbol}": {
        "successor": "/api/v2/trading/positions/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/portfolio/trade": {
        "successor": "/api/v2/trading/orders",
        "sunset": "2025-04-01",
    },
    "/api/broker/status": {
        "successor": "/api/v2/trading/broker/status",
        "sunset": "2025-04-01",
    },
    "/api/broker/account": {
        "successor": "/api/v2/trading/broker/account",
        "sunset": "2025-04-01",
    },
    "/api/broker/positions": {
        "successor": "/api/v2/trading/positions",
        "sunset": "2025-04-01",
    },
    "/api/broker/order": {
        "successor": "/api/v2/trading/orders",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # Brain/ML (103 -> 25)
    # -------------------------------------------------------------------------
    "/brain/status": {
        "successor": "/api/v2/brain/status",
        "sunset": "2025-04-01",
    },
    "/brain/initialize": {
        "successor": "/api/v2/brain/initialize",
        "sunset": "2025-04-01",
    },
    "/brain/signal/{symbol}": {
        "successor": "/api/v2/brain/signals",
        "sunset": "2025-04-01",
    },
    "/api/brain-v6/status": {
        "successor": "/api/v2/brain/status",
        "sunset": "2025-04-01",
    },
    "/api/brain-v6/config": {
        "successor": "/api/v2/brain/config",
        "sunset": "2025-04-01",
    },
    "/api/brain-v6/train": {
        "successor": "/api/v2/brain/train",
        "sunset": "2025-04-01",
    },
    "/api/beast/status": {
        "successor": "/api/v2/brain/models/beast/status",
        "sunset": "2025-04-01",
    },
    "/api/beast/train/{symbol}": {
        "successor": "/api/v2/brain/models/beast/train",
        "sunset": "2025-04-01",
    },
    "/api/beast/predict/{symbol}": {
        "successor": "/api/v2/brain/models/beast/predict",
        "sunset": "2025-04-01",
    },
    "/api/rl/status": {
        "successor": "/api/v2/brain/models/rl/status",
        "sunset": "2025-04-01",
    },
    "/api/rl/train/{symbol}": {
        "successor": "/api/v2/brain/models/rl/train",
        "sunset": "2025-04-01",
    },
    "/api/rl/action/{symbol}": {
        "successor": "/api/v2/brain/models/rl/predict",
        "sunset": "2025-04-01",
    },
    "/api/dl/status": {
        "successor": "/api/v2/brain/models/dl/status",
        "sunset": "2025-04-01",
    },
    "/api/dl/train/{symbol}": {
        "successor": "/api/v2/brain/models/dl/train",
        "sunset": "2025-04-01",
    },
    "/api/dl/predict/{symbol}": {
        "successor": "/api/v2/brain/models/dl/predict",
        "sunset": "2025-04-01",
    },
    "/api/evolution/status": {
        "successor": "/api/v2/brain/models/evolution/status",
        "sunset": "2025-04-01",
    },
    "/api/evolution/evolve/{symbol}": {
        "successor": "/api/v2/brain/models/evolution/train",
        "sunset": "2025-04-01",
    },
    "/api/evolution/best": {
        "successor": "/api/v2/brain/models/evolution/predict",
        "sunset": "2025-04-01",
    },
    "/api/neural/analysis/{symbol}": {
        "successor": "/api/v2/brain/analyze/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/neural/predictions/{symbol}": {
        "successor": "/api/v2/brain/predict/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/neural/regime": {
        "successor": "/api/v2/brain/regime",
        "sunset": "2025-04-01",
    },
    "/api/ml/predict/{symbol}": {
        "successor": "/api/v2/brain/predict/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/ml/regime": {
        "successor": "/api/v2/brain/regime",
        "sunset": "2025-04-01",
    },
    "/api/regime/status": {
        "successor": "/api/v2/brain/regime",
        "sunset": "2025-04-01",
    },
    "/api/regime/detect/{symbol}": {
        "successor": "/api/v2/brain/regime",
        "sunset": "2025-04-01",
    },
    "/api/regime/history/{symbol}": {
        "successor": "/api/v2/brain/regime/history",
        "sunset": "2025-04-01",
    },
    "/api/feedback/status": {
        "successor": "/api/v2/brain/feedback/status",
        "sunset": "2025-04-01",
    },
    "/api/feedback/metrics": {
        "successor": "/api/v2/brain/feedback/metrics",
        "sunset": "2025-04-01",
    },
    "/api/feedback/record": {
        "successor": "/api/v2/brain/feedback/record",
        "sunset": "2025-04-01",
    },
    "/api/agents/status": {
        "successor": "/api/v2/brain/agents/status",
        "sunset": "2025-04-01",
    },
    "/api/agents/consensus": {
        "successor": "/api/v2/brain/agents/consensus",
        "sunset": "2025-04-01",
    },
    "/api/agents/portfolio": {
        "successor": "/api/v2/brain/agents/consensus",
        "sunset": "2025-04-01",
    },
    "/api/memory/status": {
        "successor": "/api/v2/brain/memory/status",
        "sunset": "2025-04-01",
    },
    "/api/memory/store": {
        "successor": "/api/v2/brain/memory/store",
        "sunset": "2025-04-01",
    },
    "/api/memory/search": {
        "successor": "/api/v2/brain/memory/search",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # Risk Management (18 -> 10)
    # -------------------------------------------------------------------------
    "/api/risk/metrics": {
        "successor": "/api/v2/risk/summary",
        "sunset": "2025-04-01",
    },
    "/api/risk/safety": {
        "successor": "/api/v2/risk/summary",
        "sunset": "2025-04-01",
    },
    "/api/risk/limits": {
        "successor": "/api/v2/risk/summary",
        "sunset": "2025-04-01",
    },
    "/api/risk/exposure": {
        "successor": "/api/v2/risk/exposure",
        "sunset": "2025-04-01",
    },
    "/api/risk/sector-exposure": {
        "successor": "/api/v2/risk/exposure",
        "sunset": "2025-04-01",
    },
    "/api/risk/correlation": {
        "successor": "/api/v2/risk/correlation",
        "sunset": "2025-04-01",
    },
    "/api/risk/correlation/{symbol}": {
        "successor": "/api/v2/risk/correlation?symbol={symbol}",
        "sunset": "2025-04-01",
    },
    "/api/risk/report": {
        "successor": "/api/v2/risk/summary",
        "sunset": "2025-04-01",
    },
    "/api/risk/var": {
        "successor": "/api/v2/risk/var",
        "sunset": "2025-04-01",
    },
    "/api/risk/summary": {
        "successor": "/api/v2/risk/summary",
        "sunset": "2025-04-01",
    },
    "/api/risk/alerts": {
        "successor": "/api/v2/risk/alerts",
        "sunset": "2025-04-01",
    },
    "/api/risk/check-trade": {
        "successor": "/api/v2/risk/check",
        "sunset": "2025-04-01",
    },
    "/api/risk/alerts/{key}/acknowledge": {
        "successor": "/api/v2/risk/alerts/{id}/ack",
        "sunset": "2025-04-01",
    },
    "/api/risk/montecarlo/simulate": {
        "successor": "/api/v2/risk/montecarlo",
        "sunset": "2025-04-01",
    },
    "/api/correlation/matrix": {
        "successor": "/api/v2/risk/correlation",
        "sunset": "2025-04-01",
    },
    "/api/kill-switch": {
        "successor": "/api/v2/risk/kill-switch",
        "sunset": "2025-04-01",
    },
    "/api/kill-switch/activate": {
        "successor": "/api/v2/risk/kill-switch/activate",
        "sunset": "2025-04-01",
    },
    "/api/kill-switch/deactivate": {
        "successor": "/api/v2/risk/kill-switch/release",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # System/Settings (44 -> 15)
    # -------------------------------------------------------------------------
    "/api/system/status": {
        "successor": "/api/v2/system/status",
        "sunset": "2025-04-01",
    },
    "/api/system/health": {
        "successor": "/api/v2/health/detailed",
        "sunset": "2025-04-01",
    },
    "/api/system/memory": {
        "successor": "/api/v2/system/status",
        "sunset": "2025-04-01",
    },
    "/api/system/resources": {
        "successor": "/api/v2/system/status",
        "sunset": "2025-04-01",
    },
    "/api/system/ml-capabilities": {
        "successor": "/api/v2/system/modules",
        "sunset": "2025-04-01",
    },
    "/api/system/clear-cache": {
        "successor": "/api/v2/system/cache/clear",
        "sunset": "2025-04-01",
    },
    "/api/data-mode": {
        "successor": "/api/v2/system/data-mode",
        "sunset": "2025-04-01",
    },
    "/api/data-integrity/status": {
        "successor": "/api/v2/system/data-quality",
        "sunset": "2025-04-01",
    },
    "/api/data-integrity/price/{symbol}": {
        "successor": "/api/v2/system/data-quality",
        "sunset": "2025-04-01",
    },
    "/api/data/staleness": {
        "successor": "/api/v2/system/data-quality",
        "sunset": "2025-04-01",
    },
    "/api/data/staleness/{symbol}": {
        "successor": "/api/v2/system/data-quality",
        "sunset": "2025-04-01",
    },
    "/api/settings": {
        "successor": "/api/v2/settings",
        "sunset": "2025-04-01",
    },
    "/api/settings/presets": {
        "successor": "/api/v2/settings/presets",
        "sunset": "2025-04-01",
    },
    "/api/settings/preset/{name}": {
        "successor": "/api/v2/settings/presets/{name}",
        "sunset": "2025-04-01",
    },
    "/api/settings/api-keys": {
        "successor": "/api/v2/settings/api-keys",
        "sunset": "2025-04-01",
    },
    "/api/settings/api-keys/{provider}": {
        "successor": "/api/v2/settings/api-keys/{provider}",
        "sunset": "2025-04-01",
    },
    "/api/settings/api-keys/{provider}/test": {
        "successor": "/api/v2/settings/api-keys/{provider}/test",
        "sunset": "2025-04-01",
    },
    "/api/settings/test-connection/{provider}": {
        "successor": "/api/v2/settings/api-keys/{provider}/test",
        "sunset": "2025-04-01",
    },
    "/api/connections": {
        "successor": "/api/v2/settings/connections",
        "sunset": "2025-04-01",
    },
    "/api/connections/{id}": {
        "successor": "/api/v2/settings/connections/{id}",
        "sunset": "2025-04-01",
    },
    "/api/connections/{id}/test": {
        "successor": "/api/v2/settings/connections/{id}/test",
        "sunset": "2025-04-01",
    },
    "/api/modules/status": {
        "successor": "/api/v2/system/modules",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # Options & GEX (9 -> 6)
    # -------------------------------------------------------------------------
    "/api/options/chain/{symbol}": {
        "successor": "/api/v2/options/chain/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/options/gex/{symbol}": {
        "successor": "/api/v2/options/gex/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/options/flow": {
        "successor": "/api/v2/options/flow",
        "sunset": "2025-04-01",
    },
    "/api/gex/{symbol}": {
        "successor": "/api/v2/options/gex/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/v1/options-flow/unusual": {
        "successor": "/api/v2/options/flow?filter=unusual",
        "sunset": "2025-04-01",
    },
    "/api/v1/options-flow/gamma-exposure/{symbol}": {
        "successor": "/api/v2/options/gex/{symbol}",
        "sunset": "2025-04-01",
    },
    "/api/v1/options-flow/dark-pool": {
        "successor": "/api/v2/options/dark-pool",
        "sunset": "2025-04-01",
    },
    "/api/v1/options-flow/signals": {
        "successor": "/api/v2/options/signals",
        "sunset": "2025-04-01",
    },
    "/api/v1/options-flow/smart-money": {
        "successor": "/api/v2/options/smart-money",
        "sunset": "2025-04-01",
    },

    # -------------------------------------------------------------------------
    # WebSocket (kept for documentation, handled separately)
    # -------------------------------------------------------------------------
    "/ws/connect": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/market": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/market/{symbol}": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/orderbook/{symbol}": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/signals": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/trades": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/flow": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/brain": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/risk": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/system": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
    "/ws/executions": {
        "successor": "/ws/v2/stream",
        "sunset": "2025-04-01",
    },
}


# =============================================================================
# Deprecation Metrics - Track deprecated endpoint usage
# =============================================================================

@dataclass
class EndpointMetrics:
    """Metrics for a single deprecated endpoint."""
    total_calls: int = 0
    last_called: Optional[datetime] = None
    unique_clients: set = field(default_factory=set)
    calls_by_day: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class DeprecationMetrics:
    """
    Thread-safe metrics tracker for deprecated endpoint usage.
    
    Useful for monitoring which deprecated endpoints are still in use
    before removing them entirely.
    """
    
    def __init__(self):
        self._metrics: Dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self._lock = Lock()
    
    def record_call(
        self,
        endpoint: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Record a call to a deprecated endpoint."""
        with self._lock:
            metrics = self._metrics[endpoint]
            metrics.total_calls += 1
            metrics.last_called = datetime.now(timezone.utc)
            
            # Track unique clients by IP
            if client_ip:
                metrics.unique_clients.add(client_ip)
            
            # Track daily calls
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            metrics.calls_by_day[today] += 1
    
    def get_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for one or all deprecated endpoints."""
        with self._lock:
            if endpoint:
                m = self._metrics.get(endpoint)
                if not m:
                    return {}
                return {
                    "endpoint": endpoint,
                    "total_calls": m.total_calls,
                    "last_called": m.last_called.isoformat() if m.last_called else None,
                    "unique_clients": len(m.unique_clients),
                    "calls_by_day": dict(m.calls_by_day),
                }
            
            # All metrics
            return {
                endpoint: {
                    "total_calls": m.total_calls,
                    "last_called": m.last_called.isoformat() if m.last_called else None,
                    "unique_clients": len(m.unique_clients),
                    "calls_last_7_days": sum(
                        count for day, count in m.calls_by_day.items()
                        if (datetime.now(timezone.utc) - datetime.fromisoformat(day + "T00:00:00+00:00")).days < 7
                    ),
                }
                for endpoint, m in self._metrics.items()
                if m.total_calls > 0
            }
    
    def get_top_deprecated(self, limit: int = 10) -> list:
        """Get the most frequently called deprecated endpoints."""
        with self._lock:
            sorted_endpoints = sorted(
                self._metrics.items(),
                key=lambda x: x[1].total_calls,
                reverse=True
            )
            return [
                {
                    "endpoint": endpoint,
                    "total_calls": m.total_calls,
                    "unique_clients": len(m.unique_clients),
                }
                for endpoint, m in sorted_endpoints[:limit]
                if m.total_calls > 0
            ]
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()


# Global metrics instance
deprecation_metrics = DeprecationMetrics()


# =============================================================================
# Helper Functions
# =============================================================================

def _compile_patterns() -> list:
    """
    Compile deprecation map patterns to regex for efficient matching.
    Patterns with {param} placeholders are converted to regex groups.
    """
    patterns = []
    for path_pattern, config in DEPRECATION_MAP.items():
        # Convert {param} to regex named groups
        regex_pattern = re.sub(
            r'\{(\w+)\}',
            r'(?P<\1>[^/]+)',
            path_pattern
        )
        # Anchor the pattern
        regex = re.compile(f'^{regex_pattern}$')
        patterns.append((regex, path_pattern, config))
    return patterns


# Pre-compiled patterns for efficient matching
_DEPRECATION_PATTERNS = _compile_patterns()


def match_deprecated_endpoint(path: str) -> Optional[tuple]:
    """
    Match a request path against deprecated endpoint patterns.
    
    Returns:
        Tuple of (pattern_key, config, matched_params) or None if no match.
    """
    for regex, pattern_key, config in _DEPRECATION_PATTERNS:
        match = regex.match(path)
        if match:
            return (pattern_key, config, match.groupdict())
    return None


def build_successor_url(successor_template: str, params: Dict[str, str]) -> str:
    """Build the successor URL by substituting path parameters."""
    url = successor_template
    for key, value in params.items():
        url = url.replace(f'{{{key}}}', value)
    return url


def format_sunset_date(sunset_str: str) -> str:
    """
    Format sunset date to HTTP-date format (RFC 7231).
    Input: "2025-04-01"
    Output: "Tue, 01 Apr 2025 00:00:00 GMT"
    """
    dt = datetime.strptime(sunset_str, "%Y-%m-%d")
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


# =============================================================================
# Deprecation Middleware
# =============================================================================

class DeprecationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds RFC 8594 deprecation headers to deprecated endpoints.
    
    Headers added:
    - Deprecation: true (or date when deprecated)
    - Sunset: <HTTP-date> (when endpoint will be removed)
    - Link: <url>; rel="successor-version" (pointer to new endpoint)
    
    Also logs deprecation warnings and records metrics.
    """
    
    def __init__(
        self,
        app,
        log_warnings: bool = True,
        track_metrics: bool = True,
    ):
        super().__init__(app)
        self.log_warnings = log_warnings
        self.track_metrics = track_metrics
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Check if this is a deprecated endpoint
        match_result = match_deprecated_endpoint(path)
        
        if not match_result:
            # Not deprecated, pass through
            return await call_next(request)
        
        pattern_key, config, params = match_result
        
        # Log deprecation warning
        if self.log_warnings:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(
                f"DEPRECATED ENDPOINT: {request.method} {path} "
                f"from {client_ip} - migrate to {config['successor']}"
            )
        
        # Record metrics
        if self.track_metrics:
            deprecation_metrics.record_call(
                endpoint=pattern_key,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        
        # Call the actual endpoint
        response = await call_next(request)
        
        # Add deprecation headers
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = format_sunset_date(config["sunset"])
        
        # Build successor URL with parameters
        successor_url = build_successor_url(config["successor"], params)
        response.headers["Link"] = f'<{successor_url}>; rel="successor-version"'
        
        # Add custom header for easier debugging
        response.headers["X-Deprecated-Endpoint"] = pattern_key
        
        return response


# =============================================================================
# Redirect Middleware (Optional)
# =============================================================================

class RedirectMiddleware(BaseHTTPMiddleware):
    """
    Optional middleware that redirects old endpoints to new v2 endpoints.
    
    Uses HTTP 307 (Temporary Redirect) to preserve the request method.
    Can be enabled for soft migration or testing.
    
    Note: This is more aggressive than just adding headers - it actually
    redirects the request. Use with caution in production.
    """
    
    def __init__(
        self,
        app,
        enabled_patterns: Optional[list] = None,
        log_redirects: bool = True,
    ):
        """
        Initialize redirect middleware.
        
        Args:
            app: The ASGI application.
            enabled_patterns: List of endpoint patterns to redirect.
                             If None, redirects ALL deprecated endpoints.
            log_redirects: Whether to log redirect events.
        """
        super().__init__(app)
        self.enabled_patterns = set(enabled_patterns) if enabled_patterns else None
        self.log_redirects = log_redirects
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Check if this is a deprecated endpoint
        match_result = match_deprecated_endpoint(path)
        
        if not match_result:
            return await call_next(request)
        
        pattern_key, config, params = match_result
        
        # Check if this pattern should be redirected
        if self.enabled_patterns and pattern_key not in self.enabled_patterns:
            return await call_next(request)
        
        # Build redirect URL
        successor_url = build_successor_url(config["successor"], params)
        
        # Preserve query string
        if request.url.query:
            separator = "&" if "?" in successor_url else "?"
            successor_url = f"{successor_url}{separator}{request.url.query}"
        
        if self.log_redirects:
            logger.info(
                f"REDIRECT: {request.method} {path} -> {successor_url}"
            )
        
        # 307 preserves the request method (important for POST/PUT/DELETE)
        return RedirectResponse(
            url=successor_url,
            status_code=307,
            headers={
                "X-Redirect-Reason": "API deprecated - migrating to v2",
                "X-Original-Endpoint": path,
            }
        )


# =============================================================================
# Convenience Functions for Registration
# =============================================================================

def add_deprecation_middleware(
    app,
    log_warnings: bool = True,
    track_metrics: bool = True,
) -> None:
    """
    Add deprecation middleware to a FastAPI app.
    
    Example:
        from api.middleware.deprecation import add_deprecation_middleware
        add_deprecation_middleware(app)
    """
    app.add_middleware(
        DeprecationMiddleware,
        log_warnings=log_warnings,
        track_metrics=track_metrics,
    )


def add_redirect_middleware(
    app,
    enabled_patterns: Optional[list] = None,
    log_redirects: bool = True,
) -> None:
    """
    Add redirect middleware to a FastAPI app.
    
    Example:
        from api.middleware.deprecation import add_redirect_middleware
        # Redirect only specific endpoints
        add_redirect_middleware(app, enabled_patterns=[
            "/api/signals/active",
            "/api/market/tickers",
        ])
    """
    app.add_middleware(
        RedirectMiddleware,
        enabled_patterns=enabled_patterns,
        log_redirects=log_redirects,
    )


# =============================================================================
# API Routes for Metrics (optional, can be mounted separately)
# =============================================================================

def create_metrics_routes():
    """
    Create FastAPI router for deprecation metrics.
    
    Example:
        from api.middleware.deprecation import create_metrics_routes
        app.include_router(create_metrics_routes(), prefix="/admin")
    """
    from fastapi import APIRouter
    
    router = APIRouter(tags=["deprecation-metrics"])
    
    @router.get("/deprecation/metrics")
    async def get_all_metrics():
        """Get metrics for all deprecated endpoints."""
        return {
            "metrics": deprecation_metrics.get_metrics(),
            "top_deprecated": deprecation_metrics.get_top_deprecated(10),
        }
    
    @router.get("/deprecation/metrics/{endpoint:path}")
    async def get_endpoint_metrics(endpoint: str):
        """Get metrics for a specific deprecated endpoint."""
        # Reconstruct path with leading slash
        full_path = f"/{endpoint}" if not endpoint.startswith("/") else endpoint
        return deprecation_metrics.get_metrics(full_path)
    
    @router.post("/deprecation/metrics/reset")
    async def reset_metrics():
        """Reset all deprecation metrics."""
        deprecation_metrics.reset()
        return {"status": "ok", "message": "Metrics reset"}
    
    @router.get("/deprecation/map")
    async def get_deprecation_map():
        """Get the full deprecation map."""
        return {
            "total_deprecated": len(DEPRECATION_MAP),
            "map": DEPRECATION_MAP,
        }
    
    return router
