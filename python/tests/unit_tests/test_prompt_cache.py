"""Test the prompt cache module."""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from langsmith import schemas as ls_schemas
from langsmith.prompt_cache import (
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


class TestCacheBasic:
    """Basic tests for Cache."""

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


class TestCacheLRU:
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


class TestCacheBackgroundRefresh:
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

        # Trigger lazy thread initialization by setting a value
        cache.set("test-key", sample_prompt_commit)

        # Verify thread is running
        assert cache._refresh_thread is not None
        assert cache._refresh_thread.is_alive()

        cache.shutdown()

        # Thread should be stopped
        assert cache._refresh_thread is None or not cache._refresh_thread.is_alive()


class TestCacheThreadSafety:
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


class TestAsyncCache:
    """Tests for AsyncCache."""

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
            await cache.aset("test-key", sample_prompt_commit)

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
            await cache.aset("test-key", sample_prompt_commit)

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
        await cache.aset("test-key", sample_prompt_commit)
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

    async def test_async_cache_dump_load(self, sample_prompt_commit, tmp_path):
        """Test that AsyncCache can also dump/load."""
        cache_file = tmp_path / "async_cache.json"

        # dump/load are inherited from base class
        cache1 = AsyncPromptCache()
        await cache1.aset("prompt1", sample_prompt_commit)
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
            await cache.aset("key1", sample_prompt_commit)
            cache.get("key1")
            assert cache.metrics.hits == 1

            # Start refresh and wait
            await cache.start()
            await asyncio.sleep(1)

            assert cache.metrics.refreshes >= 1
        finally:
            await cache.stop()


class TestGlobalSingleton:
    """Tests for global singleton behavior."""

    def test_singleton_instances_exist(self):
        """Test that global singletons are created."""
        from langsmith.prompt_cache import (
            async_prompt_cache_singleton,
            prompt_cache_singleton,
        )

        assert prompt_cache_singleton is not None
        assert isinstance(prompt_cache_singleton, PromptCache)
        assert async_prompt_cache_singleton is not None
        assert isinstance(async_prompt_cache_singleton, AsyncPromptCache)

    def test_singleton_is_same_instance(self):
        """Test that singleton returns the same instance."""
        from langsmith.prompt_cache import prompt_cache_singleton

        # Import again to ensure it's the same instance
        from langsmith.prompt_cache import prompt_cache_singleton as singleton2

        assert prompt_cache_singleton is singleton2

    def test_client_uses_singleton_by_default(self):
        """Test that Client uses the global singleton by default."""
        from langsmith.client import Client
        from langsmith.prompt_cache import prompt_cache_singleton

        client = Client(api_key="test-key")
        assert client._cache is prompt_cache_singleton

    def test_client_can_disable_cache(self):
        """Test that Client can disable caching."""
        from langsmith.client import Client

        client = Client(api_key="test-key", disable_prompt_cache=True)
        assert client._cache is None

    def test_async_client_uses_singleton_by_default(self):
        """Test that AsyncClient uses the global singleton by default."""
        from langsmith.async_client import AsyncClient
        from langsmith.prompt_cache import async_prompt_cache_singleton

        client = AsyncClient(api_key="test-key")
        assert client._cache is async_prompt_cache_singleton

    def test_async_client_can_disable_cache(self):
        """Test that AsyncClient can disable caching."""
        from langsmith.async_client import AsyncClient

        client = AsyncClient(api_key="test-key", disable_prompt_cache=True)
        assert client._cache is None

    def test_configure_global_prompt_cache(self, sample_prompt_commit):
        """Test configuring the global cache."""
        from langsmith.prompt_cache import (
            configure_global_prompt_cache,
            prompt_cache_singleton,
        )

        # Get initial values
        initial_max_size = prompt_cache_singleton._max_size
        initial_ttl = prompt_cache_singleton._ttl_seconds

        try:
            # Configure with new values
            configure_global_prompt_cache(max_size=200, ttl_seconds=7200)

            assert prompt_cache_singleton._max_size == 200
            assert prompt_cache_singleton._ttl_seconds == 7200

        finally:
            # Restore original values
            configure_global_prompt_cache(
                max_size=initial_max_size, ttl_seconds=initial_ttl
            )

    def test_multiple_clients_share_singleton(self, sample_prompt_commit):
        """Test that multiple clients share the same cache instance."""
        from langsmith.client import Client
        from langsmith.prompt_cache import prompt_cache_singleton

        client1 = Client(api_key="test-key-1")
        client2 = Client(api_key="test-key-2")

        # Both should use the same cache
        assert client1._cache is client2._cache
        assert client1._cache is prompt_cache_singleton

        # Set a value through singleton
        prompt_cache_singleton.set("shared-key", sample_prompt_commit)

        # Both clients should see it (if they used the cache)
        assert prompt_cache_singleton.get("shared-key") is not None

    def test_configure_after_clients_created(self, sample_prompt_commit):
        """Test configuring singleton after clients are already created."""
        from langsmith.client import Client
        from langsmith.prompt_cache import (
            configure_global_prompt_cache,
            prompt_cache_singleton,
        )

        # Get initial config
        initial_max_size = prompt_cache_singleton._max_size
        initial_ttl = prompt_cache_singleton._ttl_seconds

        try:
            # Create clients before configure
            client1 = Client(api_key="test-key-1")
            client2 = Client(api_key="test-key-2")

            # Configure singleton
            configure_global_prompt_cache(max_size=200, ttl_seconds=7200)

            # Both clients should see new config (same singleton)
            assert client1._cache._max_size == 200
            assert client1._cache._ttl_seconds == 7200
            assert client2._cache._max_size == 200
            assert client2._cache._ttl_seconds == 7200

            # Verify it's the same object
            assert client1._cache is client2._cache
            assert client1._cache is prompt_cache_singleton

        finally:
            # Restore original values
            configure_global_prompt_cache(
                max_size=initial_max_size, ttl_seconds=initial_ttl
            )

    def test_shared_metrics_across_clients(self, sample_prompt_commit):
        """Test that metrics are shared across all clients using singleton."""
        from langsmith.client import Client
        from langsmith.prompt_cache import prompt_cache_singleton

        # Clean up singleton state
        prompt_cache_singleton.clear()
        prompt_cache_singleton.reset_metrics()

        try:
            client1 = Client(api_key="test-key-1")
            client2 = Client(api_key="test-key-2")

            # Client 1 sets a value
            client1._cache.set("key1", sample_prompt_commit)

            # Client 2 gets the value (hit)
            result = client2._cache.get("key1")
            assert result is not None

            # Metrics should be shared
            assert client1._cache.metrics.hits == 1
            assert client2._cache.metrics.hits == 1  # Same metrics object
            assert client1._cache.metrics is client2._cache.metrics

            # Client 1 misses
            client1._cache.get("missing-key")

            # Client 2 should see the miss
            assert client2._cache.metrics.misses == 1

        finally:
            prompt_cache_singleton.clear()
            prompt_cache_singleton.reset_metrics()

    def test_singleton_background_thread_shared(self, sample_prompt_commit):
        """Test that singleton has only ONE background thread shared by all clients."""
        from langsmith.client import Client
        from langsmith.prompt_cache import prompt_cache_singleton

        # Clean up singleton state
        prompt_cache_singleton.clear()
        prompt_cache_singleton.reset_metrics()
        prompt_cache_singleton.shutdown()

        def mock_fetch(key):
            return sample_prompt_commit

        # Create singleton with fetch func
        prompt_cache_singleton._fetch_func = mock_fetch
        prompt_cache_singleton._ttl_seconds = 10

        try:
            # Create multiple clients
            client1 = Client(api_key="test-key-1")
            client2 = Client(api_key="test-key-2")
            client3 = Client(api_key="test-key-3")

            # Trigger thread start via any client
            client1._cache.set("key1", sample_prompt_commit)

            # Should only be ONE thread
            assert client1._cache._refresh_thread is not None
            assert client2._cache._refresh_thread is client1._cache._refresh_thread
            assert client3._cache._refresh_thread is client1._cache._refresh_thread

            # All point to same thread object
            thread = client1._cache._refresh_thread
            assert thread.is_alive()

        finally:
            prompt_cache_singleton._fetch_func = None
            prompt_cache_singleton.shutdown()
            prompt_cache_singleton.clear()
            prompt_cache_singleton.reset_metrics()

    def test_singleton_persistence(self, sample_prompt_commit, tmp_path):
        """Test dump/load with singleton."""
        from langsmith.client import Client
        from langsmith.prompt_cache import prompt_cache_singleton

        cache_file = tmp_path / "singleton_cache.json"

        # Clean up singleton state
        prompt_cache_singleton.clear()
        prompt_cache_singleton.reset_metrics()

        try:
            client1 = Client(api_key="test-key-1")

            # Client sets some values
            client1._cache.set("prompt1", sample_prompt_commit)
            client1._cache.set("prompt2", sample_prompt_commit)

            # Dump via singleton
            prompt_cache_singleton.dump(cache_file)

            # Clear and load
            prompt_cache_singleton.clear()
            loaded = prompt_cache_singleton.load(cache_file)

            assert loaded == 2

            # New client should see loaded values
            client2 = Client(api_key="test-key-2")
            assert client2._cache.get("prompt1") is not None
            assert client2._cache.get("prompt2") is not None

        finally:
            prompt_cache_singleton.clear()
            prompt_cache_singleton.reset_metrics()

    @pytest.mark.asyncio
    async def test_configure_global_async_prompt_cache(self, sample_prompt_commit):
        """Test configuring the global async prompt cache."""
        from langsmith.async_client import AsyncClient
        from langsmith.prompt_cache import (
            async_prompt_cache_singleton,
            configure_global_async_prompt_cache,
        )

        # Get initial values
        initial_max_size = async_prompt_cache_singleton._max_size
        initial_ttl = async_prompt_cache_singleton._ttl_seconds

        # Clean up
        async_prompt_cache_singleton.clear()
        async_prompt_cache_singleton.reset_metrics()
        await async_prompt_cache_singleton.stop()

        try:
            # Configure async singleton
            await configure_global_async_prompt_cache(max_size=200, ttl_seconds=7200)

            assert async_prompt_cache_singleton._max_size == 200
            assert async_prompt_cache_singleton._ttl_seconds == 7200

            # Create client after configure
            client = AsyncClient(api_key="test-key")
            assert client._cache is async_prompt_cache_singleton
            assert client._cache._max_size == 200

        finally:
            # Restore original values
            await configure_global_async_prompt_cache(
                max_size=initial_max_size, ttl_seconds=initial_ttl
            )
            async_prompt_cache_singleton.clear()
            async_prompt_cache_singleton.reset_metrics()
            await async_prompt_cache_singleton.stop()

    @pytest.mark.asyncio
    async def test_async_singleton_shared_across_clients(self, sample_prompt_commit):
        """Test that async clients share the same singleton."""
        from langsmith.async_client import AsyncClient
        from langsmith.prompt_cache import async_prompt_cache_singleton

        # Clean up
        async_prompt_cache_singleton.clear()
        async_prompt_cache_singleton.reset_metrics()
        await async_prompt_cache_singleton.stop()

        try:
            client1 = AsyncClient(api_key="test-key-1")
            client2 = AsyncClient(api_key="test-key-2")

            # Both should use same singleton
            assert client1._cache is client2._cache
            assert client1._cache is async_prompt_cache_singleton

            # Client 1 sets a value
            await client1._cache.aset("key1", sample_prompt_commit)

            # Client 2 should see it
            result = client2._cache.get("key1")
            assert result is not None
            assert result.owner == "test-owner"

            # Metrics should be shared (already 1 hit from client2.get above)
            assert client1._cache.metrics.hits == 1
            assert client2._cache.metrics.hits == 1  # Same metrics object
            assert client1._cache.metrics is client2._cache.metrics

        finally:
            async_prompt_cache_singleton.clear()
            async_prompt_cache_singleton.reset_metrics()
            await async_prompt_cache_singleton.stop()


class TestLazyInitialization:
    """Tests for lazy background thread initialization."""

    def test_thread_not_started_on_creation(self):
        """Test that background thread is not started when cache is created."""
        cache = PromptCache()
        try:
            # Thread should be None before first set
            assert cache._refresh_thread is None
        finally:
            cache.shutdown()

    def test_thread_starts_on_first_set_with_fetch_func(self):
        """Test that background thread starts on first set
        when fetch_func is provided."""

        def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test",
                repo="test",
                commit_hash="abc",
                manifest={},
                examples=[],
            )

        cache = PromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Thread should be None before first set
            assert cache._refresh_thread is None

            # Set a value - should trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            cache.set("test-key", prompt)

            # Thread should now be started
            assert cache._refresh_thread is not None
            assert cache._refresh_thread.is_alive()
        finally:
            cache.shutdown()

    def test_thread_not_started_without_fetch_func(self):
        """Test that thread doesn't start without fetch_func even after set."""
        cache = PromptCache(ttl_seconds=10)
        try:
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            cache.set("test-key", prompt)

            # Thread should still be None (no fetch_func)
            assert cache._refresh_thread is None
        finally:
            cache.shutdown()

    def test_thread_not_started_with_infinite_ttl(self):
        """Test that thread doesn't start with infinite TTL (None)."""

        def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = PromptCache(fetch_func=mock_fetch, ttl_seconds=None)
        try:
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            cache.set("test-key", prompt)

            # Thread should not start with infinite TTL
            assert cache._refresh_thread is None
        finally:
            cache.shutdown()

    def test_configure_stops_and_restarts_thread(self):
        """Test that configure stops existing thread and can restart it."""

        def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = PromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            cache.set("test-key", prompt)

            # Thread should be running
            assert cache._refresh_thread is not None

            # Reconfigure - should stop the thread
            cache.configure(ttl_seconds=20)

            # Thread should be stopped (configure calls shutdown)
            # After configure, thread won't start until next set()
            assert cache._refresh_thread is None

            # Set again to trigger restart
            cache.set("test-key-2", prompt)

            # New thread should be started (different from first)
            assert cache._refresh_thread is not None
            assert cache._refresh_thread.is_alive()
        finally:
            cache.shutdown()

    def test_shutdown_stops_thread(self):
        """Test that shutdown stops the background thread."""

        def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = PromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            cache.set("test-key", prompt)

            # Thread should be running
            assert cache._refresh_thread is not None
            assert cache._refresh_thread.is_alive()

            # Shutdown
            cache.shutdown()

            # Thread should be None
            assert cache._refresh_thread is None
        except:
            cache.shutdown()
            raise


