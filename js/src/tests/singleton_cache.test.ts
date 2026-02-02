import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { CacheManagerSingleton } from "../singletons/cache.js";
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
    CacheManagerSingleton.cleanup();
  });

  afterEach(() => {
    CacheManagerSingleton.cleanup();
  });

  test("cache should be enabled by default", () => {
    const client = new Client();
    const cache = client.cache;

    // Cache should be enabled by default (lazy initialized on access)
    expect(cache).toBeDefined();
    expect(CacheManagerSingleton.isInitialized()).toBe(true);
  });

  test("multiple clients should share the same cache instance", () => {
    const client1 = new Client({ cache: true });
    const client2 = new Client({ cache: true });

    const cache1 = client1.cache;
    const cache2 = client2.cache;

    // Both clients should have cache enabled
    expect(cache1).toBeDefined();
    expect(cache2).toBeDefined();

    // They should be the exact same instance
    expect(cache1).toBe(cache2);
  });

  test("cache should be shared across client instances", () => {
    const client1 = new Client({ cache: true });
    const client2 = new Client({ cache: true });

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
      cache: {
        maxSize: 50,
        ttlSeconds: 1800,
      },
    });

    const cache1 = client1.cache;
    expect(cache1).toBeDefined();

    // Second client with different config should use the same instance
    const client2 = new Client({
      cache: {
        maxSize: 100, // Different config, but should be ignored
        ttlSeconds: 3600,
      },
    });

    const cache2 = client2.cache;

    // Should be the same instance
    expect(cache1).toBe(cache2);
  });

  test("client with cache disabled should not access the singleton", () => {
    const client1 = new Client({ cache: true });
    const client2 = new Client({ cache: false });

    expect(client1.cache).toBeDefined();
    expect(client2.cache).toBeUndefined();
  });

  test("cleanup should not stop the global cache", () => {
    const client1 = new Client({ cache: true });
    const cache = client1.cache;

    expect(cache).toBeDefined();

    // Call cleanup on client
    client1.cleanup();

    // Cache should still be accessible from another client
    const client2 = new Client({ cache: true });
    expect(client2.cache).toBe(cache);
  });

  test("CacheManagerSingleton.cleanup should stop and clear the cache", () => {
    const client1 = new Client({ cache: true });
    const cache1 = client1.cache;

    expect(cache1).toBeDefined();
    if (!cache1) throw new Error("Cache should be defined");

    // Add something to the cache
    cache1.set("test-key", createMockPromptCommit("test"));
    expect(cache1.size).toBe(1);

    // Cleanup the singleton
    CacheManagerSingleton.cleanup();

    // New client should get a fresh cache
    const client2 = new Client({ cache: true });
    const cache2 = client2.cache;

    expect(cache2).toBeDefined();
    if (!cache2) throw new Error("Cache should be defined");

    // Should be a new instance
    expect(cache2).not.toBe(cache1);

    // Should be empty
    expect(cache2.size).toBe(0);
  });

  test("metrics should be shared across clients", () => {
    const client1 = new Client({ cache: true });
    const client2 = new Client({ cache: true });

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
    expect(CacheManagerSingleton.isInitialized()).toBe(false);

    // Accessing cache property should initialize it
    const cache = client.cache;
    expect(cache).toBeDefined();
    expect(CacheManagerSingleton.isInitialized()).toBe(true);
  });

  test("cache should lazy initialize on first prompt pull", async () => {
    const { client, callSpy } = mockClient();

    // Cache should not be initialized yet
    expect(CacheManagerSingleton.isInitialized()).toBe(false);

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
    expect(CacheManagerSingleton.isInitialized()).toBe(true);
    expect(result.commit_hash).toBe("abc123");
    
    const cache = client.cache;
    expect(cache).toBeDefined();
  });
});
