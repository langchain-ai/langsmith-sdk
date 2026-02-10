"""Prompt caching module for LangSmith SDK.

This module provides thread-safe LRU caches with background refresh
for prompt caching. Includes both sync and async implementations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import warnings
from abc import ABC
from collections import OrderedDict
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

if TYPE_CHECKING:
    pass

logger = logging.getLogger("langsmith.cache")


DEFAULT_PROMPT_CACHE_TTL_SECONDS = 5 * 60  # 5 minutes
DEFAULT_PROMPT_CACHE_MAX_SIZE = 100
DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS = 60  # 1 minute


@dataclass
class CacheEntry:
    """A single cache entry with metadata for TTL tracking."""

    value: Any  # The cached value (e.g., PromptCommit)
    created_at: float  # time.time() when entry was created/refreshed
    refresh_func: Optional[Callable[[], Any]] = None  # Function to refresh this entry

    def is_stale(self, ttl_seconds: Optional[float]) -> bool:
        """Check if entry is past its TTL (needs refresh)."""
        if ttl_seconds is None:
            return False  # Infinite TTL, never stale
        return (time.time() - self.created_at) > ttl_seconds


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    refreshes: int = 0
    refresh_errors: int = 0

    @property
    def total_requests(self) -> int:
        """Total cache requests (hits + misses)."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self.total_requests
        return self.hits / total if total > 0 else 0.0


