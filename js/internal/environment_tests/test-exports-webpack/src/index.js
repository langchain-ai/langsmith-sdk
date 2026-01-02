/**
 * Webpack browser environment test for langsmith exports.
 * Tests that public API works correctly when bundled with webpack for browsers.
 *
 * This test verifies:
 * 1. Webpack can build langsmith for browser targets
 * 2. The browser field in package.json correctly swaps Node-specific code
 * 3. Client export is available (uses fetch, works in browsers)
 */

import { Client } from "langsmith";

// Export to prevent tree-shaking
export { Client };

// Simple test that instantiation works
export function testExports() {
  const client = new Client({ apiKey: "test-key" });
  return { client };
}
