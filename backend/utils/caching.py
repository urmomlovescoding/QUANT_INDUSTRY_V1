"""
API Response Caching with ETag Support for QUANT INDUSTRY
==========================================================
Provides HTTP caching with:
- ETag generation and validation
- Cache-Control headers
- In-memory and Redis caching
- Cache invalidation

Matches quant-platform pattern for API performance optimization.
"""

import asyncio
import functools
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ============== CACHE TYPES ==============

class CachePolicy(Enum):
    """Cache control policies"""
    NO_CACHE = "no-cache"
    NO_STORE = "no-store"
    PRIVATE = "private"
    PUBLIC = "public"
    MUST_REVALIDATE = "must-revalidate"


@dataclass
class CacheConfig:
    """Configuration for cache behavior"""
    enabled: bool = True
    default_ttl: int = 60  # seconds
    max_size: int = 1000  # max entries
    policy: CachePolicy = CachePolicy.PRIVATE
    etag_enabled: bool = True
    vary_headers: List[str] = field(default_factory=lambda: ["Accept", "Accept-Encoding"])


@dataclass
class CacheEntry:
    """A cached response entry"""
    content: bytes
    content_type: str
    etag: str
    created_at: datetime
    expires_at: datetime
    headers: Dict[str, str] = field(default_factory=dict)
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @property
    def age(self) -> int:
        """Age in seconds"""
        return int((datetime.now() - self.created_at).total_seconds())


# ============== ETAG UTILITIES ==============

def generate_etag(content: Union[bytes, str, dict]) -> str:
    """
    Generate an ETag for content.

    Args:
        content: Response content (bytes, string, or dict)

    Returns:
        ETag string (weak ETag format: W/"hash")
    """
    if isinstance(content, dict):
        content = json.dumps(content, sort_keys=True, default=str)

    if isinstance(content, str):
        content = content.encode('utf-8')

    # Use MD5 for speed (ETag doesn't need cryptographic security)
    hash_value = hashlib.md5(content).hexdigest()[:16]

    # Weak ETag (W/) indicates semantic equivalence
    return f'W/"{hash_value}"'


def etag_matches(etag: str, if_none_match: str) -> bool:
    """
    Check if ETag matches If-None-Match header.

    Args:
        etag: Current ETag
        if_none_match: Value from If-None-Match header

    Returns:
        True if ETags match (304 should be returned)
    """
    if not if_none_match:
        return False

    # Handle multiple ETags in If-None-Match
    client_etags = [e.strip() for e in if_none_match.split(',')]

    # Check for wildcard
    if '*' in client_etags:
        return True

    # Normalize ETags for comparison
    etag_normalized = etag.strip('"').lstrip('W/')

    for client_etag in client_etags:
        client_normalized = client_etag.strip('"').lstrip('W/')
        if etag_normalized == client_normalized:
            return True

    return False


# ============== IN-MEMORY CACHE ==============

