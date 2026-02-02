"""Singleton cache manager for prompts.

This module provides singleton caches that are shared across all Client instances,
improving cache hit rates and memory efficiency when multiple clients are used
in the same process.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from langsmith.cache import AsyncCache, Cache

# Module-level singleton cache instances
_cache_instance: Optional[Cache] = None
_async_cache_instance: Optional[AsyncCache] = None
_cache_lock = threading.RLock()


class PromptCacheManager:
    """Manager for the singleton prompt cache (sync version).
    
    This manager ensures only one Cache instance is shared across
    all Client instances in the same process.
    """

    def get_instance(self) -> Optional[Cache]:
        """Get the cache instance.
        
        Returns:
            The singleton Cache instance, or None if not initialized.
        """
        return _cache_instance

    def initialize_instance(
        self,
        max_size: int = 100,
        ttl_seconds: Optional[float] = 3600.0,
        refresh_interval_seconds: float = 60.0,
        force: bool = False,
    ) -> Cache:
        """Initialize the cache instance.
        
        If already initialized, this is a no-op unless force=True.
        
        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale. Set to None for
                infinite TTL (entries never expire, no background refresh).
            refresh_interval_seconds: How often to check for stale entries.
            force: If True, replace existing cache instance (will shutdown the old one).
            
        Returns:
            The cache instance.
        """
        global _cache_instance

        with _cache_lock:
            if _cache_instance is not None and not force:
                # Already initialized, return existing
                return _cache_instance

            if _cache_instance is not None and force:
                # Shutdown the existing cache before replacing
                _cache_instance.shutdown()

            # Import here to avoid circular dependency
            from langsmith.cache import Cache

            # Create new cache instance
            _cache_instance = Cache(
                max_size=max_size,
                ttl_seconds=ttl_seconds,
                refresh_interval_seconds=refresh_interval_seconds,
            )
            return _cache_instance

    def is_initialized(self) -> bool:
        """Check if the cache has been initialized."""
        return _cache_instance is not None

    def cleanup(self) -> None:
        """Shutdown and clear the cache instance."""
        global _cache_instance

        with _cache_lock:
            if _cache_instance is not None:
                _cache_instance.shutdown()
                _cache_instance = None


class AsyncPromptCacheManager:
    """Manager for the singleton async prompt cache.
    
    This manager ensures only one AsyncCache instance is shared across
    all AsyncClient instances in the same process.
    """

    def get_instance(self) -> Optional[AsyncCache]:
        """Get the async cache instance.
        
        Returns:
            The singleton AsyncCache instance, or None if not initialized.
        """
        return _async_cache_instance

    def initialize_instance(
        self,
        max_size: int = 100,
        ttl_seconds: Optional[float] = 3600.0,
        refresh_interval_seconds: float = 60.0,
        force: bool = False,
    ) -> AsyncCache:
        """Initialize the async cache instance.
        
        If already initialized, this is a no-op unless force=True.
        
        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale. Set to None for
                infinite TTL (entries never expire, no background refresh).
            refresh_interval_seconds: How often to check for stale entries.
            force: If True, replace existing cache instance (will shutdown the old one).
            
        Returns:
            The async cache instance.
        """
        global _async_cache_instance

        with _cache_lock:
            if _async_cache_instance is not None and not force:
                # Already initialized, return existing
                return _async_cache_instance

            if _async_cache_instance is not None and force:
                # Shutdown the existing cache before replacing
                _async_cache_instance.shutdown()

            # Import here to avoid circular dependency
            from langsmith.cache import AsyncCache

            # Create new cache instance
            _async_cache_instance = AsyncCache(
                max_size=max_size,
                ttl_seconds=ttl_seconds,
                refresh_interval_seconds=refresh_interval_seconds,
            )
            return _async_cache_instance

    def is_initialized(self) -> bool:
        """Check if the async cache has been initialized."""
        return _async_cache_instance is not None

    def cleanup(self) -> None:
        """Shutdown and clear the async cache instance."""
        global _async_cache_instance

        with _cache_lock:
            if _async_cache_instance is not None:
                _async_cache_instance.shutdown()
                _async_cache_instance = None


# Singleton instances
PromptCacheManagerSingleton = PromptCacheManager()
AsyncPromptCacheManagerSingleton = AsyncPromptCacheManager()


def get_or_initialize_cache(
    max_size: int = 100,
    ttl_seconds: Optional[float] = 3600.0,
    refresh_interval_seconds: float = 60.0,
) -> Cache:
    """Get or initialize the prompt cache singleton.
    
    Args:
        max_size: Maximum entries in cache (used only if not yet initialized).
        ttl_seconds: TTL for cache entries (used only if not yet initialized).
        refresh_interval_seconds: Refresh interval (used only if not yet initialized).
        
    Returns:
        The singleton cache instance.
    """
    existing = PromptCacheManagerSingleton.get_instance()
    if existing is not None:
        return existing
    return PromptCacheManagerSingleton.initialize_instance(
        max_size=max_size,
        ttl_seconds=ttl_seconds,
        refresh_interval_seconds=refresh_interval_seconds,
    )


def get_or_initialize_async_cache(
    max_size: int = 100,
    ttl_seconds: Optional[float] = 3600.0,
    refresh_interval_seconds: float = 60.0,
) -> AsyncCache:
    """Get or initialize the async prompt cache singleton.
    
    Args:
        max_size: Maximum entries in cache (used only if not yet initialized).
        ttl_seconds: TTL for cache entries (used only if not yet initialized).
        refresh_interval_seconds: Refresh interval (used only if not yet initialized).
        
    Returns:
        The singleton async cache instance.
    """
    existing = AsyncPromptCacheManagerSingleton.get_instance()
    if existing is not None:
        return existing
    return AsyncPromptCacheManagerSingleton.initialize_instance(
        max_size=max_size,
        ttl_seconds=ttl_seconds,
        refresh_interval_seconds=refresh_interval_seconds,
    )
