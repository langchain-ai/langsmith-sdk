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
 * Resolve `ls_agent_type` for a Vercel-generated span.
 *
 * Precedence:
 *   1. Narrowing parent tag (`middleware` / `subagent` / `compaction`)
 *      always inherits — user narrowing intent beats structural detection.
 *   2. `parent.run_type === "tool"` → `subagent`. Vercel's structural
 *      convention overrides inherited/default `root`.
 *   3. Parent tagged `root` (default or user) inherits explicitly.
 *   4. `"root"` when there is no parent runtree.
 *   5. Otherwise `undefined` — caller skips stamping.
 */
export function resolveLsAgentType(
  parentRunTree?: unknown,
): LsAgentType | undefined {
  const parent = parentRunTree ?? getCurrentRunTree(true);
  if (!isRunTreeLike(parent) || parent == null) return "root";

  const parentTag = parent.extra?.metadata?.ls_agent_type;
  if (typeof parentTag === "string" && NARROWING_TAGS.has(parentTag)) {
    return parentTag as LsAgentType;
  }
  if (parent.run_type === "tool") return "subagent";
  if (parentTag === "root") return "root";
  return undefined;
}

/**
 * Convenience spread — `{ ls_agent_type: <tag> }` or `{}` when the resolver
 * yields undefined. Prevents `ls_agent_type: undefined` from landing in a
 * spread metadata object.
 */
export function lsAgentTypeMetadata(parentRunTree?: unknown): {
  ls_agent_type?: LsAgentType;
} {
  const tag = resolveLsAgentType(parentRunTree);
  return tag !== undefined ? { ls_agent_type: tag } : {};
}