class InMemoryCache:
    """
    Thread-safe in-memory cache with LRU eviction.

    Example:
        cache = InMemoryCache(max_size=1000, default_ttl=60)
        cache.set("key", "value")
        value = cache.get("key")
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 60
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl

        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._lock = asyncio.Lock()

        # Stats
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cached entry"""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired:
                del self._cache[key]
                self._access_order.remove(key)
                self._misses += 1
                return None

            # Update access order (LRU)
            self._access_order.remove(key)
            self._access_order.append(key)

            entry.hit_count += 1
            self._hits += 1
            return entry

    async def set(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/json",
        ttl: int = None,
        headers: Dict[str, str] = None
    ) -> CacheEntry:
        """Set a cached entry"""
        ttl = ttl or self.default_ttl

        entry = CacheEntry(
            content=content,
            content_type=content_type,
            etag=generate_etag(content),
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=ttl),
            headers=headers or {}
        )

        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = self._access_order.pop(0)
                del self._cache[oldest_key]

            self._cache[key] = entry
            self._access_order.append(key)

        return entry

    async def delete(self, key: str) -> bool:
        """Delete a cached entry"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_order.remove(key)
                return True
            return False

    async def clear(self) -> int:
        """Clear all entries"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            return count

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate entries matching a pattern"""
        async with self._lock:
            keys_to_delete = [
                k for k in self._cache.keys()
                if pattern in k
            ]
            for key in keys_to_delete:
                del self._cache[key]
                self._access_order.remove(key)
            return len(keys_to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2)
        }


# ============== CACHE KEY GENERATION ==============

def generate_cache_key(
    request: Request,
    vary_headers: List[str] = None
) -> str:
    """
    Generate a cache key from a request.

    Args:
        request: FastAPI request
        vary_headers: Headers to include in cache key

    Returns:
        Cache key string
    """
    parts = [
        request.method,
        str(request.url.path),
        str(request.query_params)
    ]

    # Include varied headers
    if vary_headers:
        for header in vary_headers:
            value = request.headers.get(header, "")
            parts.append(f"{header}:{value}")

    key_string = "|".join(parts)
    return hashlib.md5(key_string.encode()).hexdigest()


# ============== FASTAPI MIDDLEWARE ==============

class CacheMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for response caching with ETag support.

    Example:
        from fastapi import FastAPI
        from utils.caching import CacheMiddleware, CacheConfig

        app = FastAPI()
        app.add_middleware(
            CacheMiddleware,
            config=CacheConfig(default_ttl=60)
        )
    """

    def __init__(
        self,
        app,
        config: CacheConfig = None,
        cache: InMemoryCache = None
    ):
        super().__init__(app)
        self.config = config or CacheConfig()
        self.cache = cache or InMemoryCache(
            max_size=self.config.max_size,
            default_ttl=self.config.default_ttl
        )

    async def dispatch(self, request: Request, call_next):
        # Skip caching for non-GET requests
        if request.method != "GET":
            return await call_next(request)

        # Skip if caching disabled
        if not self.config.enabled:
            return await call_next(request)

        # Check for no-cache header
        cache_control = request.headers.get("Cache-Control", "")
        if "no-cache" in cache_control or "no-store" in cache_control:
            return await call_next(request)

        # Generate cache key
        cache_key = generate_cache_key(request, self.config.vary_headers)

        # Check for cached response
        cached = await self.cache.get(cache_key)

        if cached:
            # Check If-None-Match
            if_none_match = request.headers.get("If-None-Match")
            if if_none_match and etag_matches(cached.etag, if_none_match):
                # Return 304 Not Modified
                return Response(
                    status_code=304,
                    headers={
                        "ETag": cached.etag,
                        "Cache-Control": f"{self.config.policy.value}, max-age={self.config.default_ttl}",
                        "Age": str(cached.age)
                    }
                )

            # Return cached response
            response = Response(
                content=cached.content,
                media_type=cached.content_type,
                headers={
                    "ETag": cached.etag,
                    "Cache-Control": f"{self.config.policy.value}, max-age={self.config.default_ttl}",
                    "Age": str(cached.age),
                    "X-Cache": "HIT"
                }
            )
            return response

        # Call the actual endpoint
        response = await call_next(request)

        # Only cache successful GET responses
        if response.status_code == 200:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Cache the response
            content_type = response.headers.get("Content-Type", "application/json")
            entry = await self.cache.set(
                cache_key,
                body,
                content_type,
                self.config.default_ttl
            )

            # Create new response with cache headers
            headers = dict(response.headers)
            headers["ETag"] = entry.etag
            headers["Cache-Control"] = f"{self.config.policy.value}, max-age={self.config.default_ttl}"
            headers["X-Cache"] = "MISS"

            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=content_type
            )

        return response


# ============== DECORATOR-BASED CACHING ==============

