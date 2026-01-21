import type {
  PreToolUseHookInput,
  HookJSONOutput,
  PostToolUseHookInput,
  HookInput,
  HookEvent,
  HookCallbackMatcher,
} from "@anthropic-ai/claude-agent-sdk";
import { getCurrentRunTree } from "../../traceable.js";
import { clearActiveToolRuns } from "./context.js";
import type { AgentSDKContext } from "./context.js";

/**
 * PreToolUse hook that creates a tool span when a tool execution starts.
 * This traces ALL tools including built-in tools, external MCP tools, and SDK MCP tools.
 * Skips tools that are client-managed (subagent sessions and their children).
 */

async function preToolUseHook(
  input: PreToolUseHookInput,
  toolUseId: string | undefined,
  context: AgentSDKContext
): Promise<HookJSONOutput> {
  if (!toolUseId) return {};

  // Skip if this tool run is already managed by the client (subagent or its children)
  if (context.clientManagedRuns.has(toolUseId)) {
    return {};
  }

  const toolName = input.tool_name || "unknown_tool";
  const toolInput = input.tool_input;

  try {
    const parent = context.currentParentRun || getCurrentRunTree();
    if (!parent) {
      return {};
    }

    const startTime = Date.now();
    const toolRun = await parent.createChild({
      name: toolName,
      run_type: "tool",
      inputs: toolInput ?? {},
    });

    await toolRun.postRun();

    context.activeToolRuns.set(toolUseId, { run: toolRun, startTime });
  } catch {
    // Silently fail - don't interrupt tool execution
  }

  return {};
}

/**
 * PostToolUse hook that ends the tool span when a tool execution completes.
 * Handles both regular tool runs and client-managed runs (subagents and their children).
 */
async function postToolUseHook(
  input: PostToolUseHookInput,
  toolUseId: string | undefined,
  context: AgentSDKContext
): Promise<HookJSONOutput> {
  if (!toolUseId) return {};

  // Format outputs based on response type
  const parseResponse = (
    response: unknown
  ): { outputs: Record<string, unknown>; error: string | undefined } => {
    let outputs: Record<string, unknown>;
    if (typeof response === "object" && response !== null) {
      if (Array.isArray(response)) {
        outputs = { content: response };
      } else {
        outputs = response as Record<string, unknown>;
      }
    } else {
      outputs = response ? { output: String(response) } : {};
    }

    const error =
      typeof response === "object" &&
      response !== null &&
      "is_error" in response &&
      (response as Record<string, unknown>).is_error === true
        ? outputs.output?.toString()
        : undefined;

    return { outputs, error };
  };

  try {
    // Check if this is a client-managed run (subagent session or its children)
    const clientRun = context.clientManagedRuns.get(toolUseId);
    const runInfo = context.activeToolRuns.get(toolUseId);
    const { outputs, error } = parseResponse(input.tool_response);

    if (clientRun) {
      context.clientManagedRuns.delete(toolUseId);
      await clientRun.end(outputs, error);
      await clientRun.patchRun();
    } else if (runInfo) {
      context.activeToolRuns.delete(toolUseId);
      await runInfo.run.end(outputs, error);
      await runInfo.run.patchRun();
    }
  } catch {
    // Silently fail - don't interrupt tool execution
  }

  return {};
}
/**
 * Creates hook matchers for LangSmith tracing.
 * Returns PreToolUse and PostToolUse hook configurations.
 */
function createTracingHooks(context: AgentSDKContext) {
  return {
    PreToolUse: [
      {
        matcher: undefined, // Match all tools
        hooks: [
          async (
            input: HookInput,
            toolUseId: string | undefined,
            _options: { signal: AbortSignal }
          ) => preToolUseHook(input as PreToolUseHookInput, toolUseId, context),
        ],
      },
    ],
    PostToolUse: [
      {
        matcher: undefined, // Match all tools
        hooks: [
          async (
            input: HookInput,
            toolUseId: string | undefined,
            _options: { signal: AbortSignal }
          ) =>
            postToolUseHook(input as PostToolUseHookInput, toolUseId, context),
        ],
      },
    ],

    SessionEnd: [
      {
        matcher: undefined,
        hooks: [
          async (_input: HookInput) => {
            // Clean up at end of session
            clearActiveToolRuns(context);
            return {};
          },
        ],
      },
    ],

    SubagentStop: [
      {
        matcher: undefined,
        hooks: [
          async (_input: HookInput, toolUseId: string | undefined) => {
            // Clean up subagent session
            if (toolUseId) {
              context.subagentSessions.delete(toolUseId);
              context.clientManagedRuns.delete(toolUseId);
            }
            return {};
          },
        ],
      },
    ],
    Stop: [
      {
        matcher: undefined,
        hooks: [
          async (_input: HookInput) => {
            // Clean up on stop - ensure all runs are finalized
            clearActiveToolRuns(context);
            return {};
          },
        ],
      },
    ],
  } satisfies Partial<Record<HookEvent, HookCallbackMatcher[]>>;
}
/**
 * Merges LangSmith tracing hooks with existing user hooks.
 */
export function mergeHooks(
  existingHooks: Record<string, HookCallbackMatcher[]> | undefined,
  context: AgentSDKContext
): Record<string, HookCallbackMatcher[]> {
  const tracingHooks = createTracingHooks(context);
  if (!existingHooks) return tracingHooks;

  const merged: Record<string, HookCallbackMatcher[]> = { ...existingHooks };

  // Prepend tracing hooks so they run first
  for (const [event, matchers] of Object.entries(tracingHooks)) {
    merged[event] = [...matchers, ...(merged[event] ?? [])];
  }

  return merged;
}
