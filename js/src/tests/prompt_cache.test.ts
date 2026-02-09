/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { jest } from "@jest/globals";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  PromptCache,
  promptCacheSingleton,
  configureGlobalPromptCache,
} from "../utils/prompt_cache/index.js";
import { Client } from "../client.js";
import type { PromptCommit } from "../schemas.js";

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

describe("Cache", () => {
  describe("basic operations", () => {
    test("should return undefined for missing keys", () => {
      const cache = new PromptCache();
      expect(
        cache.get("missing-key", async () => createMockPromptCommit("missing"))
      ).toBeUndefined();
      cache.stop();
    });

    test("should get and set values", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt, async () => prompt);
      expect(cache.get("test-key", async () => prompt)).toEqual(prompt);
      cache.stop();
    });

    test("should invalidate entries", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt, async () => prompt);
      cache.invalidate("test-key");
      expect(cache.get("test-key", async () => prompt)).toBeUndefined();
      cache.stop();
    });

    test("should clear all entries", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache.set("key2", createMockPromptCommit("test2"), async () =>
        createMockPromptCommit("test2")
      );
      expect(cache.size).toBe(2);
      cache.clear();
      expect(cache.size).toBe(0);
      cache.stop();
    });
  });

  describe("LRU eviction", () => {
    test("should evict oldest entry when max size reached", () => {
      const cache = new PromptCache({
        maxSize: 2,
        ttlSeconds: null,
      });

      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache.set("key2", createMockPromptCommit("test2"), async () =>
        createMockPromptCommit("test2")
      );
      cache.set("key3", createMockPromptCommit("test3"), async () =>
        createMockPromptCommit("test3")
      );

      expect(cache.size).toBe(2);
      expect(
        cache.get("key1", async () => createMockPromptCommit("test1"))
      ).toBeUndefined(); // Evicted
      expect(
        cache.get("key2", async () => createMockPromptCommit("test2"))
      ).toBeDefined();
      expect(
        cache.get("key3", async () => createMockPromptCommit("test3"))
      ).toBeDefined();
      cache.stop();
    });

    test("should update LRU order on access", () => {
      const cache = new PromptCache({
        maxSize: 2,
        ttlSeconds: null,
      });

      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache.set("key2", createMockPromptCommit("test2"), async () =>
        createMockPromptCommit("test2")
      );

      // Access key1 to make it recently used
      cache.get("key1", async () => createMockPromptCommit("test1"));

      // Add key3 - should evict key2 (least recently used)
      cache.set("key3", createMockPromptCommit("test3"), async () =>
        createMockPromptCommit("test3")
      );

      expect(
        cache.get("key1", async () => createMockPromptCommit("test1"))
      ).toBeDefined();
      expect(
        cache.get("key2", async () => createMockPromptCommit("test2"))
      ).toBeUndefined(); // Evicted
      expect(
        cache.get("key3", async () => createMockPromptCommit("test3"))
      ).toBeDefined();
      cache.stop();
    });
  });

  describe("metrics", () => {
    test("should track hits and misses", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );

      cache.get("key1", async () => createMockPromptCommit("test1")); // Hit
      cache.get("key1", async () => createMockPromptCommit("test1")); // Hit
      cache.get("missing", async () => createMockPromptCommit("missing")); // Miss

      expect(cache.metrics.hits).toBe(2);
      expect(cache.metrics.misses).toBe(1);
      expect(cache.totalRequests).toBe(3);
      expect(cache.hitRate).toBeCloseTo(0.667, 2);
      cache.stop();
    });

    test("should reset metrics", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache.get("key1", async () => createMockPromptCommit("test1"));
      cache.get("missing", async () => createMockPromptCommit("missing"));

      cache.resetMetrics();

      expect(cache.metrics.hits).toBe(0);
      expect(cache.metrics.misses).toBe(0);
      expect(cache.metrics.refreshes).toBe(0);
      expect(cache.metrics.refreshErrors).toBe(0);
      cache.stop();
    });
  });

  describe("persistence", () => {
    let tempDir: string;

    beforeEach(() => {
      tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "prompt-cache-test-"));
    });

    afterEach(() => {
      fs.rmSync(tempDir, { recursive: true, force: true });
    });

    test("should dump and load cache", () => {
      const cachePath = path.join(tempDir, "cache.json");
      const cache1 = new PromptCache({ ttlSeconds: null });

      cache1.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache1.set("key2", createMockPromptCommit("test2"), async () =>
        createMockPromptCommit("test2")
      );
      cache1.dump(cachePath);
      cache1.stop();

      const cache2 = new PromptCache({ ttlSeconds: null });
      const loaded = cache2.load(cachePath);

      expect(loaded).toBe(2);
      expect(
        cache2!.get("key1", async () => createMockPromptCommit("test1"))
      ).toBeDefined();
      expect(
        cache2!.get("key2", async () => createMockPromptCommit("test2"))
      ).toBeDefined();
      cache2.stop();
    });

    test("should return 0 for non-existent file", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      const loaded = cache.load("/non/existent/path.json");
      expect(loaded).toBe(0);
      cache.stop();
    });

    test("should return 0 for corrupted file", () => {
      const cachePath = path.join(tempDir, "corrupted.json");
      fs.writeFileSync(cachePath, "not valid json{{{");

      const cache = new PromptCache({ ttlSeconds: null });
      const loaded = cache.load(cachePath);
      expect(loaded).toBe(0);
      cache.stop();
    });

    test("should respect max size when loading", () => {
      const cachePath = path.join(tempDir, "cache.json");
      const cache1 = new PromptCache({
        maxSize: 10,
        ttlSeconds: null,
      });

      for (let i = 0; i < 5; i++) {
        cache1.set(`key${i}`, createMockPromptCommit(`test${i}`), async () =>
          createMockPromptCommit(`test${i}`)
        );
      }
      cache1.dump(cachePath);
      cache1.stop();

      const cache2 = new PromptCache({
        maxSize: 3,
        ttlSeconds: null,
      });
      const loaded = cache2.load(cachePath);

      expect(loaded).toBe(3);
      expect(cache2.size).toBe(3);
      cache2.stop();
    });

    test("should create parent directories", () => {
      const cachePath = path.join(tempDir, "nested", "dir", "cache.json");
      const cache = new PromptCache({ ttlSeconds: null });

      cache.set("key1", createMockPromptCommit("test1"), async () =>
        createMockPromptCommit("test1")
      );
      cache.dump(cachePath);

      expect(fs.existsSync(cachePath)).toBe(true);
      cache.stop();
    });
  });

  describe("background refresh", () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test("should not start refresh when ttlSeconds is null", () => {
      const fetchFunc = jest.fn();
      const cache = new PromptCache({
        ttlSeconds: null, // Infinite TTL
      });

      cache.set(
        "key1",
        createMockPromptCommit("test1"),
        fetchFunc as () => Promise<PromptCommit>
      );

      // Advance time significantly
      jest.advanceTimersByTime(120_000);

      expect(fetchFunc).not.toHaveBeenCalled();
      cache.stop();
    });

    test("should refresh stale entries", async () => {
      const refreshedPrompt = createMockPromptCommit("refreshed");
      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockResolvedValue(refreshedPrompt);

      const cache = new PromptCache({
        ttlSeconds: 1, // 1 second TTL
        refreshIntervalSeconds: 1, // Check every second
      });

      cache.set("key1", createMockPromptCommit("original"), fetchFunc);

      // Advance past TTL and refresh interval
      jest.advanceTimersByTime(2000);

      // Allow the async refresh to complete
      await Promise.resolve();

      expect(fetchFunc).toHaveBeenCalledWith();
      cache.stop();
    });

    test("should track refresh errors", async () => {
      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockRejectedValue(new Error("Network error"));

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
      });

      cache.set("key1", createMockPromptCommit("test1"), fetchFunc);

      // Advance past TTL and refresh interval
      jest.advanceTimersByTime(2000);

      // Allow the async refresh to complete
      await Promise.resolve();

      expect(cache.metrics.refreshErrors).toBeGreaterThan(0);
      cache.stop();
    });

    test("should keep serving stale data on 500 errors", async () => {
      const originalPrompt = createMockPromptCommit("original");
      const error = new Error("500 Internal Server Error");
      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockRejectedValue(error);

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
      });

      // Set initial value
      cache.set("key1", originalPrompt, fetchFunc);

      // Get it before it's stale
      const beforeStale = cache.get("key1", fetchFunc);
      expect(beforeStale).toEqual(originalPrompt);

      // Advance past TTL to make it stale
      jest.advanceTimersByTime(2000);
      await Promise.resolve();

      // Fetch should have been attempted and failed
      expect(fetchFunc).toHaveBeenCalled();
      expect(cache.metrics.refreshErrors).toBeGreaterThan(0);

      // Should still serve the stale data
      const afterError = cache.get("key1", fetchFunc);
      expect(afterError).toEqual(originalPrompt);
      expect(cache.metrics.hits).toBeGreaterThan(0);

      cache.stop();
    });

    test("should continue refresh loop after 500 errors", async () => {
      const originalPrompt = createMockPromptCommit("original");
      const updatedPrompt = createMockPromptCommit("updated");

      // First call fails with 500, second call succeeds
      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockRejectedValueOnce(new Error("500 Internal Server Error"))
        .mockResolvedValueOnce(updatedPrompt);

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
      });

      cache.set("key1", originalPrompt, fetchFunc);

      // First refresh attempt (will fail)
      jest.advanceTimersByTime(2000);
      await Promise.resolve();

      expect(fetchFunc).toHaveBeenCalledTimes(1);
      expect(cache.metrics.refreshErrors).toBe(1);

      // Should still have original data
      expect(cache.get("key1", fetchFunc)).toEqual(originalPrompt);

      // Second refresh attempt (will succeed)
      jest.advanceTimersByTime(1000);
      await Promise.resolve();

      expect(fetchFunc).toHaveBeenCalledTimes(2);
      expect(cache.metrics.refreshes).toBe(1);

      // Should now have updated data
      expect(cache.get("key1", fetchFunc)).toEqual(updatedPrompt);

      cache.stop();
    });

    test("should stop refresh on stop()", () => {
      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockResolvedValue(createMockPromptCommit("test"));

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
      });

      cache.set("key1", createMockPromptCommit("test1"), fetchFunc);
      cache.stop();

      // Advance time after stopping
      jest.advanceTimersByTime(10000);

      // Fetch should not be called since we stopped the cache
      expect(fetchFunc).not.toHaveBeenCalled();
    });
  });

  describe("offline mode", () => {
    let tempDir: string;

    beforeEach(() => {
      tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "prompt-cache-offline-"));
    });

    afterEach(() => {
      fs.rmSync(tempDir, { recursive: true, force: true });
    });

    test("should work in full offline mode", () => {
      const cachePath = path.join(tempDir, "offline-cache.json");

      // Step 1: Online - populate and dump cache
      const onlineCache = new PromptCache({
        ttlSeconds: 3600,
      });
      const prompt1 = createMockPromptCommit("test1");
      const prompt2 = createMockPromptCommit("test2");
      onlineCache.set("prompt1", prompt1, async () => prompt1);
      onlineCache.set("prompt2", prompt2, async () => prompt2);
      onlineCache.dump(cachePath);
      onlineCache.stop();

      // Step 2: Offline - load from file with infinite TTL
      const offlineCache = new PromptCache({
        ttlSeconds: null, // Never expire
      });
      const loaded = offlineCache.load(cachePath);

      expect(loaded).toBe(2);
      expect(offlineCache.get("prompt1", async () => prompt1)).toBeDefined();
      expect(offlineCache.get("prompt2", async () => prompt2)).toBeDefined();

      // Verify no refresh happens
      expect(offlineCache.metrics.refreshes).toBe(0);
      offlineCache.stop();
    });
  });
});

