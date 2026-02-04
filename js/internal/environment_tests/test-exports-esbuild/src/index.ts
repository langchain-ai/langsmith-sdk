/**
 * esbuild browser environment test for langsmith exports.
 * Tests that public API works correctly when bundled with esbuild for browsers.
 *
 * This test verifies:
 * 1. esbuild can build langsmith for browser targets (platform=browser)
 * 2. The browser field in package.json correctly swaps Node-specific code
 * 3. Client export is available (uses fetch, works in browsers)
 * 4. Cache export is available (in-memory caching works in browsers)
 *
 * Note: Cache dump/load are not supported in browsers.
 */

import { Client, PromptCache } from "langsmith";

// Export to prevent tree-shaking
export { Client, PromptCache };

// Simple test that instantiation works
export function testExports() {
  const client = new Client({ apiKey: "test-key" });

  // Test Cache - in-memory caching works in browsers
  const cache = new PromptCache({ maxSize: 100, ttlSeconds: 3600 });
  cache.stop();

  // Test Client with cache enabled
  const clientWithCache = new Client({ apiKey: "test-key" });

  return { client, cache, clientWithCache };
}
