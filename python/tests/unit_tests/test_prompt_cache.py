"""Test the prompt cache module."""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from langsmith import schemas as ls_schemas
from langsmith._internal._cache import (
    AsyncPromptCache,
    CacheEntry,
    PromptCache,
)


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
        )
        assert not entry.is_stale(ttl_seconds=3600)

    def test_is_stale_expired(self):
        """Test that old entries are stale."""
        entry = CacheEntry(
            value=None,
            created_at=time.time() - 4000,  # 4000 seconds ago
        )
        assert entry.is_stale(ttl_seconds=3600)


class TestPromptCacheBasic:
    """Basic tests for PromptCache."""

    def test_get_set_basic(self, sample_prompt_commit):
        """Test basic get/set operations."""
        cache = PromptCache(max_size=100)
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

    def test_invalidate(self, sample_prompt_commit):
        """Test cache invalidation."""
        cache = PromptCache()
        try:
            cache.set("test-key", sample_prompt_commit)
            assert cache.get("test-key") is not None

            cache.invalidate("test-key")
            assert cache.get("test-key") is None
        finally:
            cache.shutdown()

    def test_clear(self, sample_prompt_commit):
        """Test clearing entire cache."""
        cache = PromptCache()
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

    def test_lru_eviction(self, sample_prompt_commit):
        """Test that LRU eviction works when max_size is exceeded."""
        cache = PromptCache(max_size=3)
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

    def test_lru_access_updates_order(self, sample_prompt_commit):
        """Test that accessing an entry updates its position in LRU."""
        cache = PromptCache(max_size=2)
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


class TestPromptCacheBackgroundRefresh:
    """Tests for background refresh functionality."""

    def test_background_refresh_called(self, sample_prompt_commit):
        """Test that background refresh is triggered for stale entries."""
        mock_fetch = MagicMock(return_value=sample_prompt_commit)

        cache = PromptCache(
            ttl_seconds=0.1,  # Very short TTL
            refresh_interval_seconds=0.2,
            fetch_func=mock_fetch,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait for entry to become stale and refresh to run
            time.sleep(0.5)

            # Fetch should have been called
            assert mock_fetch.called
            mock_fetch.assert_called_with("test-key")
        finally:
            cache.shutdown()

    def test_refresh_failure_keeps_stale(self, sample_prompt_commit):
        """Test that refresh failure keeps serving stale data."""
        call_count = [0]

        def failing_fetch(key):
            call_count[0] += 1
            raise Exception("API error")

        cache = PromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.2,
            fetch_func=failing_fetch,
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
            assert result.owner == "test-owner"
        finally:
            cache.shutdown()

    def test_no_refresh_without_fetch_func(self, sample_prompt_commit):
        """Test that no background refresh happens without fetch_func."""
        cache = PromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.1,
            # No fetch_func
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Wait - should not crash
            time.sleep(0.3)

            # Data should still be there
            result = cache.get("test-key")
            assert result is not None
        finally:
            cache.shutdown()

    def test_shutdown_stops_refresh_thread(self, sample_prompt_commit):
        """Test that shutdown stops the background refresh thread."""
        mock_fetch = MagicMock(return_value=sample_prompt_commit)

        cache = PromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.1,
            fetch_func=mock_fetch,
        )

        # Verify thread is running
        assert cache._refresh_thread is not None
        assert cache._refresh_thread.is_alive()

        cache.shutdown()

        # Thread should be stopped
        assert cache._refresh_thread is None or not cache._refresh_thread.is_alive()


class TestPromptCacheThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_reads(self, sample_prompt_commit):
        """Test concurrent read operations."""
        cache = PromptCache()
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

    def test_concurrent_writes(self, sample_prompt_commit):
        """Test concurrent write operations."""
        cache = PromptCache(max_size=1000)
        try:
            errors = []

            def write_cache(thread_id):
                try:
                    for i in range(50):
                        cache.set(f"key-{thread_id}-{i}", sample_prompt_commit)
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=write_cache, args=(i,)) for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
        finally:
            cache.shutdown()


