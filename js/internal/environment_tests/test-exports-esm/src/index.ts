/**
 * ESM environment test for langsmith exports.
 * Tests that public API works correctly in ES module environments.
 */

import { Client } from "langsmith";
import { RunTree } from "langsmith/run_trees";
import { traceable } from "langsmith/traceable";

async function testExports() {
  console.log("Testing ESM exports...");

  // Test Client import and instantiation
  const client = new Client({ apiKey: "test-key" });
  console.log("✓ Client imported and instantiated");

  // Test RunTree import
  const runTree = new RunTree({ name: "test", run_type: "chain" });
  console.log("✓ RunTree imported and instantiated");

  // Test traceable import
  const traced = traceable((x: string) => x, { name: "test" });
  console.log("✓ traceable imported successfully");

  console.log("\n✅ All ESM export tests passed!");
}

testExports()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Test failed:", err);
    process.exit(1);
  });