class _BasePromptCache(ABC):
    """Base class for prompt caches with shared LRU logic.

    Provides thread-safe in-memory LRU cache operations.
    Subclasses implement the background refresh mechanism.
    """

    __slots__ = [
        "_cache",
        "_lock",
        "_max_size",
        "_ttl_seconds",
        "_refresh_interval",
        "_metrics",
    ]

    def __init__(
        self,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the base cache.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale. Set to None for
                infinite TTL (entries never expire, no background refresh).
            refresh_interval_seconds: How often to check for stale entries.
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._metrics = CacheMetrics()
        self._configure(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )

    @property
    def metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self._metrics = CacheMetrics()

    def get(self, key: str, refresh_func: Callable[[], Any]) -> Optional[Any]:
        """Get a value from cache.

        Args:
            key: The cache key (prompt identifier like "owner/name:hash").
            refresh_func: Function to refresh this cache entry when stale.

        Returns:
            The cached value or None if not found.
            Stale entries are still returned (background refresh handles updates).
        """
        # If max_size is 0, cache is disabled
        if self._max_size == 0:
            return None

        with self._lock:
            if key not in self._cache:
                self._metrics.misses += 1
                return None

            entry = self._cache[key]

            # Update refresh function
            entry.refresh_func = refresh_func

            # Move to end for LRU
            self._cache.move_to_end(key)

            self._metrics.hits += 1
            return entry.value

    def _set(self, key: str, value: Any, refresh_func: Callable[[], Any]) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key (prompt identifier).
            value: The value to cache.
            refresh_func: Function to refresh this cache entry when stale.
        """
        # If max_size is 0, cache is disabled - do nothing
        if self._max_size == 0:
            return

        with self._lock:
            now = time.time()
            entry = CacheEntry(value=value, created_at=now, refresh_func=refresh_func)

            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self._max_size:
                # Evict oldest (first item in OrderedDict)
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key)
                logger.debug(f"Evicted oldest cache entry: {oldest_key}")

            self._cache[key] = entry
            self._cache.move_to_end(key)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry from cache.

        Args:
            key: The cache key to invalidate.
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries from memory."""
        with self._lock:
            self._cache.clear()

    def _get_stale_entries(self) -> list[tuple[str, CacheEntry]]:
        """Get list of stale cache entries (thread-safe)."""
        with self._lock:
            return [
                (key, entry)
                for key, entry in self._cache.items()
                if entry.is_stale(self._ttl_seconds)
            ]

    def dump(self, path: Union[str, Path]) -> None:
        """Dump cache contents to a JSON file for offline use.

        Args:
            path: Path to the output JSON file.
        """
        from langsmith import schemas as ls_schemas

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            entries = {}
            for key, entry in self._cache.items():
                # Serialize PromptCommit using Pydantic
                if isinstance(entry.value, ls_schemas.PromptCommit):
                    # Handle both pydantic v1 and v2
                    if hasattr(entry.value, "model_dump"):
                        value_data = entry.value.model_dump(mode="json")
                    else:
                        value_data = entry.value.dict()
                else:
                    # Fallback for other types
                    value_data = entry.value

                entries[key] = value_data

            data = {"entries": entries}

        # Atomic write: write to temp file then rename
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(path)
            logger.debug(f"Dumped {len(entries)} cache entries to {path}")
        except Exception as e:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def load(self, path: Union[str, Path]) -> int:
        """Load cache contents from a JSON file.

        Args:
            path: Path to the JSON file to load.

        Returns:
            Number of entries loaded.

        Loaded entries get a fresh TTL starting from load time.
        If the file doesn't exist or is corrupted, returns 0.
        """
        from langsmith import schemas as ls_schemas

        path = Path(path)

        if not path.exists():
            logger.debug(f"Cache file not found: {path}")
            return 0

        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cache file {path}: {e}")
            return 0

        entries = data.get("entries", {})
        loaded = 0
        now = time.time()

        with self._lock:
            for key, value_data in entries.items():
                if len(self._cache) >= self._max_size:
                    logger.debug(f"Reached max cache size, stopping load at {loaded}")
                    break

                try:
                    # Deserialize PromptCommit using Pydantic (v1 and v2 compatible)
                    if hasattr(ls_schemas.PromptCommit, "model_validate"):
                        value = ls_schemas.PromptCommit.model_validate(value_data)
                    else:
                        value = ls_schemas.PromptCommit.parse_obj(value_data)

                    # Fresh TTL from load time
                    entry = CacheEntry(value=value, created_at=now)
                    self._cache[key] = entry
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to load cache entry {key}: {e}")
                    continue

        logger.debug(f"Loaded {loaded} cache entries from {path}")
        return loaded

    def _configure(
        self,
        max_size: int,
        ttl_seconds: Optional[float],
        refresh_interval_seconds: float,
    ) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._refresh_interval = refresh_interval_seconds


class PromptCache(_BasePromptCache):
    """Thread-safe LRU cache with background thread refresh.

    For use with the synchronous Client.

    Features:
    - In-memory LRU cache with configurable max size
    - Background thread for refreshing stale entries
    - Stale-while-revalidate: returns stale data while refresh happens
    - Thread-safe for concurrent access

    Example:
        >>> def fetch_prompt(key: str) -> PromptCommit:
        ...     return client._fetch_prompt_from_api(key)
        >>> cache = PromptCache(
        ...     max_size=100,
        ...     ttl_seconds=3600,
        ...     fetch_func=fetch_prompt,
        ... )
        >>> cache.set("my-prompt:latest", prompt_commit)
        >>> cached = cache.get("my-prompt:latest")
        >>> cache.shutdown()
    """

    __slots__ = ["_shutdown_event", "_refresh_thread"]

    def __init__(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the sync prompt cache.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale. Set to None for
                infinite TTL (offline mode - entries never expire).
                Default: 300 (5 minutes).
            refresh_interval_seconds: How often to check for stale entries.
        """
        super().__init__(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )
        self._shutdown_event = threading.Event()
        self._refresh_thread: Optional[threading.Thread] = None

        # Background refresh will be started lazily on first set() operation

    def set(self, key: str, value: Any, refresh_func: Callable[[], Any]) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key (prompt identifier).
            value: The value to cache.
            refresh_func: Function to refresh this cache entry when stale.
        """
        # Start background refresh on first set (lazy initialization)
        if self._refresh_thread is None:
            self._start_refresh_thread()
        self._set(key, value, refresh_func)

    def stop(self) -> None:
        """Stop background refresh thread.

        Should be called when the client is being cleaned up.
        """
        self.shutdown()

    def shutdown(self) -> None:
        """Stop background refresh thread.

        Should be called when the client is being cleaned up.
        """
        if self._shutdown_event is not None:
            self._shutdown_event.set()
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=5.0)
            self._refresh_thread = None

    def _start_refresh_thread(self) -> None:
        """Start background thread for refreshing stale entries."""
        if self._ttl_seconds is not None:
            self._shutdown_event.clear()
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop,
                daemon=True,
                name="PromptCache-refresh",
            )
            self._refresh_thread.start()
            logger.debug("Started cache refresh thread")

    def _refresh_loop(self) -> None:
        """Background loop to refresh stale entries."""
        while not self._shutdown_event.wait(self._refresh_interval):
            try:
                self._refresh_stale_entries()
            except Exception as e:
                # Log but don't die - keep the refresh loop running
                logger.exception(f"Unexpected error in cache refresh loop: {e}")

    def _refresh_stale_entries(self) -> None:
        """Check for stale entries and refresh them."""
        stale_entries = self._get_stale_entries()

        if not stale_entries:
            return

        logger.debug(f"Refreshing {len(stale_entries)} stale cache entries")

        for key, entry in stale_entries:
            if self._shutdown_event.is_set():
                break
            if entry.refresh_func is not None:
                try:
                    new_value = entry.refresh_func()
                    self.set(key, new_value, entry.refresh_func)
                    self._metrics.refreshes += 1
                    logger.debug(f"Refreshed cache entry: {key}")
                except Exception as e:
                    # Keep stale data on refresh failure
                    self._metrics.refresh_errors += 1
                    logger.warning(f"Failed to refresh cache entry {key}: {e}")

    def configure(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Reconfigure the cache parameters.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale.
            refresh_interval_seconds: How often to check for stale entries.
        """
        self.stop()
        self._configure(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )


class AsyncPromptCache(_BasePromptCache):
    """Thread-safe LRU cache with asyncio task refresh.

    For use with the asynchronous AsyncClient.

    Features:
    - In-memory LRU cache with configurable max size
    - Asyncio task for refreshing stale entries
    - Stale-while-revalidate: returns stale data while refresh happens
    - Thread-safe for concurrent access

    Example:
        >>> async def fetch_prompt(key: str) -> PromptCommit:
        ...     return await client._afetch_prompt_from_api(key)
        >>> cache = AsyncPromptCache(
        ...     max_size=100,
        ...     ttl_seconds=3600,
        ...     fetch_func=fetch_prompt,
        ... )
        >>> await cache.start()
        >>> cache.set("my-prompt:latest", prompt_commit)
        >>> cached = cache.get("my-prompt:latest")
        >>> await cache.stop()
    """

    __slots__ = ["_refresh_task"]

    def __init__(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the async prompt cache.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale. Set to None for
                infinite TTL (offline mode - entries never expire).
            refresh_interval_seconds: How often to check for stale entries.
        """
        super().__init__(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )
        self._refresh_task: Optional[asyncio.Task[None]] = None

    async def aset(
        self, key: str, value: Any, refresh_func: Callable[[], Awaitable[Any]]
    ) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key (prompt identifier).
            value: The value to cache.
            refresh_func: Async function to refresh this cache entry when stale.
        """
        # Start background refresh on first set (lazy initialization)
        if self._refresh_task is None:
            await self.start()
        self._set(key, value, refresh_func)

    async def start(self) -> None:
        """Start async background refresh loop.

        Must be called from an async context. Creates an asyncio task that
        periodically checks for stale entries and refreshes them.
        Does nothing if ttl_seconds is None (infinite TTL mode).
        """
        if self._ttl_seconds is None:
            return

        if self._refresh_task is not None:
            # Already running
            return

        self._refresh_task = asyncio.create_task(
            self._refresh_loop(),
            name="AsyncPromptCache-refresh",
        )
        logger.debug("Started async cache refresh task")

    def shutdown(self) -> None:
        """Stop background refresh task.

        Synchronous wrapper that cancels the refresh task.
        For proper cleanup in async context, use stop() instead.
        """
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    async def stop(self) -> None:
        """Stop async background refresh loop.

        Cancels the refresh task and waits for it to complete.
        """
        if self._refresh_task is None:
            return

        self._refresh_task.cancel()
        try:
            await self._refresh_task
        except asyncio.CancelledError:
            pass
        self._refresh_task = None
        logger.debug("Stopped async cache refresh task")

    async def _refresh_loop(self) -> None:
        """Async background loop to refresh stale entries."""
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self._refresh_stale_entries()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Log but don't die - keep the refresh loop running
                logger.exception(f"Unexpected error in async cache refresh loop: {e}")

    async def _refresh_stale_entries(self) -> None:
        """Check for stale entries and refresh them asynchronously."""
        stale_entries = self._get_stale_entries()

        if not stale_entries:
            return

        logger.debug(f"Async refreshing {len(stale_entries)} stale cache entries")

        for key, entry in stale_entries:
            if entry.refresh_func is not None:
                try:
                    new_value = await entry.refresh_func()
                    await self.aset(key, new_value, entry.refresh_func)
                    self._metrics.refreshes += 1
                    logger.debug(f"Async refreshed cache entry: {key}")
                except Exception as e:
                    # Keep stale data on refresh failure
                    self._metrics.refresh_errors += 1
                    logger.warning(f"Failed to async refresh cache entry {key}: {e}")

    async def configure(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Reconfigure the cache parameters.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale.
            refresh_interval_seconds: How often to check for stale entries.
        """
        await self.stop()
        self._configure(max_size, ttl_seconds, refresh_interval_seconds)


# Global singleton instances for prompt caching
prompt_cache_singleton = PromptCache()
async_prompt_cache_singleton = AsyncPromptCache()


def configure_global_prompt_cache(
    *,
    max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
    ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
    refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
) -> None:
    """Configure the global prompt cache.

    This should be called before any cache instances are created or used.

    Args:
        max_size: Maximum entries in cache (LRU eviction when exceeded).
        ttl_seconds: Time before entry is considered stale.
        refresh_interval_seconds: How often to check for stale entries.

    Example:
        >>> from langsmith import configure_global_prompt_cache
        >>> configure_global_prompt_cache(max_size=200, ttl_seconds=7200)
    """
    prompt_cache_singleton.configure(
        max_size=max_size,
        ttl_seconds=ttl_seconds,
        refresh_interval_seconds=refresh_interval_seconds,
    )


async def configure_global_async_prompt_cache(
    *,
    max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
    ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
    refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
) -> None:
    """Configure the global prompt cache.

    This should be called before any cache instances are created or used.

    Args:
        max_size: Maximum entries in cache (LRU eviction when exceeded).
        ttl_seconds: Time before entry is considered stale.
        refresh_interval_seconds: How often to check for stale entries.

    Example:
        >>> from langsmith import configure_global_prompt_cache
        >>> configure_global_prompt_cache(max_size=200, ttl_seconds=7200)
    """
    await async_prompt_cache_singleton.configure(
        max_size=max_size,
        ttl_seconds=ttl_seconds,
        refresh_interval_seconds=refresh_interval_seconds,
    )


# Deprecated alias for backwards compatibility


def _deprecated_cache_class_warning() -> None:
    warnings.warn(
        "The 'Cache' class is deprecated and will be removed in a future version. "
        "Use 'PromptCache' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


class Cache(PromptCache):
    """Deprecated alias for PromptCache. Use PromptCache instead."""

    def __init__(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the deprecated Cache class.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale.
            refresh_interval_seconds: How often to check for stale entries.
        """
        _deprecated_cache_class_warning()
        super().__init__(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )


class AsyncCache(AsyncPromptCache):
    """Deprecated alias for AsyncPromptCache. Use AsyncPromptCache instead."""

    def __init__(
        self,
        *,
        max_size: int = DEFAULT_PROMPT_CACHE_MAX_SIZE,
        ttl_seconds: Optional[float] = DEFAULT_PROMPT_CACHE_TTL_SECONDS,
        refresh_interval_seconds: float = DEFAULT_PROMPT_CACHE_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the deprecated AsyncCache class.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale.
            refresh_interval_seconds: How often to check for stale entries.
        """
        _deprecated_cache_class_warning()
        super().__init__(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            refresh_interval_seconds=refresh_interval_seconds,
        )
