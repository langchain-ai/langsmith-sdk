/**
 * Cloudflare Workers environment test for langsmith exports.
 * Tests that public API works correctly in edge runtime environments.
 */

import { Client } from "langsmith";

export default {
  async fetch(): Promise<Response> {
    const results: string[] = [];

    try {
      // Test Client import and instantiation
      const client = new Client({ apiKey: "test-key" });
      results.push("✓ Client imported and instantiated");

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