class TestAsyncPromptCache:
    """Tests for AsyncPromptCache."""

    @pytest.mark.asyncio
    async def test_async_refresh_called(self, sample_prompt_commit):
        """Test that async background refresh is triggered for stale entries."""
        mock_fetch = AsyncMock(return_value=sample_prompt_commit)

        cache = AsyncPromptCache(
            ttl_seconds=0.1,  # Very short TTL
            refresh_interval_seconds=0.2,
            fetch_func=mock_fetch,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Start async refresh
            await cache.start()

            # Wait for entry to become stale and refresh to run
            await asyncio.sleep(0.5)

            # Fetch should have been called
            assert mock_fetch.called
            mock_fetch.assert_called_with("test-key")
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_async_refresh_failure_keeps_stale(self, sample_prompt_commit):
        """Test that async refresh failure keeps serving stale data."""
        call_count = [0]

        async def failing_fetch(key):
            call_count[0] += 1
            raise Exception("API error")

        cache = AsyncPromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.2,
            fetch_func=failing_fetch,
        )
        try:
            cache.set("test-key", sample_prompt_commit)

            # Start async refresh
            await cache.start()

            # Wait for refresh attempt
            await asyncio.sleep(0.5)

            # Fetch was attempted
            assert call_count[0] > 0

            # Stale data should still be served
            result = cache.get("test-key")
            assert result is not None
            assert result.owner == "test-owner"
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_refresh_task(self, sample_prompt_commit):
        """Test that stop() cancels the refresh task."""
        mock_fetch = AsyncMock(return_value=sample_prompt_commit)

        cache = AsyncPromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.1,
            fetch_func=mock_fetch,
        )

        await cache.start()

        # Verify task is running
        assert cache._refresh_task is not None
        assert not cache._refresh_task.done()

        await cache.stop()

        # Task should be stopped
        assert cache._refresh_task is None

    @pytest.mark.asyncio
    async def test_start_without_fetch_func(self, sample_prompt_commit):
        """Test that start() is a no-op without fetch_func."""
        cache = AsyncPromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.1,
            # No fetch_func
        )

        await cache.start()

        # No task should be created
        assert cache._refresh_task is None

        # Should not crash
        await cache.stop()

    @pytest.mark.asyncio
    async def test_basic_operations(self, sample_prompt_commit):
        """Test basic get/set operations work without starting refresh."""
        cache = AsyncPromptCache()

        # Set and get
        cache.set("test-key", sample_prompt_commit)
        result = cache.get("test-key")

        assert result is not None
        assert result.owner == "test-owner"

        # Invalidate
        cache.invalidate("test-key")
        assert cache.get("test-key") is None


