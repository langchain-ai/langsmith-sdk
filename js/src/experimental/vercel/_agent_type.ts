import { isRunTree } from "../../run_trees.js";
import { getCurrentRunTree } from "../../singletons/traceable.js";
import {
  LsAgentType,
  NON_ROOT_LS_AGENT_TYPES,
  lsAgentTypeMetadata,
  resolveDefaultLsAgentType,
} from "../../utils/ls_agent_type.js";

// Vercel builds its traceable's `metadata` config eagerly, before traceable
// itself runs — this resolver stamps `ls_agent_type` at that moment.
// Traceable's own propagation would carry a parent's middleware/subagent/
// compaction/"root" tag down on its own. This resolver is needed
// for correct default tagging of the root `ls_agent_type` == root 
// and tagging of subagents. 

export function resolveVercelLsAgentType(
  parentRunTree?: unknown,
): LsAgentType | undefined {
  const parent = parentRunTree ?? getCurrentRunTree(true);
  if (!isRunTree(parent)) return resolveDefaultLsAgentType(parent);

  const parentTag = parent.extra?.metadata?.ls_agent_type;
  if (typeof parentTag === "string" && NON_ROOT_LS_AGENT_TYPES.has(parentTag)) {
    return parentTag as LsAgentType;
  }
  if (parent.run_type === "tool") return "subagent";
  if (parentTag === "root") return "root";
  return undefined;
}

export function vercelLsAgentTypeMetadata(parentRunTree?: unknown) {
  return lsAgentTypeMetadata(resolveVercelLsAgentType(parentRunTree));
}
