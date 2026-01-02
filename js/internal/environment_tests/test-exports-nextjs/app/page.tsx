/**
 * Next.js browser environment test for langsmith exports.
 * Tests that public API works correctly when bundled with Next.js for browsers.
 *
 * This test verifies:
 * 1. Next.js can build langsmith for browser targets
 * 2. The browser field in package.json correctly swaps Node-specific code
 * 3. Client export is available in client components
 */

"use client";

import { Client } from "langsmith";

export default function Page() {
  // Test that Client can be instantiated
  const client = new Client({ apiKey: "test-key" });

  return (
    <div>
      <h1>LangSmith Next.js Test</h1>
      <p>Client instantiated: {client ? "Yes" : "No"}</p>
    </div>
  );
}
