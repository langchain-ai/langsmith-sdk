/**
 * TypeScript compilation test for 'import * as langsmith from langsmith'
 * This ensures that namespace imports work correctly with the built package.
 */

// Test namespace import
import * as langsmith from "langsmith";

// Verify that common exports are accessible
function testNamespaceImport() {
  // Test Client is accessible
  const client = new langsmith.Client({ apiKey: "test-key" });
  
  // Test RunTree is accessible (should be in run_trees submodule)
  // Note: This is just a type check, we're not actually running the code
  const _clientType: typeof langsmith.Client = langsmith.Client;
  
  console.log("✓ Namespace import compiles successfully");
  console.log("✓ Client is accessible via langsmith.Client");
}

// Test that specific submodule imports also work
import * as runTrees from "langsmith/run_trees";
import * as traceable from "langsmith/traceable";

function testSubmoduleNamespaceImports() {
  const _runTreeType: typeof runTrees.RunTree = runTrees.RunTree;
  const _traceableType: typeof traceable.traceable = traceable.traceable;
  
  console.log("✓ Submodule namespace imports compile successfully");
}

// Ensure functions are referenced to avoid unused warnings
testNamespaceImport;
testSubmoduleNamespaceImports;
