/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { jest } from "@jest/globals";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  PromptCache,
  promptCacheSingleton,
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
      expect(cache.get("missing-key")).toBeUndefined();
      cache.stop();
    });

    test("should get and set values", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt);
      expect(cache.get("test-key")).toEqual(prompt);
      cache.stop();
    });

    test("should invalidate entries", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt);
      cache.invalidate("test-key");
      expect(cache.get("test-key")).toBeUndefined();
      cache.stop();
    });

    test("should clear all entries", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));
      cache.set("key2", createMockPromptCommit("test2"));
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

      cache.set("key1", createMockPromptCommit("test1"));
      cache.set("key2", createMockPromptCommit("test2"));
      cache.set("key3", createMockPromptCommit("test3"));

      expect(cache.size).toBe(2);
      expect(cache.get("key1")).toBeUndefined(); // Evicted
      expect(cache.get("key2")).toBeDefined();
      expect(cache.get("key3")).toBeDefined();
      cache.stop();
    });

    test("should update LRU order on access", () => {
      const cache = new PromptCache({
        maxSize: 2,
        ttlSeconds: null,
      });

      cache.set("key1", createMockPromptCommit("test1"));
      cache.set("key2", createMockPromptCommit("test2"));

      // Access key1 to make it recently used
      cache.get("key1");

      // Add key3 - should evict key2 (least recently used)
      cache.set("key3", createMockPromptCommit("test3"));

      expect(cache.get("key1")).toBeDefined();
      expect(cache.get("key2")).toBeUndefined(); // Evicted
      expect(cache.get("key3")).toBeDefined();
      cache.stop();
    });
  });

  describe("metrics", () => {
    test("should track hits and misses", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));

      cache.get("key1"); // Hit
      cache.get("key1"); // Hit
      cache.get("missing"); // Miss

      expect(cache.metrics.hits).toBe(2);
      expect(cache.metrics.misses).toBe(1);
      expect(cache.totalRequests).toBe(3);
      expect(cache.hitRate).toBeCloseTo(0.667, 2);
      cache.stop();
    });

    test("should reset metrics", () => {
      const cache = new PromptCache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));
      cache.get("key1");
      cache.get("missing");

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

      cache1.set("key1", createMockPromptCommit("test1"));
      cache1.set("key2", createMockPromptCommit("test2"));
      cache1.dump(cachePath);
      cache1.stop();

      const cache2 = new PromptCache({ ttlSeconds: null });
      const loaded = cache2.load(cachePath);

      expect(loaded).toBe(2);
      expect(cache2!.get("key1")).toBeDefined();
      expect(cache2!.get("key2")).toBeDefined();
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
        cache1.set(`key${i}`, createMockPromptCommit(`test${i}`));
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

      cache.set("key1", createMockPromptCommit("test1"));
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
        fetchFunc: fetchFunc as (key: string) => Promise<PromptCommit>,
      });

      cache.set("key1", createMockPromptCommit("test1"));

      // Advance time significantly
      jest.advanceTimersByTime(120_000);

      expect(fetchFunc).not.toHaveBeenCalled();
      cache.stop();
    });

    test("should refresh stale entries", async () => {
      const refreshedPrompt = createMockPromptCommit("refreshed");
      const fetchFunc = jest
        .fn<(key: string) => Promise<PromptCommit>>()
        .mockResolvedValue(refreshedPrompt);

      const cache = new PromptCache({
        ttlSeconds: 1, // 1 second TTL
        refreshIntervalSeconds: 1, // Check every second
        fetchFunc,
      });

      cache.set("key1", createMockPromptCommit("original"));

      // Advance past TTL and refresh interval
      jest.advanceTimersByTime(2000);

      // Allow the async refresh to complete
      await Promise.resolve();

      expect(fetchFunc).toHaveBeenCalledWith("key1");
      cache.stop();
    });

    test("should track refresh errors", async () => {
      const fetchFunc = jest
        .fn<(key: string) => Promise<PromptCommit>>()
        .mockRejectedValue(new Error("Network error"));

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
        fetchFunc,
      });

      cache.set("key1", createMockPromptCommit("test1"));

      // Advance past TTL and refresh interval
      jest.advanceTimersByTime(2000);

      // Allow the async refresh to complete
      await Promise.resolve();

      expect(cache.metrics.refreshErrors).toBeGreaterThan(0);
      cache.stop();
    });

    test("should stop refresh on stop()", () => {
      const fetchFunc = jest
        .fn<(key: string) => Promise<PromptCommit>>()
        .mockResolvedValue(createMockPromptCommit("test"));

      const cache = new PromptCache({
        ttlSeconds: 1,
        refreshIntervalSeconds: 1,
        fetchFunc,
      });

      cache.set("key1", createMockPromptCommit("test1"));
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
      onlineCache.set("prompt1", createMockPromptCommit("test1"));
      onlineCache.set("prompt2", createMockPromptCommit("test2"));
      onlineCache.dump(cachePath);
      onlineCache.stop();

      // Step 2: Offline - load from file with infinite TTL
      const offlineCache = new PromptCache({
        ttlSeconds: null, // Never expire
        fetchFunc: undefined, // No network access
      });
      const loaded = offlineCache.load(cachePath);

      expect(loaded).toBe(2);
      expect(offlineCache.get("prompt1")).toBeDefined();
      expect(offlineCache.get("prompt2")).toBeDefined();

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
      expect(client.cache).toBe(promptCacheSingleton);
    });

    test("Client can disable caching", () => {
      const client = new Client({
        apiKey: "test-key",
        disablePromptCache: true,
      });
      expect(client.cache).toBeUndefined();
    });

    test("Multiple clients share the same cache", () => {
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });

      expect(client1.cache).toBe(client2.cache);
      expect(client1.cache).toBe(promptCacheSingleton);
    });

    test("Clients share cached values", () => {
      const client1 = new Client({ apiKey: "test-key-1" });
      const client2 = new Client({ apiKey: "test-key-2" });

      const prompt = createMockPromptCommit("shared-prompt");
      promptCacheSingleton.set("shared-key", prompt);

      // Both clients should see the cached value
      expect(client1.cache?.get("shared-key")).toEqual(prompt);
      expect(client2.cache?.get("shared-key")).toEqual(prompt);
    });
  });
});
