/**
 * TypeScript compilation test for 'import * as langsmith from langsmith'
 */

// Test namespace import - the primary test case
import * as langsmith from "langsmith";

// Verify that common exports are accessible through the namespace
function testNamespaceImport() {
  // Test Client is accessible and can be instantiated
  const client: langsmith.Client = new langsmith.Client({ apiKey: "test-key" });

  // Test RunTree is accessible
  const runTree: langsmith.RunTree = new langsmith.RunTree({
    name: "test",
    run_type: "chain",
  });

  // Verify types are accessible
  const _config: langsmith.ClientConfig = { apiKey: "test" };
  const _runConfig: langsmith.RunTreeConfig = {
    name: "test",
    run_type: "chain",
  };

  // Use the variables to avoid unused warnings
  console.log(typeof client, typeof runTree, typeof _config, typeof _runConfig);
}

// CRITICAL TEST: Verify that @internal APIs are NOT exposed via namespace import
// promptCacheSingleton is marked @internal and should not be accessible
// If this line compiles without error, the test has FAILED - internal APIs are exposed!
const _internalCheck: typeof langsmith.promptCacheSingleton =
  langsmith.promptCacheSingleton;

// Test that specific submodule namespace imports also work
import * as runTrees from "langsmith/run_trees";
import * as traceable from "langsmith/traceable";

function testSubmoduleNamespaceImports() {
  // Verify submodule types
  const _runTreeType: typeof runTrees.RunTree = runTrees.RunTree;
  const _traceableFunc: typeof traceable.traceable = traceable.traceable;

  // Verify we can create instances
  const runTree = new runTrees.RunTree({ name: "test", run_type: "chain" });
  const traced = traceable.traceable((x: string) => x, { name: "test" });

  console.log(
    typeof _runTreeType,
    typeof _traceableFunc,
    typeof runTree,
    typeof traced
  );
}

// Actually call the functions to ensure they're type-checked
testNamespaceImport();
testSubmoduleNamespaceImports();
console.log(typeof _internalCheck);
