import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { Cache } from "../utils/prompts_cache/index.js";
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
      const cache = new Cache();
      expect(cache.get("missing-key")).toBeUndefined();
    });

    test("should get and set values", () => {
      const cache = new Cache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt);
      const result = cache.get("test-key");
      expect(result).toBeDefined();
      expect(result?.value).toEqual(prompt);
      expect(result?.isStale).toBe(false);
    });

    test("should invalidate entries", () => {
      const cache = new Cache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");
      cache.set("test-key", prompt);
      cache.invalidate("test-key");
      expect(cache.get("test-key")).toBeUndefined();
    });

    test("should clear all entries", () => {
      const cache = new Cache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));
      cache.set("key2", createMockPromptCommit("test2"));
      expect(cache.size).toBe(2);
      cache.clear();
      expect(cache.size).toBe(0);
    });
  });

  describe("LRU eviction", () => {
    test("should evict oldest entry when max size reached", () => {
      const cache = new Cache({
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
    });

    test("should update LRU order on access", () => {
      const cache = new Cache({
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
    });
  });

  describe("metrics", () => {
    test("should track hits and misses", () => {
      const cache = new Cache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));

      cache.get("key1"); // Hit
      cache.get("key1"); // Hit
      cache.get("missing"); // Miss

      expect(cache.metrics.hits).toBe(2);
      expect(cache.metrics.misses).toBe(1);
      expect(cache.totalRequests).toBe(3);
      expect(cache.hitRate).toBeCloseTo(0.667, 2);
    });

    test("should reset metrics", () => {
      const cache = new Cache({ ttlSeconds: null });
      cache.set("key1", createMockPromptCommit("test1"));
      cache.get("key1");
      cache.get("missing");

      cache.resetMetrics();

      expect(cache.metrics.hits).toBe(0);
      expect(cache.metrics.misses).toBe(0);
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
      const cache1 = new Cache({ ttlSeconds: null });

      cache1.set("key1", createMockPromptCommit("test1"));
      cache1.set("key2", createMockPromptCommit("test2"));
      cache1.dump(cachePath);

      const cache2 = new Cache({ ttlSeconds: null });
      const loaded = cache2.load(cachePath);

      expect(loaded).toBe(2);
      expect(cache2.get("key1")).toBeDefined();
      expect(cache2.get("key2")).toBeDefined();
    });

    test("should return 0 for non-existent file", () => {
      const cache = new Cache({ ttlSeconds: null });
      const loaded = cache.load("/non/existent/path.json");
      expect(loaded).toBe(0);
    });

    test("should return 0 for corrupted file", () => {
      const cachePath = path.join(tempDir, "corrupted.json");
      fs.writeFileSync(cachePath, "not valid json{{{");

      const cache = new Cache({ ttlSeconds: null });
      const loaded = cache.load(cachePath);
      expect(loaded).toBe(0);
    });

    test("should respect max size when loading", () => {
      const cachePath = path.join(tempDir, "cache.json");
      const cache1 = new Cache({
        maxSize: 10,
        ttlSeconds: null,
      });

      for (let i = 0; i < 5; i++) {
        cache1.set(`key${i}`, createMockPromptCommit(`test${i}`));
      }
      cache1.dump(cachePath);

      const cache2 = new Cache({
        maxSize: 3,
        ttlSeconds: null,
      });
      const loaded = cache2.load(cachePath);

      expect(loaded).toBe(3);
      expect(cache2.size).toBe(3);
    });

    test("should create parent directories", () => {
      const cachePath = path.join(tempDir, "nested", "dir", "cache.json");
      const cache = new Cache({ ttlSeconds: null });

      cache.set("key1", createMockPromptCommit("test1"));
      cache.dump(cachePath);

      expect(fs.existsSync(cachePath)).toBe(true);
    });
  });

  describe("staleness detection", () => {
    test("should mark entries as stale after TTL expires", async () => {
      const cache = new Cache({ ttlSeconds: 0.1 }); // 100ms TTL
      const prompt = createMockPromptCommit("test");

      cache.set("test-key", prompt);

      // Immediately - should be fresh
      let result = cache.get("test-key");
      expect(result).toBeDefined();
      expect(result?.isStale).toBe(false);

      // Wait for TTL to expire
      await new Promise((resolve) => setTimeout(resolve, 150));

      // Should now be stale
      result = cache.get("test-key");
      expect(result).toBeDefined();
      expect(result?.isStale).toBe(true);
    });

    test("should never mark entries as stale with null TTL", async () => {
      const cache = new Cache({ ttlSeconds: null });
      const prompt = createMockPromptCommit("test");

      cache.set("test-key", prompt);

      // Wait a bit
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should still be fresh
      const result = cache.get("test-key");
      expect(result).toBeDefined();
      expect(result?.isStale).toBe(false);
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
      const onlineCache = new Cache({
        ttlSeconds: 3600,
      });
      onlineCache.set("prompt1", createMockPromptCommit("test1"));
      onlineCache.set("prompt2", createMockPromptCommit("test2"));
      onlineCache.dump(cachePath);

      // Step 2: Offline - load from file with infinite TTL
      const offlineCache = new Cache({
        ttlSeconds: null, // Never expire
      });
      const loaded = offlineCache.load(cachePath);

      expect(loaded).toBe(2);
      expect(offlineCache.get("prompt1")).toBeDefined();
      expect(offlineCache.get("prompt2")).toBeDefined();
    });
  });
});