describe("Global Singleton", () => {
  afterEach(() => {
    // Clean up singleton after each test
    promptCacheSingleton.clear();
    promptCacheSingleton.resetMetrics();
  });

  describe("singleton instance", () => {
    test("should have a global singleton", () => {
      expect(promptCacheSingleton).toBeDefined();
      expect(promptCacheSingleton).toBeInstanceOf(PromptCache);
    });

    test("should have default configuration", () => {
      expect(promptCacheSingleton.size).toBe(0);
      // Check private properties through bracket notation
      expect((promptCacheSingleton as any).maxSize).toBe(100);
      expect((promptCacheSingleton as any).ttlSeconds).toBe(5 * 60); // 5 minutes
    });
  });

  describe("Client integration", () => {
    test("Client should use singleton by default", () => {
      const client = new Client({ apiKey: "test-key" });
      expect((client as any)._promptCache).toBe(promptCacheSingleton);
    });

    test("Client can disable caching", () => {
      const client = new Client({
        apiKey: "test-key",
        disablePromptCache: true,
      });
      expect((client as any)._promptCache).toBeUndefined();
    });

    test("Multiple clients share the same cache", () => {
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });

      expect((client1 as any)._promptCache).toBe((client2 as any)._promptCache);
      expect((client1 as any)._promptCache).toBe(promptCacheSingleton);
    });

    test("Clients share cached values", () => {
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });

      const prompt = createMockPromptCommit("shared-prompt");
      promptCacheSingleton.set("shared-key", prompt, async () => prompt);

      // Both clients should see the cached value
      expect((client1 as any)._promptCache?.get("shared-key")).toEqual(prompt);
      expect((client2 as any)._promptCache?.get("shared-key")).toEqual(prompt);
    });
  });
});

