import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { PromptCacheManagerSingleton } from "../singletons/prompt_cache.js";
import type { PromptCommit } from "../schemas.js";
import { mockClient } from "./utils/mock_client.js";

// Helper to create a mock PromptCommit
function createMockPromptCommit(name: string): PromptCommit {
  return {
    owner: "test-owner",
    repo: name,
    commit_hash: "abc123",
    manifest: { template: `Hello from ${name}` },
    examples: [],
  };
}

describe("Singleton Cache in Client", () => {
  // Clean up the singleton before each test
  beforeEach(() => {
    PromptCacheManagerSingleton.cleanup();
  });

  afterEach(() => {
    PromptCacheManagerSingleton.cleanup();
  });

  test("cache should be enabled by default", () => {
    const client = new Client();
    const cache = client.cache;

    // Cache should be enabled by default (lazy initialized on access)
    expect(cache).toBeDefined();
    expect(PromptCacheManagerSingleton.isInitialized()).toBe(true);
  });

  test("multiple clients should share the same cache instance", () => {
    const client1 = new Client({ promptCache: true });
    const client2 = new Client({ promptCache: true });

    const cache1 = client1.cache;
    const cache2 = client2.cache;

    // Both clients should have cache enabled
    expect(cache1).toBeDefined();
    expect(cache2).toBeDefined();

    // They should be the exact same instance
    expect(cache1).toBe(cache2);
  });

  test("cache should be shared across client instances", () => {
    const client1 = new Client({ promptCache: true });
    const client2 = new Client({ promptCache: true });

    const cache1 = client1.cache;
    const cache2 = client2.cache;

    if (!cache1 || !cache2) {
      throw new Error("Cache should be defined");
    }

    // Set a value through client1's cache
    const mockPrompt = createMockPromptCommit("shared-test");
    cache1.set("test-key", mockPrompt);

    // Should be accessible from client2's cache
    expect(cache2.get("test-key")).toEqual(mockPrompt);
  });

  test("first client configuration should initialize the singleton", () => {
    const client1 = new Client({
      promptCache: {
        maxSize: 50,
        ttlSeconds: 1800,
      },
    });

    const cache1 = client1.cache;
    expect(cache1).toBeDefined();

    // Second client with different config should use the same instance
    const client2 = new Client({
      promptCache: {
        maxSize: 100, // Different config, but should be ignored
        ttlSeconds: 3600,
      },
    });

    const cache2 = client2.cache;

    // Should be the same instance
    expect(cache1).toBe(cache2);
  });

  test("client with cache disabled should not access the singleton", () => {
    const client1 = new Client({ promptCache: true });
    const client2 = new Client({ promptCache: false });

    expect(client1.cache).toBeDefined();
    expect(client2.cache).toBeUndefined();
  });

  test("PromptCacheManagerSingleton.cleanup should stop and clear the cache", () => {
    const client1 = new Client({ promptCache: true });
    const cache1 = client1.cache;

    expect(cache1).toBeDefined();
    if (!cache1) throw new Error("Cache should be defined");

    // Add something to the cache
    cache1.set("test-key", createMockPromptCommit("test"));
    expect(cache1.size).toBe(1);

    // Cleanup the singleton
    PromptCacheManagerSingleton.cleanup();

    // New client should get a fresh cache
    const client2 = new Client({ promptCache: true });
    const cache2 = client2.cache;

    expect(cache2).toBeDefined();
    if (!cache2) throw new Error("Cache should be defined");

    // Should be a new instance
    expect(cache2).not.toBe(cache1);

    // Should be empty
    expect(cache2.size).toBe(0);
  });

  test("metrics should be shared across clients", () => {
    const client1 = new Client({ promptCache: true });
    const client2 = new Client({ promptCache: true });

    const cache1 = client1.cache;
    const cache2 = client2.cache;

    if (!cache1 || !cache2) {
      throw new Error("Cache should be defined");
    }

    // Initial metrics
    expect(cache1.metrics.hits).toBe(0);
    expect(cache1.metrics.misses).toBe(0);

    // Perform operations through client1
    cache1.set("key1", createMockPromptCommit("test1"));
    cache1.get("key1"); // Hit
    cache1.get("key2"); // Miss

    // Metrics should be visible through client2
    expect(cache2.metrics.hits).toBe(1);
    expect(cache2.metrics.misses).toBe(1);
  });

  test("cache should lazy initialize only when accessed", () => {
    // Creating client should not initialize cache
    const client = new Client();
    expect(PromptCacheManagerSingleton.isInitialized()).toBe(false);

    // Accessing cache property should initialize it
    const cache = client.cache;
    expect(cache).toBeDefined();
    expect(PromptCacheManagerSingleton.isInitialized()).toBe(true);
  });

  test("cache should lazy initialize on first prompt pull", async () => {
    const { client, callSpy } = mockClient();

    // Cache should not be initialized yet
    expect(PromptCacheManagerSingleton.isInitialized()).toBe(false);

    // Mock the response for prompt pulling
    callSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve(""),
      json: () =>
        Promise.resolve({
          commit_hash: "abc123",
          manifest: { template: "test" },
          examples: [],
        }),
    } as Response);

    // Pull a prompt - this should trigger cache initialization
    const result = await client.pullPromptCommit("test-prompt");

    // Cache should now be initialized after the prompt pull
    expect(PromptCacheManagerSingleton.isInitialized()).toBe(true);
    expect(result.commit_hash).toBe("abc123");
    
    const cache = client.cache;
    expect(cache).toBeDefined();
  });
});

