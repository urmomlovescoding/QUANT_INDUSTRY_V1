"""
Performance Middleware for QUANT INDUSTRY
Response caching, compression, and optimization
"""
import gzip
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL support"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._lock:
            if key not in self._cache:
                return None

            # Check TTL
            if time.time() - self._timestamps[key] > self.default_ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        with self._lock:
            # Remove if exists
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                del self._timestamps[oldest]

            self._cache[key] = value
            self._timestamps[key] = time.time()

    def invalidate(self, key: str):
        """Remove key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]

    def clear(self):
        """Clear all cache"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.default_ttl
            }


# Global response cache
_response_cache = LRUCache(max_size=500, default_ttl=30)


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware for caching API responses

    Caches GET requests based on path and query parameters.
    Cache is invalidated on POST/PUT/DELETE to related paths.
    """

    # Paths that should be cached
    CACHEABLE_PATHS = {
        "/api/market/status": 5,      # 5 second cache
        "/api/market/sectors": 30,    # 30 second cache
        "/api/market/movers": 30,
        "/api/market/tickers": 60,
        "/api/settings/presets": 300, # 5 minute cache
        "/api/brain-v6/rulesets": 300,
    }

    # Paths that should never be cached
    NOCACHE_PATHS = {
        "/api/health",
        "/api/system/health",
        "/api/market/quote",  # Quotes should be fresh
        "/api/positions",
        "/api/portfolio",
    }

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            # Invalidate related cache on mutations
            if request.method in ("POST", "PUT", "DELETE"):
                self._invalidate_related(request.url.path)
            return await call_next(request)

        # Check if path should be cached
        path = request.url.path
        ttl = self._get_cache_ttl(path)

        if ttl is None:
            return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Check cache
        cached = _response_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for {path}")
            return Response(
                content=cached["content"],
                status_code=cached["status_code"],
                headers={
                    **cached["headers"],
                    "X-Cache": "HIT"
                },
                media_type=cached["media_type"]
            )

        # Execute request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Store in cache
            _response_cache.set(cache_key, {
                "content": body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }, ttl)

            return Response(
                content=body,
                status_code=response.status_code,
                headers={**response.headers, "X-Cache": "MISS"},
                media_type=response.media_type
            )

        return response

    def _get_cache_ttl(self, path: str) -> Optional[int]:
        """Get TTL for a path, or None if not cacheable"""
        # Check nocache paths
        for nocache in self.NOCACHE_PATHS:
            if path.startswith(nocache):
                return None

        # Check explicit cache paths
        for cache_path, ttl in self.CACHEABLE_PATHS.items():
            if path.startswith(cache_path):
                return ttl

        return None

    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key from request"""
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.items()))
        ]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _invalidate_related(self, path: str):
        """Invalidate cache entries related to a path"""
        # Simple invalidation - clear entire cache for now
        # In production, would implement more targeted invalidation
        if path.startswith("/api/settings") or path.startswith("/api/brain"):
            _response_cache.clear()


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for response compression

    Compresses responses using gzip when:
    - Client accepts gzip encoding
    - Response is large enough (>1KB)
    - Content type is compressible (JSON, text)
    """

    COMPRESSIBLE_TYPES = {
        "application/json",
        "text/plain",
        "text/html",
        "text/css",
        "application/javascript",
        "text/javascript"
    }

    MIN_SIZE = 1024  # Minimum size to compress (1KB)

    async def dispatch(self, request: Request, call_next):
        # Check if client accepts gzip
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            return await call_next(request)

        response = await call_next(request)

        # Check if response should be compressed
        content_type = response.headers.get("Content-Type", "")
        base_type = content_type.split(";")[0]

        if base_type not in self.COMPRESSIBLE_TYPES:
            return response

        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Only compress if large enough
        if len(body) < self.MIN_SIZE:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        # Compress
        compressed = gzip.compress(body)

        # Only use compressed if smaller
        if len(compressed) < len(body):
            headers = dict(response.headers)
            headers["Content-Encoding"] = "gzip"
            headers["Content-Length"] = str(len(compressed))

            return Response(
                content=compressed,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type
            )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add response timing headers

    Adds X-Response-Time header to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        response.headers["X-Response-Time"] = f"{process_time:.2f}ms"

        # Log slow requests
        if process_time > 1000:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}ms"
            )

        return response


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return _response_cache.stats()


def clear_cache():
    """Clear all cached responses"""
    _response_cache.clear()
    logger.info("Response cache cleared")
