"""Prompt caching module for LangSmith SDK.

This module provides a thread-safe LRU cache with filesystem persistence
and background TTL-based refresh for prompt caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from langsmith._internal._serde import dumps_json

if TYPE_CHECKING:
    from langsmith import schemas as ls_schemas

logger = logging.getLogger("langsmith.cache")

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A single cache entry with metadata for TTL tracking."""

    value: Any  # The cached value (e.g., PromptCommit)
    created_at: float  # time.time() when entry was created
    last_accessed_at: float  # time.time() when entry was last accessed
    refresh_attempted_at: Optional[float] = None  # When background refresh was last attempted

    def is_stale(self, ttl_seconds: float) -> bool:
        """Check if entry is past its TTL (needs refresh)."""
        return (time.time() - self.created_at) > ttl_seconds

    def is_expired(self, max_stale_seconds: float) -> bool:
        """Check if entry is too old to serve even as stale data."""
        return (time.time() - self.created_at) > max_stale_seconds


class PromptCache:
    """Thread-safe LRU cache with filesystem persistence and background refresh.

    Features:
    - In-memory LRU cache with configurable max size
    - Write-through filesystem persistence (JSON format)
    - Background TTL-based refresh (stale-while-revalidate)
    - Thread-safe for concurrent access
    - Cache warming from filesystem on startup

    Example:
        >>> cache = PromptCache(
        ...     max_size=100,
        ...     ttl_seconds=3600,
        ...     persist_path="/path/to/cache",
        ... )
        >>> cache.set("my-prompt:latest", prompt_commit)
        >>> cached = cache.get("my-prompt:latest")
    """

    __slots__ = [
        "_cache",
        "_lock",
        "_max_size",
        "_ttl_seconds",
        "_max_stale_seconds",
        "_persist_path",
        "_refresh_interval_seconds",
        "_refresh_thread",
        "_stop_event",
        "_fetch_func",
        "_client_ref",
        "_enabled",
    ]

    def __init__(
        self,
        *,
        max_size: int = 100,
        ttl_seconds: float = 3600.0,  # 1 hour
        max_stale_seconds: float = 86400.0,  # 24 hours
        persist_path: Optional[str] = None,
        refresh_interval_seconds: float = 60.0,
        fetch_func: Optional[Callable[[str], Any]] = None,
        client_ref: Optional[weakref.ref] = None,
        enabled: bool = True,
    ) -> None:
        """Initialize the prompt cache.

        Args:
            max_size: Maximum entries in cache (LRU eviction when exceeded).
            ttl_seconds: Time before entry is considered stale and needs refresh.
            max_stale_seconds: Maximum time to serve stale data before requiring fresh fetch.
            persist_path: Directory for JSON cache files. Defaults to ~/.langsmith/prompt_cache/
            refresh_interval_seconds: Interval for background thread to check for stale entries.
            fetch_func: Function to fetch fresh data, signature: (key: str) -> Any.
            client_ref: Weak reference to the Client instance for lifecycle management.
            enabled: Whether caching is enabled.
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._max_stale_seconds = max_stale_seconds
        self._persist_path = Path(persist_path) if persist_path else self._default_persist_path()
        self._refresh_interval_seconds = refresh_interval_seconds
        self._fetch_func = fetch_func
        self._client_ref = client_ref
        self._enabled = enabled
        self._stop_event = threading.Event()
        self._refresh_thread: Optional[threading.Thread] = None

        if self._enabled:
            # Ensure persist directory exists
            try:
                self._persist_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Failed to create cache directory {self._persist_path}: {e}")

            # Warm cache from filesystem
            self._warm_from_filesystem()

            # Start background refresh thread
            self._start_refresh_thread()

    @staticmethod
    def _default_persist_path() -> Path:
        """Get default cache directory path."""
        return Path.home() / ".langsmith" / "prompt_cache"

    def get(self, key: str) -> Optional[ls_schemas.PromptCommit]:
        """Get a value from cache.

        Returns cached value if available (even if stale, within max_stale_seconds).
        Triggers background refresh if entry is stale.
        Returns None if no entry exists or entry is too old.

        Args:
            key: The cache key (prompt identifier like "owner/name:hash").

        Returns:
            The cached PromptCommit or None if not found/expired.
        """
        if not self._enabled:
            return None

        with self._lock:
            if key not in self._cache:
                # Try loading from filesystem
                entry = self._load_from_filesystem(key)
                if entry is None:
                    return None
                self._cache[key] = entry

            entry = self._cache[key]

            # Check if too old to serve
            if entry.is_expired(self._max_stale_seconds):
                self._cache.pop(key, None)
                self._delete_from_filesystem(key)
                return None

            # Move to end for LRU
            self._cache.move_to_end(key)
            entry.last_accessed_at = time.time()

            # Return value (may be stale, refresh happens in background)
            return entry.value

    def set(self, key: str, value: ls_schemas.PromptCommit) -> None:
        """Set a value in the cache with write-through persistence.

        Args:
            key: The cache key (prompt identifier).
            value: The PromptCommit to cache.
        """
        if not self._enabled:
            return

        with self._lock:
            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                last_accessed_at=now,
            )

            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self._max_size:
                # Evict oldest (first item in OrderedDict)
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key)
                self._delete_from_filesystem(oldest_key)
                logger.debug(f"Evicted oldest cache entry: {oldest_key}")

            self._cache[key] = entry
            self._cache.move_to_end(key)

            # Write-through to filesystem
            self._persist_to_filesystem(key, entry)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry from cache.

        Args:
            key: The cache key to invalidate.
        """
        if not self._enabled:
            return

        with self._lock:
            self._cache.pop(key, None)
            self._delete_from_filesystem(key)

    def clear(self) -> None:
        """Clear all cache entries from memory and filesystem."""
        with self._lock:
            self._cache.clear()
            # Clear filesystem cache
            if self._persist_path.exists():
                for f in self._persist_path.glob("*.json"):
                    try:
                        f.unlink()
                    except OSError:
                        pass

    # -------------------------------------------------------------------------
    # Filesystem persistence
    # -------------------------------------------------------------------------

    def _key_to_filename(self, key: str) -> str:
        """Convert cache key to safe filename.

        Handles special characters in prompt identifiers like "owner/name:hash".
        """
        # Use hash for safety with special chars, but keep prefix for debugging
        safe_prefix = key.replace("/", "_").replace(":", "_")[:50]
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"{safe_prefix}_{key_hash}.json"

    def _persist_to_filesystem(self, key: str, entry: CacheEntry) -> None:
        """Write cache entry to filesystem with atomic write."""
        try:
            filename = self._key_to_filename(key)
            filepath = self._persist_path / filename

            # Serialize the value using Pydantic's method
            if hasattr(entry.value, "model_dump"):
                value_dict = entry.value.model_dump()  # Pydantic v2
            elif hasattr(entry.value, "dict"):
                value_dict = entry.value.dict()  # Pydantic v1
            else:
                value_dict = entry.value

            data = {
                "key": key,
                "value": value_dict,
                "created_at": entry.created_at,
                "last_accessed_at": entry.last_accessed_at,
            }

            # Write atomically using temp file + rename
            temp_path = filepath.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                f.write(dumps_json(data))
            temp_path.rename(filepath)

        except Exception as e:
            logger.warning(f"Failed to persist cache entry {key}: {e}")

    def _load_from_filesystem(self, key: str) -> Optional[CacheEntry]:
        """Load cache entry from filesystem."""
        try:
            from langsmith import schemas as ls_schemas

            filename = self._key_to_filename(key)
            filepath = self._persist_path / filename

            if not filepath.exists():
                return None

            with open(filepath, "r") as f:
                data = json.load(f)

            # Validate key matches
            if data.get("key") != key:
                logger.warning(f"Cache key mismatch in file {filename}")
                return None

            # Reconstruct PromptCommit
            value = ls_schemas.PromptCommit(**data["value"])

            return CacheEntry(
                value=value,
                created_at=data["created_at"],
                last_accessed_at=data.get("last_accessed_at", data["created_at"]),
            )

        except Exception as e:
            logger.warning(f"Failed to load cache entry {key}: {e}")
            return None

    def _delete_from_filesystem(self, key: str) -> None:
        """Delete cache entry from filesystem."""
        try:
            filename = self._key_to_filename(key)
            filepath = self._persist_path / filename
            if filepath.exists():
                filepath.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete cache file for {key}: {e}")

    def _warm_from_filesystem(self) -> None:
        """Load existing cache entries from filesystem on startup."""
        if not self._persist_path.exists():
            return

        from langsmith import schemas as ls_schemas

        loaded_count = 0
        for filepath in self._persist_path.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                key = data.get("key")
                if not key:
                    continue

                value = ls_schemas.PromptCommit(**data["value"])
                entry = CacheEntry(
                    value=value,
                    created_at=data["created_at"],
                    last_accessed_at=data.get("last_accessed_at", data["created_at"]),
                )

                # Skip if expired
                if entry.is_expired(self._max_stale_seconds):
                    try:
                        filepath.unlink()
                    except OSError:
                        pass
                    continue

                # Add to cache (respecting max_size)
                if len(self._cache) < self._max_size:
                    self._cache[key] = entry
                    loaded_count += 1

            except Exception as e:
                logger.warning(f"Failed to warm cache from {filepath}: {e}")

        if loaded_count > 0:
            logger.debug(f"Warmed cache with {loaded_count} entries from filesystem")

    # -------------------------------------------------------------------------
    # Background refresh thread
    # -------------------------------------------------------------------------

    def _start_refresh_thread(self) -> None:
        """Start the background refresh thread."""
        if self._refresh_thread is not None:
            return

        self._refresh_thread = threading.Thread(
            target=self._refresh_thread_func,
            daemon=True,
            name="langsmith-prompt-cache-refresh",
        )
        self._refresh_thread.start()

    def _refresh_thread_func(self) -> None:
        """Background thread that refreshes stale cache entries."""
        logger.debug("Prompt cache refresh thread started")

        while not self._stop_event.is_set():
            try:
                self._refresh_stale_entries()
            except Exception as e:
                logger.warning(f"Error in cache refresh thread: {e}")

            # Wait for next refresh interval or stop event
            self._stop_event.wait(timeout=self._refresh_interval_seconds)

        logger.debug("Prompt cache refresh thread stopped")

    def _refresh_stale_entries(self) -> None:
        """Find and refresh stale entries."""
        if self._fetch_func is None:
            return

        # Check if client is still alive
        if self._client_ref is not None:
            client = self._client_ref()
            if client is None or getattr(client, "_manual_cleanup", False):
                self._stop_event.set()
                return

        # Get list of stale entries (copy to avoid holding lock during refresh)
        stale_keys = []
        with self._lock:
            now = time.time()
            for key, entry in self._cache.items():
                if entry.is_stale(self._ttl_seconds):
                    # Only attempt refresh if not recently attempted
                    if (
                        entry.refresh_attempted_at is None
                        or (now - entry.refresh_attempted_at) > self._refresh_interval_seconds
                    ):
                        stale_keys.append(key)

        # Refresh stale entries (outside lock)
        for key in stale_keys:
            self._refresh_entry(key)

    def _refresh_entry(self, key: str) -> None:
        """Refresh a single cache entry."""
        if self._fetch_func is None:
            return

        # Mark refresh attempted
        with self._lock:
            if key in self._cache:
                self._cache[key].refresh_attempted_at = time.time()

        try:
            # Fetch fresh data
            fresh_value = self._fetch_func(key)

            # Update cache with fresh data
            self.set(key, fresh_value)
            logger.debug(f"Successfully refreshed cache entry: {key}")

        except Exception as e:
            # On refresh failure, keep serving stale data
            logger.debug(f"Failed to refresh cache entry {key}: {e}")
            # Entry remains in cache with stale data

    def shutdown(self) -> None:
        """Stop the background refresh thread and cleanup."""
        self._stop_event.set()
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=5.0)
            self._refresh_thread = None

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        try:
            self.shutdown()
        except Exception:
            pass
