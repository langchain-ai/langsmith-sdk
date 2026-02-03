/**
 * Vite browser environment test for langsmith exports.
 * Tests that public API works correctly when bundled for browsers.
 *
 * This test verifies:
 * 1. Vite can build langsmith for browser targets
 * 2. The browser field in package.json correctly swaps Node-specific code
 * 3. Client export is available (uses fetch, works in browsers)
 * 4. Cache export is available (in-memory caching works in browsers)
 *
 * Note: traceable and RunTree use AsyncLocalStorage from node:async_hooks
 * which doesn't have a browser equivalent, so they're not tested here.
 * Note: Cache dump/load are not supported in browsers.
 */

import { Client, Cache } from "langsmith";

// Export to prevent tree-shaking
export { Client, Cache };

// Simple test that instantiation works
export function testExports() {
  // Test Client - should work in browser (API calls use fetch)
  const client = new Client({ apiKey: "test-key" });

  // Test Cache - in-memory caching works in browsers
  const cache = new Cache({ maxSize: 100, ttlSeconds: 3600 });

  // Test Client with cache enabled
  const clientWithCache = new Client({ apiKey: "test-key", cache: true });

  return { client, cache, clientWithCache };
}
