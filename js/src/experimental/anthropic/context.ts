import type { RunTree, RunTreeConfig } from "../../run_trees.js";

export type AgentSDKContext = {
  /**
   * Storage for active tool runs, keyed by tool_use_id.
   * Used to correlate PreToolUse and PostToolUse hooks.
   */
  activeToolRuns: Map<string, { run: RunTree; startTime: number }>;

  /**
   * Storage for client-managed runs (subagent sessions and their child tools).
   * These are created when processing AssistantMessage content blocks and
   * closed when PostToolUse hook fires. Keyed by tool_use_id.
   */
  clientManagedRuns: Map<string, RunTree>;

  /**
   * Storage for subagent sessions, keyed by the Task tool's tool_use_id.
   * Used to parent LLM turns and tools to the correct subagent.
   */
  subagentSessions: Map<string, RunTree>;

  /**
   * Tracks the currently active subagent context (tool_use_id).
   * Set when a Task tool is called, cleared when the tool result returns.
   * Assistant messages that arrive while a subagent is active belong to that subagent.
   */
  activeSubagentToolUseId: string | undefined;

  /**
   * Reference to the current parent run tree for tool tracing.
   * Set when a traced query starts, cleared when it ends.
   */
  currentParentRun: RunTree | undefined;
};

/**
 * Configuration options for wrapping Claude Agent SDK with LangSmith tracing.
 */
export type WrapClaudeAgentSDKConfig = Partial<
  Omit<
    RunTreeConfig,
    "inputs" | "outputs" | "run_type" | "child_runs" | "parent_run" | "error"
  >
>;
/**
 * Clears all active tool runs and client-managed runs. Called when a conversation ends.
 */

export function clearActiveToolRuns(context: AgentSDKContext): void {
  // Clean up client-managed runs (subagents and their children)
  for (const [, run] of context.clientManagedRuns) {
    try {
      run
        .end({ error: "Run not completed (conversation ended)" })
        .then(() => run.patchRun())
        .catch(() => {});
    } catch {
      // Ignore cleanup errors
    }
  }
  context.clientManagedRuns.clear();
  context.subagentSessions.clear();
  context.activeSubagentToolUseId = undefined;

  // Clean up regular tool runs
  for (const [, { run }] of context.activeToolRuns) {
    try {
      run
        .end({ error: "Tool run not completed (conversation ended)" })
        .then(() => run.patchRun())
        .catch(() => {});
    } catch {
      // Ignore cleanup errors
    }
  }
  context.activeToolRuns.clear();
}

export const createQueryContext = (): AgentSDKContext => ({
  activeToolRuns: new Map(),
  clientManagedRuns: new Map(),
  subagentSessions: new Map(),
  activeSubagentToolUseId: undefined,
  currentParentRun: undefined,
});
