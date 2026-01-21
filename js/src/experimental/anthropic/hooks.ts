import type {
  PreToolUseHookInput,
  HookJSONOutput,
  PostToolUseHookInput,
  HookCallbackMatcher,
  UserPromptSubmitHookInput,
  HookCallback,
  PostToolUseFailureHookInput,
  SessionStartHookInput,
  StopHookInput,
  SessionEndHookInput,
  SubagentStopHookInput,
  NotificationHookInput,
  PermissionRequestHookInput,
  SubagentStartHookInput,
  PreCompactHookInput,
} from "@anthropic-ai/claude-agent-sdk";
import { getCurrentRunTree } from "../../traceable.js";
import { clearActiveToolRuns } from "./context.js";
import type { AgentSDKContext } from "./context.js";

type HookInputMap = {
  PreToolUse: PreToolUseHookInput;
  PostToolUse: PostToolUseHookInput;
  PostToolUseFailure: PostToolUseFailureHookInput;
  Notification: NotificationHookInput;
  UserPromptSubmit: UserPromptSubmitHookInput;
  SessionStart: SessionStartHookInput;
  SessionEnd: SessionEndHookInput;
  Stop: StopHookInput;
  SubagentStart: SubagentStartHookInput;
  SubagentStop: SubagentStopHookInput;
  PreCompact: PreCompactHookInput;
  PermissionRequest: PermissionRequestHookInput;
};

function asHook<TName extends keyof HookInputMap>(
  name: TName,
  callback: (
    input: HookInputMap[TName],
    toolUseID: string | undefined,
    options: {
      signal: AbortSignal;
    }
  ) => Promise<HookJSONOutput>
) {
  return [
    name,
    [
      {
        matcher: undefined,
        hooks: [callback as unknown as HookCallback],
      },
    ],
  ] as [TName, HookCallbackMatcher[]];
}

/**
 * Merges LangSmith tracing hooks with existing user hooks.
 */
export function mergeHooks(
  existingHooks: Record<string, HookCallbackMatcher[]> | undefined,
  context: AgentSDKContext
): Record<string, HookCallbackMatcher[]> {
  const tracingHooks = Object.fromEntries([
    /**
     * PreToolUse hook that creates a tool span when a tool execution starts.
     * This traces ALL tools including built-in tools, external MCP tools, and SDK MCP tools.
     * Skips tools that are client-managed (subagent sessions and their children).
     */
    asHook("PreToolUse", async (input, toolUseId) => {
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
        const toolRun = parent.createChild({
          name: toolName,
          run_type: "tool",
          inputs: toolInput ?? {},
        });

        context.promiseQueue.push(toolRun.postRun());
        context.activeToolRuns.set(toolUseId, { run: toolRun, startTime });
      } catch {
        // Silently fail - don't interrupt tool execution
      }

      return {};
    }),

    /**
     * PostToolUse hook that ends the tool span when a tool execution completes.
     * Handles both regular tool runs and client-managed runs (subagents and their children).
     */
    asHook("PostToolUse", async (input, toolUseId) => {
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
          context.promiseQueue.push(
            clientRun.end(outputs, error).then(() => clientRun.patchRun())
          );
        } else if (runInfo) {
          context.activeToolRuns.delete(toolUseId);
          context.promiseQueue.push(
            runInfo.run.end(outputs, error).then(() => runInfo.run.patchRun())
          );
        }
      } catch {
        // Silently fail - don't interrupt tool execution
      }

      return {};
    }),

    asHook("SubagentStop", async (_, toolUseId) => {
      if (toolUseId) {
        context.subagentSessions.delete(toolUseId);
        context.clientManagedRuns.delete(toolUseId);
      }
      return {};
    }),

    asHook("Stop", async () => {
      clearActiveToolRuns(context);
      return {};
    }),
  ]);

  if (!existingHooks) return tracingHooks;

  const merged: Record<string, HookCallbackMatcher[]> = { ...existingHooks };

  // Prepend tracing hooks so they run first
  for (const [event, matchers] of Object.entries(tracingHooks)) {
    merged[event] = [...matchers, ...(merged[event] ?? [])];
  }

  return merged;
}