def cached(
    ttl: int = 60,
    key_prefix: str = "",
    etag: bool = True,
    vary: List[str] = None
):
    """
    Decorator for caching endpoint responses.

    Example:
        @app.get("/api/data")
        @cached(ttl=120)
        async def get_data():
            return {"data": "value"}
    """
    def decorator(func: Callable):
        cache = InMemoryCache(default_ttl=ttl)

        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{generate_cache_key(request, vary)}"

            # Check cache
            cached_entry = await cache.get(cache_key)

            if cached_entry:
                # Check ETag
                if etag:
                    if_none_match = request.headers.get("If-None-Match")
                    if if_none_match and etag_matches(cached_entry.etag, if_none_match):
                        return Response(
                            status_code=304,
                            headers={"ETag": cached_entry.etag}
                        )

                return Response(
                    content=cached_entry.content,
                    media_type=cached_entry.content_type,
                    headers={
                        "ETag": cached_entry.etag,
                        "X-Cache": "HIT",
                        "Age": str(cached_entry.age)
                    }
                )

            # Call endpoint
            result = await func(request, *args, **kwargs)

            # Cache result
            if isinstance(result, Response):
                content = result.body
                content_type = result.media_type or "application/json"
            else:
                content = json.dumps(result, default=str).encode('utf-8')
                content_type = "application/json"

            entry = await cache.set(cache_key, content, content_type, ttl)

            if isinstance(result, Response):
                result.headers["ETag"] = entry.etag
                result.headers["X-Cache"] = "MISS"
                return result

            return Response(
                content=content,
                media_type=content_type,
                headers={
                    "ETag": entry.etag,
                    "X-Cache": "MISS"
                }
            )

        return wrapper
    return decorator


# ============== CACHE INVALIDATION ==============

class CacheInvalidator:
    """
    Manages cache invalidation across multiple cache instances.

    Example:
        invalidator = CacheInvalidator()
        invalidator.register("api", api_cache)

        # Invalidate specific patterns
        await invalidator.invalidate("api", "/api/signals*")

        # Invalidate on data changes
        invalidator.on_change("signals", lambda: invalidator.invalidate("api", "/api/signals*"))
    """

    def __init__(self):
        self._caches: Dict[str, InMemoryCache] = {}
        self._handlers: Dict[str, List[Callable]] = {}

    def register(self, name: str, cache: InMemoryCache) -> None:
        """Register a cache for invalidation"""
        self._caches[name] = cache

    async def invalidate(self, cache_name: str, pattern: str = "") -> int:
        """Invalidate cache entries matching pattern"""
        cache = self._caches.get(cache_name)
        if not cache:
            return 0

        if pattern:
            return await cache.invalidate_pattern(pattern)
        else:
            return await cache.clear()

    async def invalidate_all(self) -> Dict[str, int]:
        """Invalidate all registered caches"""
        results = {}
        for name, cache in self._caches.items():
            results[name] = await cache.clear()
        return results

    def on_change(self, event: str, handler: Callable) -> None:
        """Register a handler for data change events"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    async def notify_change(self, event: str) -> None:
        """Notify that data has changed"""
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Cache invalidation handler error: {e}")


# ============== CONDITIONAL RESPONSES ==============

def add_cache_headers(
    response: Response,
    content: bytes,
    ttl: int = 60,
    policy: CachePolicy = CachePolicy.PRIVATE
) -> Response:
    """
    Add cache headers to a response.

    Args:
        response: FastAPI response
        content: Response content for ETag generation
        ttl: Cache TTL in seconds
        policy: Cache-Control policy

    Returns:
        Response with cache headers
    """
    etag = generate_etag(content)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = f"{policy.value}, max-age={ttl}"
    response.headers["Expires"] = (
        datetime.utcnow() + timedelta(seconds=ttl)
    ).strftime("%a, %d %b %Y %H:%M:%S GMT")

    return response


def check_not_modified(
    request: Request,
    etag: str
) -> Optional[Response]:
    """
    Check if 304 Not Modified should be returned.

    Args:
        request: FastAPI request
        etag: Current ETag

    Returns:
        304 Response if not modified, None otherwise
    """
    if_none_match = request.headers.get("If-None-Match")

    if if_none_match and etag_matches(etag, if_none_match):
        return Response(
            status_code=304,
            headers={"ETag": etag}
        )

    return None


# ============== SINGLETON ==============

_global_cache: Optional[InMemoryCache] = None
_cache_invalidator: Optional[CacheInvalidator] = None


def get_cache() -> InMemoryCache:
    """Get or create the global cache"""
    global _global_cache

    if _global_cache is None:
        _global_cache = InMemoryCache()

    return _global_cache


def get_cache_invalidator() -> CacheInvalidator:
    """Get or create the global cache invalidator"""
    global _cache_invalidator

    if _cache_invalidator is None:
        _cache_invalidator = CacheInvalidator()
        _cache_invalidator.register("default", get_cache())

    return _cache_invalidator
