import type Anthropic from "@anthropic-ai/sdk";
import type { RunTree, RunTreeConfig } from "../../run_trees.js";

/**
 * Types from @anthropic-ai/claude-agent-sdk
 */
export type SDKAssistantMessage = {
  type: "assistant";
  message: Anthropic.Beta.BetaMessage;
  parent_tool_use_id: string | null;
};
type SDKResultMessage = {
  type: "result";
  duration_ms: number;
  duration_api_ms: number;
  total_cost_usd: number;
  usage: Record<string, Anthropic.Beta.BetaUsage>;
  modelUsage: Record<string, SDKModelUsage>;
};

type SDKUserMessage = {
  type: "user";
  message: Anthropic.MessageParam;
  parent_tool_use_id: string | null;
  isSynthetic?: boolean;
  tool_use_result?: unknown;
  session_id: string;
  isReplay?: boolean;
};

export type SDKMessage =
  | SDKAssistantMessage
  | SDKResultMessage
  | SDKUserMessage;

export type SDKModelUsage = {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
  webSearchRequests: number;
  costUSD: number;
  contextWindow: number;
};

export type SDKHookEvents = [
  "PreToolUse",
  "PostToolUse",
  "PostToolUseFailure",
  "Notification",
  "UserPromptSubmit",
  "SessionStart",
  "SessionEnd",
  "Stop",
  "SubagentStart",
  "SubagentStop",
  "PreCompact",
  "PermissionRequest"
][number];

export type QueryOptions = {
  model?: string;
  maxTurns?: number;
  tools?: Array<SdkMcpToolDefinition<unknown>>;
  hooks?: Record<string, HookCallbackMatcher[]>;
  [key: string]: unknown;
};

type CallToolResult = {
  content: unknown[];
  isError?: boolean;
};

export type ToolHandler<T> = (
  args: T,
  extra: unknown
) => Promise<CallToolResult>;

export type SdkMcpToolDefinition<T> = {
  name: string;
  description: string;
  inputSchema: unknown;
  handler: ToolHandler<T>;
};

/**
 * Hook input types from Claude Agent SDK
 */
export type HookInput = {
  hook_event_name: string;
  tool_name?: string;
  tool_input?: unknown;
  tool_response?: unknown;
  tool_use_id?: string;
  session_id?: string;
  [key: string]: unknown;
};

export type HookOutput = {
  continue?: boolean;
  [key: string]: unknown;
};

type HookCallback = (
  input: HookInput,
  toolUseId: string | undefined,
  options: { signal: AbortSignal }
) => Promise<HookOutput>;

export type HookCallbackMatcher = {
  matcher?: string;
  hooks: HookCallback[];
  timeout?: number;
};

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
