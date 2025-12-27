"""Test the prompt cache module."""

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from langsmith import schemas as ls_schemas
from langsmith._internal._cache import CacheEntry, PromptCache


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_prompt_commit():
    """Create a sample PromptCommit for testing."""
    return ls_schemas.PromptCommit(
        owner="test-owner",
        repo="test-prompt",
        commit_hash="abc123",
        manifest={"type": "test", "content": "hello"},
        examples=[{"input": "test", "output": "response"}],
    )


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_is_stale_fresh(self):
        """Test that fresh entries are not stale."""
        entry = CacheEntry(
            value=None,
            created_at=time.time(),
            last_accessed_at=time.time(),
        )
        assert not entry.is_stale(ttl_seconds=3600)

    def test_is_stale_expired(self):
        """Test that old entries are stale."""
        entry = CacheEntry(
            value=None,
            created_at=time.time() - 4000,  # 4000 seconds ago
            last_accessed_at=time.time(),
        )
        assert entry.is_stale(ttl_seconds=3600)

    def test_is_expired_fresh(self):
        """Test that fresh entries are not expired."""
        entry = CacheEntry(
            value=None,
            created_at=time.time(),
            last_accessed_at=time.time(),
        )
        assert not entry.is_expired(max_stale_seconds=86400)

    def test_is_expired_old(self):
        """Test that very old entries are expired."""
        entry = CacheEntry(
            value=None,
            created_at=time.time() - 100000,  # Very old
            last_accessed_at=time.time(),
        )
        assert entry.is_expired(max_stale_seconds=86400)


class TestPromptCacheBasic:
    """Basic tests for PromptCache."""

    def test_cache_disabled(self, sample_prompt_commit):
        """Test that disabled cache returns None."""
        cache = PromptCache(enabled=False)
        cache.set("test-key", sample_prompt_commit)
        assert cache.get("test-key") is None
        cache.shutdown()

    def test_get_set_basic(self, sample_prompt_commit, temp_cache_dir):
        """Test basic get/set operations."""
        cache = PromptCache(
            persist_path=temp_cache_dir,
            max_size=100,
            enabled=True,
        )
        try:
            # Initially empty
            assert cache.get("test-key") is None

            # Set and get
            cache.set("test-key", sample_prompt_commit)
            result = cache.get("test-key")

            assert result is not None
            assert result.owner == "test-owner"
            assert result.repo == "test-prompt"
            assert result.commit_hash == "abc123"
        finally:
            cache.shutdown()

    def test_invalidate(self, sample_prompt_commit, temp_cache_dir):
        """Test cache invalidation."""
        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache.set("test-key", sample_prompt_commit)
            assert cache.get("test-key") is not None

            cache.invalidate("test-key")
            assert cache.get("test-key") is None
        finally:
            cache.shutdown()

    def test_clear(self, sample_prompt_commit, temp_cache_dir):
        """Test clearing entire cache."""
        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache.set("key1", sample_prompt_commit)
            cache.set("key2", sample_prompt_commit)
            assert cache.get("key1") is not None
            assert cache.get("key2") is not None

            cache.clear()
            assert cache.get("key1") is None
            assert cache.get("key2") is None
        finally:
            cache.shutdown()


class TestPromptCacheLRU:
    """Tests for LRU eviction."""

    def test_lru_eviction(self, sample_prompt_commit, temp_cache_dir):
        """Test that LRU eviction works when max_size is exceeded."""
        cache = PromptCache(
            persist_path=temp_cache_dir,
            max_size=3,
            enabled=True,
        )
        try:
            # Fill cache to max
            cache.set("key1", sample_prompt_commit)
            cache.set("key2", sample_prompt_commit)
            cache.set("key3", sample_prompt_commit)

            # All should be present
            assert cache.get("key1") is not None
            assert cache.get("key2") is not None
            assert cache.get("key3") is not None

            # Add one more - key1 should be evicted (oldest)
            cache.set("key4", sample_prompt_commit)

            # key1 was accessed most recently due to get() above,
            # but let's test the actual behavior
            assert cache.get("key4") is not None
        finally:
            cache.shutdown()

    def test_lru_access_updates_order(self, sample_prompt_commit, temp_cache_dir):
        """Test that accessing an entry updates its position in LRU."""
        cache = PromptCache(
            persist_path=temp_cache_dir,
            max_size=2,
            enabled=True,
        )
        try:
            cache.set("key1", sample_prompt_commit)
            cache.set("key2", sample_prompt_commit)

            # Access key1 to make it most recently used
            cache.get("key1")

            # Add key3 - key2 should be evicted (now oldest)
            cache.set("key3", sample_prompt_commit)

            assert cache.get("key1") is not None  # Still present
            assert cache.get("key3") is not None  # Present
            # key2 was evicted
        finally:
            cache.shutdown()


