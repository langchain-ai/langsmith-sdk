import { isRunTree } from "../../run_trees.js";
import { getCurrentRunTree } from "../../singletons/traceable.js";

export type LsAgentType = "root" | "subagent" | "middleware" | "compaction";

const NARROWING_TAGS: ReadonlySet<string> = new Set([
  "middleware",
  "subagent",
  "compaction",
]);

// Precedence: narrowing tag > run_type=tool > inherited root > root (no parent) > undefined.
export function resolveLsAgentType(
  parentRunTree?: unknown,
): LsAgentType | undefined {
  const parent = parentRunTree ?? getCurrentRunTree(true);
  // ContextPlaceholder (tracingEnabled=false) isn't a RunTree; treat as no parent.
  if (!isRunTree(parent)) return "root";

  const parentTag = parent.extra?.metadata?.ls_agent_type;
  if (typeof parentTag === "string" && NARROWING_TAGS.has(parentTag)) {
    return parentTag as LsAgentType;
  }
  if (parent.run_type === "tool") return "subagent";
  if (parentTag === "root") return "root";
  return undefined;
}

// Spread helper — skips `ls_agent_type` when the resolver returns undefined.
export function lsAgentTypeMetadata(parentRunTree?: unknown): {
  ls_agent_type?: LsAgentType;
} {
  const tag = resolveLsAgentType(parentRunTree);
  return tag !== undefined ? { ls_agent_type: tag } : {};
}
