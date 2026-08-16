// Shared primitives for the `ls_agent_type` metadata tag.
// Consumed by wrappers/integrations that stamp or inspect `ls_agent_type` on
// traced runs (wrap_openai, OpenAI Agents SDK, Vercel, future wrappers).
// Keep this module SDK-agnostic: the caller passes in the parent run tree.

import { isRunTree } from "../run_trees.js";

export type LsAgentType = "root" | "middleware" | "subagent" | "compaction";

// Non-root tags: preserved against default/structural stamping.
export const NON_ROOT_LS_AGENT_TYPES: ReadonlySet<string> = new Set([
  "middleware",
  "subagent",
  "compaction",
]);

// `"root"` at trace root; `undefined` when nested (rely on propagation).
export function resolveDefaultLsAgentType(
  parentRunTree?: unknown,
): LsAgentType | undefined {
  return isRunTree(parentRunTree) ? undefined : "root";
}

// Spread helper: `{ ls_agent_type: tag }` when tag is set, `{}` when undefined.
export function lsAgentTypeMetadata(tag: LsAgentType | undefined): {
  ls_agent_type?: LsAgentType;
} {
  return tag !== undefined ? { ls_agent_type: tag } : {};
}

// Preserves user-supplied ls_agent_type; stamps default only when key is absent.
export function defaultLsAgentTypeMetadata(
  existingMetadata: Record<string, unknown>,
  parentRunTree?: unknown,
): { ls_agent_type?: LsAgentType } {
  if ("ls_agent_type" in existingMetadata) return {};
  return lsAgentTypeMetadata(resolveDefaultLsAgentType(parentRunTree));
}
