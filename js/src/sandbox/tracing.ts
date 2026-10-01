import { isRunTree } from "../run_trees.js";
import { getCurrentRunTree } from "../singletons/traceable.js";

export function addSandboxMetadata(sandboxId?: string): void {
  if (!sandboxId) return;
  const run = getCurrentRunTree(true);
  if (isRunTree(run)) {
    run.metadata = { sandbox_id: sandboxId };
  }
}
