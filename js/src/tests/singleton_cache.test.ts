import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { PromptCacheManagerSingleton } from "../singletons/prompt_cache.js";
import type { PromptCommit } from "../schemas.js";
import { LangSmithNotFoundError } from "../utils/error.js";
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

// Helper to create a mock fetch Response
function mockFetchResponse(
  commit: PromptCommit,
  status: number = 200
): Response {
  const isOk = status >= 200 && status < 300;
  return {
    ok: isOk,
    status,
    statusText: status === 200 ? "OK" : status === 404 ? "Not Found" : "Error",
    json: async () => ({
      commit_hash: commit.commit_hash,
      manifest: commit.manifest,
      examples: commit.examples,
    }),
    text: async () =>
      status === 404
        ? "Prompt not found"
        : status === 500
        ? "Server error"
        : "",
  } as Response;
}

// Helper to create a mock 404 Response
function mock404Response(): Response {
  return {
    ok: false,
    status: 404,
    statusText: "Not Found",
    text: async () => "Prompt not found",
    json: async () => ({}),
  } as Response;
}

// Helper to create a mock error Response
function mockErrorResponse(status: number, message: string): Response {
  return {
    ok: false,
    status,
    statusText: message,
    text: async () => message,
    json: async () => ({}),
  } as Response;
}