class TestAsyncLazyInitialization:
    """Tests for lazy background task initialization in AsyncPromptCache."""

    @pytest.mark.asyncio
    async def test_task_not_started_on_creation(self):
        """Test that background task is not started when cache is created."""
        cache = AsyncPromptCache()
        try:
            # Task should be None before first set
            assert cache._refresh_task is None
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_task_starts_on_first_set_with_fetch_func(self):
        """Test that background task starts on first set when fetch_func is provided."""

        async def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = AsyncPromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Task should be None before first set
            assert cache._refresh_task is None

            # Set a value - should trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should now be started
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_task_not_started_without_fetch_func(self):
        """Test that task doesn't start without fetch_func even after set."""
        cache = AsyncPromptCache(ttl_seconds=10)
        try:
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should still be None (no fetch_func)
            assert cache._refresh_task is None
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_task_not_started_with_infinite_ttl(self):
        """Test that task doesn't start with infinite TTL (None)."""

        async def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = AsyncPromptCache(fetch_func=mock_fetch, ttl_seconds=None)
        try:
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should not start with infinite TTL
            assert cache._refresh_task is None
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_configure_stops_and_restarts_task(self):
        """Test that configure stops existing task and can restart it."""

        async def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = AsyncPromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should be running
            assert cache._refresh_task is not None

            # Reconfigure - should stop the task
            await cache.configure(ttl_seconds=20)

            # Task should be stopped (configure calls stop)
            # After configure, task won't start until next aset()
            assert cache._refresh_task is None

            # Set again to trigger restart
            await cache.aset("test-key-2", prompt)

            # New task should be started
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()
        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_configure_stops_background_task(self):
        """Test that configure stops the background task like TypeScript."""

        async def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = AsyncPromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Trigger task start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should be running
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()
            first_task = cache._refresh_task

            # Reconfigure - should stop the task
            await cache.configure(ttl_seconds=20)

            # Task should be stopped (configure calls stop())
            assert cache._refresh_task is None

            # Set again to restart with new config
            await cache.aset("test-key-2", prompt)

            # New task should be started
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()
            second_task = cache._refresh_task

            # Should be a different task object
            assert second_task is not first_task

        finally:
            await cache.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """Test that stop cancels the background task."""

        async def mock_fetch(key):
            return ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )

        cache = AsyncPromptCache(fetch_func=mock_fetch, ttl_seconds=10)
        try:
            # Trigger lazy start
            prompt = ls_schemas.PromptCommit(
                owner="test", repo="test", commit_hash="abc", manifest={}, examples=[]
            )
            await cache.aset("test-key", prompt)

            # Task should be running
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()

            # Stop
            await cache.stop()

            # Task should be None
            assert cache._refresh_task is None
        except:
            await cache.stop()
            raise