describe("Pull-Through Refresh Pattern", () => {
  // Clean up the singleton before and after each test
  beforeEach(() => {
    PromptCacheManagerSingleton.cleanup();
  });

  afterEach(() => {
    PromptCacheManagerSingleton.cleanup();
  });

  test("cache miss should fetch from API and cache result", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    // Mock the fetch
    const fetchSpy = jest
      .spyOn(client as any, "_fetchPromptFromApi")
      .mockResolvedValue(mockCommit);

    // First call - cache miss
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Verify it was cached
    const cache = client.cache;
    expect(cache).toBeDefined();
    if (cache) {
      const cached = cache.get("test-prompt:latest:false");
      expect(cached).toBeDefined();
      expect(cached?.value.repo).toBe("abc123");
    }

    fetchSpy.mockRestore();
  });

  test("fresh cache hit should return immediately without fetching", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    const fetchSpy = jest
      .spyOn(client as any, "_fetchPromptFromApi")
      .mockResolvedValue(mockCommit);

    // First call - populate cache
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Second call - should hit cache and not fetch
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.repo).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1); // Still 1, not 2

    fetchSpy.mockRestore();
  });

  test("stale cache hit should return stale data when refresh times out", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache with stale data
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow API call (will timeout)
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(freshCommit), 2000)
        )
    );

    const start = Date.now();
    const result2 = await client.pullPromptCommit("test-prompt");
    const elapsed = Date.now() - start;

    // Should return stale data quickly (within 1.5s)
    expect(elapsed).toBeLessThan(1500);
    expect(result2.repo).toBe("old123"); // Stale data returned

    fetchSpy.mockRestore();
  });

  test("stale cache hit should return fresh data if refresh completes quickly", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock fast API call (completes within 1s)
    fetchSpy.mockResolvedValueOnce(freshCommit);
    const result2 = await client.pullPromptCommit("test-prompt");

    // Should return fresh data
    expect(result2.repo).toBe("new456");

    fetchSpy.mockRestore();
  });

  test("concurrent requests should reuse in-flight fetch on cache miss", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    let fetchCount = 0;
    const fetchSpy = jest
      .spyOn(client as any, "_fetchPromptFromApi")
      .mockImplementation(
        () =>
          new Promise((resolve) => {
            fetchCount++;
            setTimeout(() => resolve(mockCommit), 200);
          })
      );

    // Launch 5 concurrent requests
    const results = await Promise.all([
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
    ]);

    // Should have only fetched once (reused in-flight fetch)
    expect(fetchCount).toBe(1);
    expect(results).toHaveLength(5);
    expect(results.every((r) => r.repo === "abc123")).toBe(true);

    fetchSpy.mockRestore();
  });

  test("concurrent requests should reuse in-flight fetch on stale hit", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    await client.pullPromptCommit("test-prompt");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow refresh
    let refreshCount = 0;
    fetchSpy.mockImplementation(
      () =>
        new Promise((resolve) => {
          refreshCount++;
          setTimeout(() => resolve(freshCommit), 200);
        })
    );

    // Launch 5 concurrent requests for stale key
    const results = await Promise.all([
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
      client.pullPromptCommit("test-prompt"),
    ]);

    // Should have only started one refresh (reused in-flight fetch)
    expect(refreshCount).toBe(1);
    expect(results).toHaveLength(5);

    fetchSpy.mockRestore();
  });

  test("background refresh should update cache after timeout", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow API call that will timeout but complete in background
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(freshCommit), 1500)
        )
    );

    // This should return stale and start background refresh
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.repo).toBe("old123"); // Stale returned

    // Wait for background refresh to complete
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Cache should now have fresh data
    const cache = client.cache;
    expect(cache).toBeDefined();
    if (cache) {
      const cached = cache.get("test-prompt:latest:false");
      expect(cached).toBeDefined();
      expect(cached?.value.repo).toBe("new456");
    }

    fetchSpy.mockRestore();
  });

  test("skip_cache should bypass cache", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit1 = createMockPromptCommit("abc123");
    const mockCommit2 = createMockPromptCommit("def456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");
    fetchSpy.mockResolvedValueOnce(mockCommit1);
    fetchSpy.mockResolvedValueOnce(mockCommit2);

    // First call - populates cache
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("abc123");

    // Second call with skip_cache - should fetch again
    const result2 = await client.pullPromptCommit("test-prompt", {
      skipCache: true,
    });
    expect(result2.repo).toBe("def456");
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  test("cache disabled should always fetch", async () => {
    const client = new Client({ promptCache: false });
    const mockCommit1 = createMockPromptCommit("abc123");
    const mockCommit2 = createMockPromptCommit("def456");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");
    fetchSpy.mockResolvedValueOnce(mockCommit1);
    fetchSpy.mockResolvedValueOnce(mockCommit2);

    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("abc123");

    // Second call should fetch again (no cache)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.repo).toBe("def456");
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  test("fetch error should return stale and mark as fresh", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock fetch error
    fetchSpy.mockRejectedValueOnce(new Error("Network error"));

    // Should return stale data and mark as fresh to prevent retry storms
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.repo).toBe("old123");

    // Verify it was marked fresh (no longer stale)
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt:latest:false");
      expect(cached?.isStale).toBe(false);
    }

    fetchSpy.mockRestore();
  });

  test("404 during foreground refresh should clear cache and throw", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock 404 error (prompt was deleted)
    const notFoundError = new Error("Prompt not found");
    (notFoundError as any).name = "LangSmithNotFoundError";
    fetchSpy.mockRejectedValueOnce(notFoundError);

    // Should clear cache and throw
    await expect(client.pullPromptCommit("test-prompt")).rejects.toThrow(
      "Prompt not found"
    );

    // Verify cache was cleared
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt:latest:false");
      expect(cached).toBeUndefined();
    }

    fetchSpy.mockRestore();
  });

  test("404 during background refresh should clear cache", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(staleCommit);
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.repo).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow 404 (will timeout in foreground, complete in background)
    const notFoundError = new Error("Prompt not found");
    (notFoundError as any).name = "LangSmithNotFoundError";
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((_, reject) =>
          setTimeout(() => reject(notFoundError), 1500)
        )
    );

    // Should return stale (background 404 pending)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.repo).toBe("old123");

    // Wait for background refresh to complete
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Verify cache was cleared by background refresh
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt:latest:false");
      expect(cached).toBeUndefined();
    }

    fetchSpy.mockRestore();
  });
});
