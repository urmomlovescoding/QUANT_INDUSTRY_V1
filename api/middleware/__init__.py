"""
API Middleware Package
======================
Custom middleware for the QUANT INDUSTRY V1 API.
"""

from .deprecation import (
    # Middleware classes
    DeprecationMiddleware,
    RedirectMiddleware,
    
    # Convenience registration functions
    add_deprecation_middleware,
    add_redirect_middleware,
    
    # Metrics
    deprecation_metrics,
    DeprecationMetrics,
    
    # Mapping
    DEPRECATION_MAP,
    
    # Routes factory
    create_metrics_routes,
)

__all__ = [
    "DeprecationMiddleware",
    "RedirectMiddleware",
    "add_deprecation_middleware",
    "add_redirect_middleware",
    "deprecation_metrics",
    "DeprecationMetrics",
    "DEPRECATION_MAP",
    "create_metrics_routes",
]