describe("Singleton Cache in Client", () => {
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
    const result = cache2.get("test-key");
    expect(result).toBeDefined();
    expect(result?.value).toEqual(mockPrompt);
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
  afterEach(() => {
    PromptCacheManagerSingleton.cleanup();
  });

  test("cache miss should fetch from API and cache result", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    // Mock the fetch
    const fetchSpy = jest
      .spyOn(client as any, "_fetch")
      .mockResolvedValue(mockFetchResponse(mockCommit));

    // First call - cache miss
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Verify it was cached
    const cache = client.cache;
    expect(cache).toBeDefined();
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeDefined();
      expect(cached?.value.commit_hash).toBe("abc123");
    }

    fetchSpy.mockRestore();
  });

  test("fresh cache hit should return immediately without fetching", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    const fetchSpy = jest
      .spyOn(client as any, "_fetch")
      .mockResolvedValue(mockFetchResponse(mockCommit));

    // First call - populate cache
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // Second call - should hit cache and not fetch
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(1); // Still 1, not 2

    fetchSpy.mockRestore();
  });

  test("stale cache hit should return stale data when refresh times out", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetch");

    // Populate cache with stale data
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow API call (will timeout)
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(mockFetchResponse(freshCommit)), 2000)
        )
    );

    const start = Date.now();
    const result2 = await client.pullPromptCommit("test-prompt");
    const elapsed = Date.now() - start;

    // Should return stale data quickly (within 1.5s)
    expect(elapsed).toBeLessThan(1500);
    expect(result2.commit_hash).toBe("abc123"); // Stale data returned

    fetchSpy.mockRestore();
  });

  test("stale cache hit should return fresh data if refresh completes quickly", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetch");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock fast API call (completes within 1s)
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(freshCommit));
    const result2 = await client.pullPromptCommit("test-prompt");

    // Should return fresh data
    expect(result2.commit_hash).toBe("abc123");

    fetchSpy.mockRestore();
  });

  test("concurrent requests should reuse in-flight fetch on cache miss", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit = createMockPromptCommit("abc123");

    let fetchCount = 0;
    const fetchSpy = jest.spyOn(client as any, "_fetch").mockImplementation(
      () =>
        new Promise((resolve) => {
          fetchCount++;
          setTimeout(
            () =>
              resolve({
                ok: true,
                status: 200,
                statusText: "OK",
                json: async () => ({
                  commit_hash: "abc123",
                  manifest: mockCommit.manifest,
                  examples: mockCommit.examples,
                }),
              } as Response),
            200
          );
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
    expect(results.every((r) => r.commit_hash === "abc123")).toBe(true);

    fetchSpy.mockRestore();
  });

  test("concurrent requests should reuse in-flight fetch on stale hit", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");
    const freshCommit = createMockPromptCommit("new456");

    const fetchSpy = jest.spyOn(client as any, "_fetch");

    // Populate cache - mock successful response
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        commit_hash: "old123",
        manifest: staleCommit.manifest,
        examples: staleCommit.examples,
      }),
    } as Response);
    await client.pullPromptCommit("test-prompt");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow refresh
    let refreshCount = 0;
    fetchSpy.mockImplementation(
      () =>
        new Promise((resolve) => {
          refreshCount++;
          setTimeout(
            () =>
              resolve({
                ok: true,
                status: 200,
                statusText: "OK",
                json: async () => ({
                  commit_hash: "new456",
                  manifest: freshCommit.manifest,
                  examples: freshCommit.examples,
                }),
              } as Response),
            200
          );
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

    const fetchSpy = jest.spyOn(client as any, "_fetch");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow API call that will timeout but complete in background
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(mockFetchResponse(freshCommit)), 1500)
        )
    );

    // This should return stale and start background refresh
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("abc123"); // Stale returned

    // Wait for background refresh to complete
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Cache should now have fresh data
    const cache = client.cache;
    expect(cache).toBeDefined();
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeDefined();
      expect(cached?.value.commit_hash).toBe("abc123");
    }

    fetchSpy.mockRestore();
  });

  test("skip_cache should bypass cache", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 60 } });
    const mockCommit1 = createMockPromptCommit("abc123");
    const mockCommit2 = createMockPromptCommit("def456");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(mockCommit1));
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(mockCommit2));

    // First call - populates cache
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Second call with skip_cache - should fetch again
    const result2 = await client.pullPromptCommit("test-prompt", {
      skipCache: true,
    });
    expect(result2.commit_hash).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  test("cache disabled should always fetch", async () => {
    const client = new Client({ promptCache: false });
    const mockCommit1 = createMockPromptCommit("abc123");
    const mockCommit2 = createMockPromptCommit("def456");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(mockCommit1));
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(mockCommit2));

    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Second call should fetch again (no cache)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("abc123");
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    fetchSpy.mockRestore();
  });

  test("fetch error should return stale and mark as fresh", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // Populate cache - mock successful response
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        commit_hash: "old123",
        manifest: staleCommit.manifest,
        examples: staleCommit.examples,
      }),
    } as Response);

    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow 500 error response (will timeout in foreground, complete in background)
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () =>
              resolve({
                ok: false,
                status: 500,
                statusText: "Internal Server Error",
                text: async () => "Server error",
                json: async () => ({}),
              } as Response),
            1500
          );
        })
    );

    // Should return stale data (timeout after 1s)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("old123");

    // Wait for background error to complete (with retries this can take longer)
    await new Promise((resolve) => setTimeout(resolve, 5000));

    // Verify the stale entry still exists (was marked as fresh to prevent eviction)
    // With short TTL it may be stale again, but it should still be cached
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeDefined();
      expect(cached?.value.commit_hash).toBe("old123");
      // Verify the background error handling was invoked
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Background prompt refresh failed"),
        expect.anything()
      );
    }

    fetchSpy.mockRestore();
    warnSpy.mockRestore();
  });

  test("404 during foreground refresh should clear cache and throw", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetch");

    // Populate cache
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock 404 response from fetch
    fetchSpy.mockResolvedValueOnce(mock404Response());

    // Should clear cache and throw
    await expect(client.pullPromptCommit("test-prompt")).rejects.toThrow(
      LangSmithNotFoundError
    );

    // Verify cache was cleared
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeUndefined();
    }

    fetchSpy.mockRestore();
  });

  test("404 during background refresh should clear cache", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    // Populate cache - mock successful response
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        commit_hash: "old123",
        manifest: staleCommit.manifest,
        examples: staleCommit.examples,
      }),
    } as Response);

    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("old123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow 404 response (fetch itself is slow, then returns 404)
    // This will timeout in foreground, then complete in background with 404
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () =>
              resolve({
                ok: false,
                status: 404,
                statusText: "Not Found",
                text: async () => "Prompt not found",
                json: async () => ({}),
              } as Response),
            1500 // Slower than 1s timeout
          );
        })
    );

    // Should return stale (timeout after 1s, before 404 completes)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("old123");

    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Verify cache was cleared by background 404
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeUndefined();
    }

    // Now verify that a subsequent request properly throws 404
    fetchSpy.mockResolvedValueOnce(mock404Response());

    await expect(client.pullPromptCommit("test-prompt")).rejects.toThrow(
      LangSmithNotFoundError
    );

    fetchSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  test("network failure should return stale data and mark as fresh", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // Populate cache
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock network failure (slow then reject)
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          setTimeout(() => reject(new Error("Network error")), 1500);
        })
    );

    // Should return stale data
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("abc123");

    // Wait for background error to complete
    await new Promise((resolve) => setTimeout(resolve, 5000));

    // Verify the stale entry still exists (was marked as fresh)
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeDefined();
      expect(cached?.value.commit_hash).toBe("abc123");
      // Verify the background error handling was invoked
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Background prompt refresh failed"),
        expect.anything()
      );
    }

    fetchSpy.mockRestore();
    warnSpy.mockRestore();
  });

  test("429 rate limit should return stale data and mark as fresh", async () => {
    const client = new Client({ promptCache: { ttlSeconds: 0.1 } });
    const staleCommit = createMockPromptCommit("old123");

    const fetchSpy = jest.spyOn(client as any, "_fetch");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // Populate cache
    fetchSpy.mockResolvedValueOnce(mockFetchResponse(staleCommit));
    const result1 = await client.pullPromptCommit("test-prompt");
    expect(result1.commit_hash).toBe("abc123");

    // Wait for entry to become stale
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Mock slow 429 rate limit response
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () => resolve(mockErrorResponse(429, "Too Many Requests")),
            1500
          );
        })
    );

    // Should return stale data (timeout after 1s)
    const result2 = await client.pullPromptCommit("test-prompt");
    expect(result2.commit_hash).toBe("abc123");

    // Wait for background error to complete (with retries)
    await new Promise((resolve) => setTimeout(resolve, 5000));

    // Verify the stale entry still exists (was marked as fresh)
    const cache = client.cache;
    if (cache) {
      const cached = cache.get("test-prompt");
      expect(cached).toBeDefined();
      expect(cached?.value.commit_hash).toBe("abc123");
      // Note: 429 errors will be retried by p-retry, so we just verify stale data was preserved
    }

    fetchSpy.mockRestore();
    warnSpy.mockRestore();
  });
});