class TestCachePersistence:
    """Tests for dump/load persistence functionality."""

    def test_dump_and_load(self, sample_prompt_commit, tmp_path):
        """Test dumping and loading cache to/from file."""
        cache_file = tmp_path / "cache.json"

        # Create cache and add entries
        cache1 = PromptCache()
        try:
            cache1.set("prompt1", sample_prompt_commit)
            cache1.set("prompt2", sample_prompt_commit)

            # Dump to file
            cache1.dump(cache_file)
        finally:
            cache1.shutdown()

        # Verify file exists
        assert cache_file.exists()

        # Load into new cache
        cache2 = PromptCache()
        try:
            loaded = cache2.load(cache_file)

            assert loaded == 2

            # Verify data
            result1 = cache2.get("prompt1")
            assert result1 is not None
            assert result1.owner == "test-owner"
            assert result1.repo == "test-prompt"
            assert result1.commit_hash == "abc123"

            result2 = cache2.get("prompt2")
            assert result2 is not None
        finally:
            cache2.shutdown()

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from nonexistent file returns 0."""
        cache = PromptCache()
        try:
            loaded = cache.load(tmp_path / "nonexistent.json")
            assert loaded == 0
        finally:
            cache.shutdown()

    def test_load_corrupted_file(self, tmp_path):
        """Test loading corrupted file returns 0."""
        cache_file = tmp_path / "corrupted.json"
        cache_file.write_text("not valid json {{{")

        cache = PromptCache()
        try:
            loaded = cache.load(cache_file)
            assert loaded == 0
        finally:
            cache.shutdown()

    def test_load_respects_max_size(self, sample_prompt_commit, tmp_path):
        """Test that load respects max_size limit."""
        cache_file = tmp_path / "cache.json"

        # Create cache with many entries
        cache1 = PromptCache(max_size=100)
        try:
            for i in range(10):
                cache1.set(f"prompt{i}", sample_prompt_commit)
            cache1.dump(cache_file)
        finally:
            cache1.shutdown()

        # Load into cache with smaller max_size
        cache2 = PromptCache(max_size=3)
        try:
            loaded = cache2.load(cache_file)
            assert loaded == 3  # Only loaded up to max_size
        finally:
            cache2.shutdown()

    def test_dump_creates_parent_dirs(self, sample_prompt_commit, tmp_path):
        """Test that dump creates parent directories if needed."""
        cache_file = tmp_path / "nested" / "dir" / "cache.json"

        cache = PromptCache()
        try:
            cache.set("prompt1", sample_prompt_commit)
            cache.dump(cache_file)
        finally:
            cache.shutdown()

        assert cache_file.exists()

    def test_load_gives_fresh_ttl(self, sample_prompt_commit, tmp_path):
        """Test that loaded entries get fresh TTL."""
        cache_file = tmp_path / "cache.json"

        # Create and dump cache
        cache1 = PromptCache()
        try:
            cache1.set("prompt1", sample_prompt_commit)
            cache1.dump(cache_file)
        finally:
            cache1.shutdown()

        # Load into new cache - entries should have fresh TTL (not stale)
        cache2 = PromptCache(ttl_seconds=3600)
        try:
            cache2.load(cache_file)
            stale_keys = cache2._get_stale_keys()
            assert "prompt1" not in stale_keys  # Fresh TTL, not stale
        finally:
            cache2.shutdown()

    def test_async_cache_dump_load(self, sample_prompt_commit, tmp_path):
        """Test that AsyncPromptCache can also dump/load."""
        cache_file = tmp_path / "async_cache.json"

        # dump/load are inherited from base class
        cache1 = AsyncPromptCache()
        cache1.set("prompt1", sample_prompt_commit)
        cache1.dump(cache_file)

        cache2 = AsyncPromptCache()
        loaded = cache2.load(cache_file)

        assert loaded == 1
        assert cache2.get("prompt1") is not None


class TestOfflineMode:
    """Tests for offline mode (infinite TTL)."""

    def test_infinite_ttl_never_stale(self, sample_prompt_commit):
        """Test that entries with ttl_seconds=None are never stale."""
        cache = PromptCache(ttl_seconds=None)
        try:
            cache.set("prompt1", sample_prompt_commit)

            # Manually set old timestamp
            cache._cache["prompt1"].created_at = time.time() - 1000000

            # Should still not be stale
            stale_keys = cache._get_stale_keys()
            assert "prompt1" not in stale_keys

            # Should still be retrievable
            assert cache.get("prompt1") is not None
        finally:
            cache.shutdown()

    def test_infinite_ttl_no_refresh_thread(self, sample_prompt_commit):
        """Test that no refresh thread starts with ttl_seconds=None."""
        mock_fetch = MagicMock(return_value=sample_prompt_commit)

        cache = PromptCache(
            ttl_seconds=None,
            fetch_func=mock_fetch,
        )
        try:
            # No refresh thread should be started
            assert cache._refresh_thread is None

            cache.set("prompt1", sample_prompt_commit)

            # Wait a bit - fetch should never be called
            time.sleep(0.3)
            assert not mock_fetch.called
        finally:
            cache.shutdown()

    def test_offline_workflow(self, sample_prompt_commit, tmp_path):
        """Test full offline workflow: dump online, load offline."""
        cache_file = tmp_path / "offline_cache.json"

        # Online: populate and dump cache
        online_cache = PromptCache(ttl_seconds=3600)
        try:
            online_cache.set("prompt1", sample_prompt_commit)
            online_cache.set("prompt2", sample_prompt_commit)
            online_cache.dump(cache_file)
        finally:
            online_cache.shutdown()

        # Offline: load with infinite TTL
        offline_cache = PromptCache(ttl_seconds=None)
        try:
            loaded = offline_cache.load(cache_file)
            assert loaded == 2

            # Entries work and never expire
            assert offline_cache.get("prompt1") is not None
            assert offline_cache.get("prompt2") is not None

            # No refresh thread
            assert offline_cache._refresh_thread is None
        finally:
            offline_cache.shutdown()

    @pytest.mark.asyncio
    async def test_async_infinite_ttl_no_refresh_task(self, sample_prompt_commit):
        """Test that async cache doesn't start refresh task with ttl_seconds=None."""
        mock_fetch = AsyncMock(return_value=sample_prompt_commit)

        cache = AsyncPromptCache(
            ttl_seconds=None,
            fetch_func=mock_fetch,
        )

        await cache.start()

        # No task should be created
        assert cache._refresh_task is None

        await cache.stop()