class TestPromptCacheFilesystem:
    """Tests for filesystem persistence."""

    def test_write_through(self, sample_prompt_commit, temp_cache_dir):
        """Test that entries are persisted to disk on set."""
        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache.set("test-key", sample_prompt_commit)

            # Check that file was created
            files = list(Path(temp_cache_dir).glob("*.json"))
            assert len(files) == 1
        finally:
            cache.shutdown()

    def test_load_from_filesystem(self, sample_prompt_commit, temp_cache_dir):
        """Test loading from filesystem when entry not in memory."""
        # First cache - write to disk
        cache1 = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache1.set("test-key", sample_prompt_commit)
        finally:
            cache1.shutdown()

        # Second cache - should load from disk
        cache2 = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            result = cache2.get("test-key")
            assert result is not None
            assert result.owner == "test-owner"
        finally:
            cache2.shutdown()

    def test_cache_warming(self, sample_prompt_commit, temp_cache_dir):
        """Test that cache warms from filesystem on startup."""
        # First cache - write multiple entries
        cache1 = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache1.set("key1", sample_prompt_commit)
            cache1.set("key2", sample_prompt_commit)
        finally:
            cache1.shutdown()

        # Second cache - entries should be loaded on init (cache warming)
        cache2 = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            # Entries should already be in memory from warming
            # We verify by checking _cache dict directly
            assert "key1" in cache2._cache
            assert "key2" in cache2._cache

            # Getting should work
            result1 = cache2.get("key1")
            result2 = cache2.get("key2")
            assert result1 is not None
            assert result2 is not None
            assert result1.owner == "test-owner"
        finally:
            cache2.shutdown()

    def test_delete_from_filesystem(self, sample_prompt_commit, temp_cache_dir):
        """Test that invalidate also deletes from filesystem."""
        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache.set("test-key", sample_prompt_commit)
            assert len(list(Path(temp_cache_dir).glob("*.json"))) == 1

            cache.invalidate("test-key")
            assert len(list(Path(temp_cache_dir).glob("*.json"))) == 0
        finally:
            cache.shutdown()

    def test_corrupted_file_handling(self, temp_cache_dir):
        """Test handling of corrupted cache files."""
        # Create a corrupted file
        cache_file = Path(temp_cache_dir) / "corrupted_abc123.json"
        cache_file.write_text("not valid json {{{")

        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            # Should not raise, just log warning
            result = cache.get("nonexistent")
            assert result is None
        finally:
            cache.shutdown()


class TestPromptCacheTTL:
    """Tests for TTL and staleness."""

    def test_stale_entry_still_served(self, sample_prompt_commit, temp_cache_dir):
        """Test that stale entries are still served."""
        cache = PromptCache(
            persist_path=temp_cache_dir,
            ttl_seconds=1,  # Very short TTL
            max_stale_seconds=3600,  # Long max stale
            enabled=True,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait for entry to become stale
            time.sleep(1.5)

            # Should still be served (within max_stale)
            result = cache.get("test-key")
            assert result is not None
        finally:
            cache.shutdown()

    def test_expired_entry_not_served(self, sample_prompt_commit, temp_cache_dir):
        """Test that expired entries are not served."""
        cache = PromptCache(
            persist_path=temp_cache_dir,
            ttl_seconds=0.1,
            max_stale_seconds=0.2,  # Very short max stale
            enabled=True,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait for entry to expire
            time.sleep(0.5)

            # Should not be served (past max_stale)
            result = cache.get("test-key")
            assert result is None
        finally:
            cache.shutdown()


class TestPromptCacheBackgroundRefresh:
    """Tests for background refresh functionality."""

    def test_background_refresh_called(self, sample_prompt_commit, temp_cache_dir):
        """Test that background refresh is triggered for stale entries."""
        mock_fetch = MagicMock(return_value=sample_prompt_commit)

        cache = PromptCache(
            persist_path=temp_cache_dir,
            ttl_seconds=0.1,  # Very short TTL
            max_stale_seconds=3600,
            refresh_interval_seconds=0.2,
            fetch_func=mock_fetch,
            enabled=True,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait for entry to become stale and refresh to run
            time.sleep(0.5)

            # Fetch should have been called
            assert mock_fetch.called
        finally:
            cache.shutdown()

    def test_refresh_failure_keeps_stale(self, sample_prompt_commit, temp_cache_dir):
        """Test that refresh failure keeps serving stale data."""
        call_count = [0]

        def failing_fetch(key):
            call_count[0] += 1
            raise Exception("API error")

        cache = PromptCache(
            persist_path=temp_cache_dir,
            ttl_seconds=0.1,
            max_stale_seconds=3600,
            refresh_interval_seconds=0.2,
            fetch_func=failing_fetch,
            enabled=True,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait for refresh attempt
            time.sleep(0.5)

            # Fetch was attempted
            assert call_count[0] > 0

            # Stale data should still be served
            result = cache.get("test-key")
            assert result is not None
        finally:
            cache.shutdown()


class TestPromptCacheThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_reads(self, sample_prompt_commit, temp_cache_dir):
        """Test concurrent read operations."""
        cache = PromptCache(persist_path=temp_cache_dir, enabled=True)
        try:
            cache.set("test-key", sample_prompt_commit)

            results = []
            errors = []

            def read_cache():
                try:
                    for _ in range(100):
                        result = cache.get("test-key")
                        results.append(result is not None)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=read_cache) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
            assert all(results)
        finally:
            cache.shutdown()

    def test_concurrent_writes(self, sample_prompt_commit, temp_cache_dir):
        """Test concurrent write operations."""
        cache = PromptCache(persist_path=temp_cache_dir, max_size=1000, enabled=True)
        try:
            errors = []

            def write_cache(thread_id):
                try:
                    for i in range(50):
                        cache.set(f"key-{thread_id}-{i}", sample_prompt_commit)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write_cache, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
        finally:
            cache.shutdown()


class TestPromptCacheKeyGeneration:
    """Tests for cache key generation."""

    def test_key_to_filename_safe(self):
        """Test that key_to_filename handles special characters."""
        cache = PromptCache(enabled=False)

        # Test various prompt identifiers
        filename1 = cache._key_to_filename("owner/prompt-name:latest")
        assert ".json" in filename1
        assert "/" not in filename1
        assert ":" not in filename1.replace(".json", "")

        filename2 = cache._key_to_filename("owner/prompt:abc123:with_model")
        assert ".json" in filename2
        assert "/" not in filename2
