import { getCurrentRunTree } from "../../singletons/traceable.js";

export type LsAgentType = "root" | "subagent" | "middleware" | "compaction";

const KNOWN_TAGS: ReadonlySet<string> = new Set([
  "root",
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
 * Resolve `ls_agent_type` for a Vercel-generated span.
 *
 * Precedence:
 *   1. Any known user-supplied parent tag (`root` / `middleware` / `subagent` /
 *      `compaction`) inherits. Explicit inheritance because Vercel's inner LLM
 *      spans don't reliably use traceable's outer_metadata propagation.
 *   2. `parent.run_type === "tool"` → `subagent` (Vercel-specific convention).
 *   3. `undefined` when nested with no user signal — caller should skip
 *      stamping so the run has no `ls_agent_type` on its own metadata.
 *   4. `"root"` when no parent runtree (top-level Vercel call).
 *
 * `parentRunTree` may be passed explicitly (used by `telemetry.ts`, which
 * captures the parent runtree at a specific point in its emission pipeline);
 * otherwise the current AsyncLocalStorage runtree is consulted.
 */
export function resolveLsAgentType(
  parentRunTree?: unknown,
): LsAgentType | undefined {
  const parent = parentRunTree ?? getCurrentRunTree(true);
  if (!isRunTreeLike(parent) || parent == null) return "root";

  const parentTag = parent.extra?.metadata?.ls_agent_type;
  if (typeof parentTag === "string" && KNOWN_TAGS.has(parentTag)) {
    return parentTag as LsAgentType;
  }
  if (parent.run_type === "tool") return "subagent";
  return undefined;
}

/**
 * Convenience spread for metadata objects — yields `{ ls_agent_type: <tag> }`
 * when the resolver returns a value, or an empty object when it returns
 * `undefined`. Prevents `ls_agent_type: undefined` from landing in metadata.
 */
export function lsAgentTypeMetadata(
  parentRunTree?: unknown,
): { ls_agent_type?: LsAgentType } {
  const tag = resolveLsAgentType(parentRunTree);
  return tag !== undefined ? { ls_agent_type: tag } : {};
}
