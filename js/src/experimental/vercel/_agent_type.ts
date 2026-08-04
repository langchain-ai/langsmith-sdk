import { isRunTree } from "../../run_trees.js";
import { getCurrentRunTree } from "../../singletons/traceable.js";
import {
  LsAgentType,
  NON_ROOT_LS_AGENT_TYPES,
  lsAgentTypeMetadata,
  resolveDefaultLsAgentType,
} from "../../utils/ls_agent_type.js";

// Vercel composition: AI SDK inner spans bypass traceable's outer_metadata
// propagation, so we manually inspect the parent runtree. Precedence:
// non-root parent tag > run_type=tool > inherited root > no-parent default.
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
