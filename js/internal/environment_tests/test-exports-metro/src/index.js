/**
 * Metro bundler test for langsmith exports.
 * Tests that public API works correctly when bundled with Metro.
 *
 * This test verifies:
 * 1. Metro can bundle langsmith
 * 2. The browser field in package.json correctly swaps Node-specific code
 * 3. Client export is available
 * 4. Cache export is available (in-memory caching works in React Native)
 *
 * Note: Cache dump/load are not supported in React Native.
 */

import { Client, PromptCache } from "langsmith";

// Export to prevent tree-shaking
export { Client, Cache };

// Simple test that instantiation works
export function testExports() {
  const client = new Client({ apiKey: "test-key" });

  // Test Cache - in-memory caching works in React Native
  const cache = new PromptCache({ maxSize: 100, ttlSeconds: 3600 });
  cache.stop();

  // Test Client with cache enabled
  const clientWithCache = new Client({
    apiKey: "test-key",
    disablePromptCache: false,
  });

  return { client, cache, clientWithCache };
}
