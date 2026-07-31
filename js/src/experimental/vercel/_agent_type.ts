import { getCurrentRunTree } from "../../singletons/traceable.js";

export type LsAgentType = "root" | "subagent" | "middleware" | "compaction";

const NARROWING_TAGS: ReadonlySet<string> = new Set([
  "middleware",
  "subagent",
  "compaction",
]);

function isRunTreeLike(
  x: unknown,
): x is { run_type?: string; extra?: { metadata?: Record<string, unknown> } } {
  return typeof x === "object" && x !== null;
}

/**
 * Resolve `ls_agent_type` for a Vercel-generated inner LLM span.
 *
 * Precedence:
 *   1. Narrowing parent tag (`middleware` / `subagent` / `compaction`) inherits.
 *   2. `parent.run_type === "tool"` → `subagent` (Vercel-specific convention).
 *   3. Default `root`.
 *
 * `parentRunTree` may be passed explicitly (used by `telemetry.ts`, which
 * captures the parent runtree at a specific point in its emission pipeline);
 * otherwise the current AsyncLocalStorage runtree is consulted.
 */
export function resolveLsAgentType(parentRunTree?: unknown): LsAgentType {
  const parent = parentRunTree ?? getCurrentRunTree(true);
  if (!isRunTreeLike(parent) || parent == null) return "root";

  const parentTag = parent.extra?.metadata?.ls_agent_type;
  if (typeof parentTag === "string" && NARROWING_TAGS.has(parentTag)) {
    return parentTag as LsAgentType;
  }
  if (parent.run_type === "tool") return "subagent";
  return "root";
}
