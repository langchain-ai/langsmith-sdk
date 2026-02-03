"""Test the singleton async cache behavior with AsyncClient."""

import pytest

from langsmith import AsyncClient
from langsmith import schemas as ls_schemas
from langsmith.prompt_cache_singleton import AsyncPromptCacheManagerSingleton


@pytest.fixture(autouse=True)
def cleanup_singleton():
    """Clean up the singleton before and after each test."""
    AsyncPromptCacheManagerSingleton.cleanup()
    yield
    AsyncPromptCacheManagerSingleton.cleanup()


def create_mock_prompt_commit(hash_value: str) -> ls_schemas.PromptCommit:
    """Create a mock PromptCommit for testing."""
    return ls_schemas.PromptCommit(
        owner="test-owner",
        repo="test-prompt",
        commit_hash=hash_value,
        manifest={"type": "test", "content": "hello"},
        examples=[],
    )


class TestSingletonAsyncCacheInClient:
    """Tests for singleton async cache behavior in AsyncClient."""

    def test_cache_enabled_by_default(self):
        """Cache should be enabled by default (lazy initialized on access)."""
        client = AsyncClient(api_key="test")
        cache = client.cache

        # Cache should be enabled by default
        assert cache is not None
        assert AsyncPromptCacheManagerSingleton.is_initialized()

    def test_multiple_clients_share_same_cache(self):
        """Multiple clients should share the same cache instance."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        client2 = AsyncClient(api_key="test", prompt_cache=True)

        cache1 = client1.cache
        cache2 = client2.cache

        # Should be the exact same instance
        assert cache1 is cache2

    def test_cache_shared_across_instances(self):
        """Cache data should be shared across client instances."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        client2 = AsyncClient(api_key="test", prompt_cache=True)

        cache1 = client1.cache
        cache2 = client2.cache

        # Add data via client1's cache
        test_commit = create_mock_prompt_commit("test123")
        cache1.set("test-key", test_commit)

        # Should be accessible via client2's cache
        assert cache2.get("test-key") == test_commit
        assert cache2.get("test-key").commit_hash == "test123"

    def test_first_client_config_used(self):
        """First client configuration should initialize the singleton."""
        client1 = AsyncClient(
            api_key="test",
            prompt_cache={"max_size": 50, "ttl_seconds": 1800},
        )

        cache1 = client1.cache
        assert cache1 is not None

        # Second client with different config should use the same instance
        client2 = AsyncClient(
            api_key="test",
            prompt_cache={"max_size": 100, "ttl_seconds": 3600},
        )

        cache2 = client2.cache

        # Should be the same instance
        assert cache1 is cache2

    def test_cache_disabled_client(self):
        """Client with cache disabled should not access the singleton."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        client2 = AsyncClient(api_key="test", prompt_cache=False)

        assert client1.cache is not None
        assert client2.cache is None

    @pytest.mark.asyncio
    async def test_aclose_does_not_stop_global_cache(self):
        """Client aclose should not stop the global cache."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        cache = client1.cache

        assert cache is not None

        # Close client
        await client1.aclose()

        # Cache should still be accessible from another client
        client2 = AsyncClient(api_key="test", prompt_cache=True)
        assert client2.cache is cache

    def test_singleton_cleanup_stops_cache(self):
        """AsyncPromptCacheManagerSingleton.cleanup should stop and clear the cache."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        cache1 = client1.cache

        assert cache1 is not None

        # Add something to the cache
        cache1.set("test-key", create_mock_prompt_commit("test"))
        assert cache1.get("test-key") is not None

        # Cleanup the singleton
        AsyncPromptCacheManagerSingleton.cleanup()

        # New client should get a fresh cache
        client2 = AsyncClient(api_key="test", prompt_cache=True)
        cache2 = client2.cache

        assert cache2 is not None

        # Should be a new instance
        assert cache2 is not cache1

        # Should be empty
        assert cache2.get("test-key") is None

    def test_cache_lazy_initialization(self):
        """Cache should lazy initialize only when accessed."""
        # Creating client should not initialize cache
        client = AsyncClient(api_key="test")
        assert not AsyncPromptCacheManagerSingleton.is_initialized()

        # Accessing cache property should initialize it
        cache = client.cache
        assert cache is not None
        assert AsyncPromptCacheManagerSingleton.is_initialized()

    def test_metrics_shared_across_clients(self):
        """Cache metrics should be shared across clients."""
        client1 = AsyncClient(api_key="test", prompt_cache=True)
        client2 = AsyncClient(api_key="test", prompt_cache=True)

        cache1 = client1.cache
        cache2 = client2.cache

        # Initial metrics
        assert cache1.metrics.hits == 0
        assert cache1.metrics.misses == 0

        # Miss from client1
        cache1.get("nonexistent")
        assert cache1.metrics.misses == 1
        assert cache2.metrics.misses == 1  # Same metrics object

        # Set and hit from client2
        cache2.set("key", create_mock_prompt_commit("test"))
        cache2.get("key")
        assert cache1.metrics.hits == 1
        assert cache2.metrics.hits == 1

    def test_cache_config_with_dict(self):
        """Test cache configuration with dictionary."""
        client = AsyncClient(
            api_key="test",
            prompt_cache={
                "max_size": 200,
                "ttl_seconds": 7200,
                "refresh_interval_seconds": 120,
            },
        )

        cache = client.cache
        assert cache is not None
        assert AsyncPromptCacheManagerSingleton.is_initialized()

    def test_cache_config_defaults(self):
        """Test cache with default configuration."""
        client = AsyncClient(api_key="test", prompt_cache=True)

        cache = client.cache
        assert cache is not None
        assert AsyncPromptCacheManagerSingleton.is_initialized()
