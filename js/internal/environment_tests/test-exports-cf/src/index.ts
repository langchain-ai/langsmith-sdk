/**
 * Cloudflare Workers environment test for langsmith exports.
 * Tests that public API works correctly in edge runtime environments.
 *
 * Note: Cache dump/load are not supported in edge environments.
 */

import { Client, PromptCache } from "langsmith";

export default {
  async fetch(): Promise<Response> {
    const results: string[] = [];

    try {
      // Test Client import and instantiation
      const client = new Client({ apiKey: "test-key" });
      results.push("✓ Client imported and instantiated");

      // Test Cache import and instantiation
      const cache = new PromptCache({ maxSize: 100, ttlSeconds: 3600 });
      results.push("✓ Cache imported and instantiated");
      cache.stop();

      // Test Client with cache enabled
      const clientWithCache = new Client({
        apiKey: "test-key",
        disablePromptCache: false,
      });
      results.push("✓ Client with cache enabled");

      results.push("\n✅ All Cloudflare export tests passed!");

      return new Response(results.join("\n"), {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      });
    } catch (err) {
      return new Response(`❌ Test failed: ${err}`, {
        status: 500,
        headers: { "Content-Type": "text/plain" },
      });
    }
  },
};