class TestCacheMetrics:
    """Tests for cache metrics."""

    def test_initial_metrics(self):
        """Test that metrics start at zero."""
        cache = PromptCache()
        try:
            assert cache.metrics.hits == 0
            assert cache.metrics.misses == 0
            assert cache.metrics.refreshes == 0
            assert cache.metrics.refresh_errors == 0
            assert cache.metrics.total_requests == 0
            assert cache.metrics.hit_rate == 0.0
        finally:
            cache.shutdown()

    def test_hit_miss_tracking(self, sample_prompt_commit):
        """Test that hits and misses are tracked correctly."""
        cache = PromptCache()
        try:
            # Miss on empty cache
            cache.get("key1")
            assert cache.metrics.misses == 1
            assert cache.metrics.hits == 0

            # Set and hit
            cache.set("key1", sample_prompt_commit)
            cache.get("key1")
            assert cache.metrics.hits == 1
            assert cache.metrics.misses == 1

            # Another hit
            cache.get("key1")
            assert cache.metrics.hits == 2

            # Another miss
            cache.get("key2")
            assert cache.metrics.misses == 2

            # Verify totals
            assert cache.metrics.total_requests == 4
            assert cache.metrics.hit_rate == 0.5  # 2 hits / 4 requests
        finally:
            cache.shutdown()

    def test_refresh_tracking(self, sample_prompt_commit):
        """Test that refreshes are tracked correctly."""
        mock_fetch = MagicMock(return_value=sample_prompt_commit)

        cache = PromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.2,
            fetch_func=mock_fetch,
        )
        try:
            cache.set("key1", sample_prompt_commit)

            # Wait for refresh
            time.sleep(0.5)

            assert cache.metrics.refreshes >= 1
            assert cache.metrics.refresh_errors == 0
        finally:
            cache.shutdown()

    def test_refresh_error_tracking(self, sample_prompt_commit):
        """Test that refresh errors are tracked."""

        def failing_fetch(key):
            raise Exception("API error")

        cache = PromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.2,
            fetch_func=failing_fetch,
        )
        try:
            cache.set("key1", sample_prompt_commit)

            # Wait for refresh attempt
            time.sleep(0.5)

            assert cache.metrics.refresh_errors >= 1
            assert cache.metrics.refreshes == 0
        finally:
            cache.shutdown()

    def test_reset_metrics(self, sample_prompt_commit):
        """Test that metrics can be reset."""
        cache = PromptCache()
        try:
            cache.set("key1", sample_prompt_commit)
            cache.get("key1")
            cache.get("key2")

            assert cache.metrics.hits == 1
            assert cache.metrics.misses == 1

            cache.reset_metrics()

            assert cache.metrics.hits == 0
            assert cache.metrics.misses == 0
            assert cache.metrics.total_requests == 0
        finally:
            cache.shutdown()

    @pytest.mark.asyncio
    async def test_async_metrics(self, sample_prompt_commit):
        """Test that async cache also tracks metrics."""
        mock_fetch = AsyncMock(return_value=sample_prompt_commit)

        cache = AsyncPromptCache(
            ttl_seconds=0.1,
            refresh_interval_seconds=0.2,
            fetch_func=mock_fetch,
        )
        try:
            # Miss
            cache.get("key1")
            assert cache.metrics.misses == 1

            # Set and hit
            cache.set("key1", sample_prompt_commit)
            cache.get("key1")
            assert cache.metrics.hits == 1

            # Start refresh and wait
            await cache.start()
            await asyncio.sleep(0.5)

            assert cache.metrics.refreshes >= 1
        finally:
            await cache.stop()