describe("cache disabled with maxSize: 0", () => {
  test("should not cache when maxSize is 0", () => {
    const cache = new PromptCache({ maxSize: 0 });
    const prompt = createMockPromptCommit("test");
    const refreshFunc = async () => prompt;

    // Set should do nothing
    cache.set("key1", prompt, refreshFunc);

    // Get should always return undefined
    const result = cache.get("key1", refreshFunc);
    expect(result).toBeUndefined();

    // No metrics should be tracked when disabled
    expect(cache.metrics.hits).toBe(0);
    expect(cache.metrics.misses).toBe(0);

    // Cache should be empty
    expect(cache.size).toBe(0);

    cache.stop();
  });

  test("should not track metrics when cache is disabled", () => {
    const cache = new PromptCache({ maxSize: 0 });
    const prompt = createMockPromptCommit("test");
    const refreshFunc = async () => prompt;

    // Multiple operations
    cache.set("key1", prompt, refreshFunc);
    cache.get("key1", refreshFunc);
    cache.get("key2", refreshFunc);
    cache.set("key2", prompt, refreshFunc);
    cache.get("key1", refreshFunc);

    // No metrics should be tracked
    expect(cache.metrics.hits).toBe(0);
    expect(cache.metrics.misses).toBe(0);
    expect(cache.totalRequests).toBe(0);

    cache.stop();
  });

  test("should disable cache when reconfigured to maxSize: 0", () => {
    const cache = new PromptCache({ maxSize: 10 });
    const prompt = createMockPromptCommit("test");
    const refreshFunc = async () => prompt;

    // Add entries
    cache.set("key1", prompt, refreshFunc);
    cache.set("key2", prompt, refreshFunc);

    // Verify they exist
    expect(cache.get("key1", refreshFunc)).toBeDefined();
    expect(cache.get("key2", refreshFunc)).toBeDefined();
    expect(cache.size).toBe(2);

    // Reconfigure to disable cache
    cache.configure({ maxSize: 0 });

    // Now all gets should return undefined
    expect(cache.get("key1", refreshFunc)).toBeUndefined();
    expect(cache.get("key2", refreshFunc)).toBeUndefined();

    // Sets should do nothing
    cache.set("key3", prompt, refreshFunc);
    expect(cache.get("key3", refreshFunc)).toBeUndefined();
    expect(cache.size).toBe(2); // Size unchanged (entries still in Map, but not accessible)

    cache.stop();
  });

  test("should allow disabling cache globally with configureGlobalPromptCache", () => {
    const initialMaxSize = (promptCacheSingleton as any).maxSize;

    try {
      // Configure global cache to be disabled
      configureGlobalPromptCache({ maxSize: 0 });

      // Create clients
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });

      const prompt = createMockPromptCommit("test");
      const refreshFunc = async () => prompt;

      // Set via client1's cache
      (client1 as any)._promptCache!.set("key1", prompt, refreshFunc);

      // Get via client2's cache - should return undefined (disabled)
      const result = (client2 as any)._promptCache!.get("key1", refreshFunc);
      expect(result).toBeUndefined();

      // Verify it's the same singleton
      expect((client1 as any)._promptCache).toBe((client2 as any)._promptCache);
      expect((client1 as any)._promptCache).toBe(promptCacheSingleton);
    } finally {
      // Restore original maxSize
      configureGlobalPromptCache({ maxSize: initialMaxSize });
      promptCacheSingleton.clear();
    }
  });

  test("should not start refresh timer when maxSize is 0", () => {
    jest.useFakeTimers();

    try {
      const cache = new PromptCache({
        maxSize: 0,
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
      });

      const fetchFunc = jest
        .fn<() => Promise<PromptCommit>>()
        .mockResolvedValue(createMockPromptCommit("test"));

      // Set with disabled cache
      cache.set("key1", createMockPromptCommit("test"), fetchFunc);

      // Advance time
      jest.advanceTimersByTime(10000);

      // Refresh should never be called since cache is disabled
      expect(fetchFunc).not.toHaveBeenCalled();
      expect((cache as any).refreshTimer).toBeUndefined();

      cache.stop();
    } finally {
      jest.useRealTimers();
    }
  });
});

