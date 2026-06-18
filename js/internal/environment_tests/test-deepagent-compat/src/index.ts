import { createDeepAgent } from "deepagents";

console.log("Testing deepagent compatibility with local langsmith...");

const agent = createDeepAgent();
console.log("✓ deepagents imported and compiled with local langsmith");

console.log("\n✅ deepagent compatibility smoke test passed!");
