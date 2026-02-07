/**
 * CommonJS environment test for langsmith exports.
 * Tests that public API works correctly in CJS environments.
 */

const { Client, PromptCache } = require("langsmith");
const { RunTree } = require("langsmith/run_trees");
const { traceable } = require("langsmith/traceable");

async function testExports() {
  console.log("Testing CJS exports...");

  // Test Client import and instantiation
  const client = new Client({ apiKey: "test-key" });
  console.log("✓ Client imported and instantiated");

  // Test RunTree import
  const runTree = new RunTree({ name: "test", run_type: "chain" });
  console.log("✓ RunTree imported and instantiated");

  // Test traceable import
  const traced = traceable((x) => x, { name: "test" });
  console.log("✓ traceable imported successfully");

  // Test Cache import and instantiation
  const cache = new PromptCache({ maxSize: 100, ttlSeconds: 3600 });
  console.log("✓ Cache imported and instantiated");
  cache.stop();

  // Test Client with cache
  const clientWithCache = new Client({
    apiKey: "test-key",
    disablePromptCache: false,
  });
  console.log("✓ Client with cache enabled");
  clientWithCache.cleanup();

  console.log("\n✅ All CJS export tests passed!");
}

testExports()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Test failed:", err);
    process.exit(1);
  });