describe("additional singleton tests", () => {
  test("should configure singleton after clients created", () => {
    const client1 = new Client({ apiKey: "test-key-1" });
    const client2 = new Client({ apiKey: "test-key-2" });

    // Get initial config
    const initialMaxSize = (promptCacheSingleton as any).maxSize;
    const initialTtl = (promptCacheSingleton as any).ttlSeconds;

    try {
      // Configure singleton
      configureGlobalPromptCache({ maxSize: 200, ttlSeconds: 7200 });

      // Both clients should see new config (same singleton)
      expect(((client1 as any)._promptCache as any).maxSize).toBe(200);
      expect(((client1 as any)._promptCache as any).ttlSeconds).toBe(7200);
      expect(((client2 as any)._promptCache as any).maxSize).toBe(200);
      expect(((client2 as any)._promptCache as any).ttlSeconds).toBe(7200);

      // Verify it's the same object
      expect((client1 as any)._promptCache).toBe((client2 as any)._promptCache);
      expect((client1 as any)._promptCache).toBe(promptCacheSingleton);
    } finally {
      // Restore
      configureGlobalPromptCache({
        maxSize: initialMaxSize,
        ttlSeconds: initialTtl,
      });
    }
  });

  test("should share metrics across clients", () => {
    promptCacheSingleton.clear();
    promptCacheSingleton.resetMetrics();

    const client1 = new Client({ apiKey: "test-key-1" });
    const client2 = new Client({ apiKey: "test-key-2" });

    const prompt = createMockPromptCommit("test");

    // Client 1 sets a value
    (client1 as any)._promptCache!.set("key1", prompt);

    // Client 2 gets the value (hit)
    const result = (client2 as any)._promptCache!.get("key1");
    expect(result).toBeDefined();

    // Metrics should be shared
    expect((client1 as any)._promptCache!.metrics.hits).toBe(1);
    expect((client2 as any)._promptCache!.metrics.hits).toBe(1); // Same metrics object

    // Client 1 misses
    (client1 as any)._promptCache!.get("missing-key");

    // Client 2 should see the miss
    expect((client2 as any)._promptCache!.metrics.misses).toBe(1);
  });

  test("should share refresh timer across clients", async () => {
    promptCacheSingleton.clear();
    promptCacheSingleton.resetMetrics();
    promptCacheSingleton.stop();

    const mockFetch = jest
      .fn<(key: string) => Promise<PromptCommit>>()
      .mockResolvedValue(createMockPromptCommit("refreshed"));

    // Configure singleton with fetch func
    (promptCacheSingleton as any).fetchFunc = mockFetch;
    (promptCacheSingleton as any).ttlSeconds = 10;

    try {
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });
      const client3 = new Client({ apiKey: "test-key-3" });

      // Trigger timer start via any client
      const prompt = createMockPromptCommit("test");
      (client1 as any)._promptCache!.set("key1", prompt);

      // All should share the same timer (hard to check directly, but we can verify behavior)
      expect((client1 as any)._promptCache).toBe((client2 as any)._promptCache);
      expect((client2 as any)._promptCache).toBe((client3 as any)._promptCache);
      expect(((client1 as any)._promptCache as any).refreshTimer).toBeDefined();
    } finally {
      (promptCacheSingleton as any).fetchFunc = undefined;
      promptCacheSingleton.stop();
      promptCacheSingleton.clear();
    }
  });

  test("should persist and load singleton data", () => {
    const tempDir = os.tmpdir();
    const cachePath = path.join(tempDir, "singleton_cache_test.json");

    promptCacheSingleton.clear();
    promptCacheSingleton.resetMetrics();

    try {
      const client1 = new Client({ apiKey: "test-key-1" });

      // Client sets some values
      (client1 as any)._promptCache!.set(
        "prompt1",
        createMockPromptCommit("test1")
      );
      (client1 as any)._promptCache!.set(
        "prompt2",
        createMockPromptCommit("test2")
      );

      // Dump via singleton
      promptCacheSingleton.dump(cachePath);

      // Clear and load
      promptCacheSingleton.clear();
      const loaded = promptCacheSingleton.load(cachePath);

      expect(loaded).toBe(2);

      // New client should see loaded values
      const client2 = new Client({ apiKey: "test-key-2" });
      expect((client2 as any)._promptCache!.get("prompt1")).toBeDefined();
      expect((client2 as any)._promptCache!.get("prompt2")).toBeDefined();
    } finally {
      if (fs.existsSync(cachePath)) {
        fs.unlinkSync(cachePath);
      }
      promptCacheSingleton.clear();
    }
  });

  test("should stop refresh timer when configuring", () => {
    promptCacheSingleton.clear();
    promptCacheSingleton.resetMetrics();
    promptCacheSingleton.stop();

    const mockFetch = jest
      .fn<(key: string) => Promise<PromptCommit>>()
      .mockResolvedValue(createMockPromptCommit("refreshed"));

    // Configure with fetch func and start timer
    (promptCacheSingleton as any).fetchFunc = mockFetch;
    (promptCacheSingleton as any).ttlSeconds = 10;

    const prompt = createMockPromptCommit("test");
    promptCacheSingleton.set("key1", prompt, async () => prompt);

    // Timer should be running
    expect((promptCacheSingleton as any).refreshTimer).toBeDefined();
    const firstTimer = (promptCacheSingleton as any).refreshTimer;

    // Reconfigure - should stop the timer
    promptCacheSingleton.configure({ maxSize: 200, ttlSeconds: 20 });

    // Timer should be cleared by configure (configure calls stop())
    expect((promptCacheSingleton as any).refreshTimer).toBeUndefined();

    // Set again to restart timer with new config
    promptCacheSingleton.set("key2", prompt, async () => prompt);

    // New timer should be started
    expect((promptCacheSingleton as any).refreshTimer).toBeDefined();
    const secondTimer = (promptCacheSingleton as any).refreshTimer;

    // Should be a different timer object
    expect(secondTimer).not.toBe(firstTimer);

    // Clean up
    (promptCacheSingleton as any).fetchFunc = undefined;
    promptCacheSingleton.stop();
    promptCacheSingleton.clear();
  });
});
