import { traceable, getCurrentRunTree } from "../../traceable.js";
import type { RunTreeConfig, RunTree } from "../../run_trees.js";
import { convertAnthropicUsageToInputTokenDetails } from "../../utils/usage.js";

/**
 * Types from @anthropic-ai/claude-agent-sdk
 */
type SDKMessage = {
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

type QueryOptions = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

type CallToolResult = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: Array<any>;
  isError?: boolean;
};

type ToolHandler<T> = (
  args: T,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  extra: any
) => Promise<CallToolResult>;

type SdkMcpToolDefinition<T> = {
  name: string;
  description: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inputSchema: any;
  handler: ToolHandler<T>;
};

/**
 * Content block types from Claude SDK
 */
type ContentBlock = {
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

/**
 * Hook input types from Claude Agent SDK
 */
type HookInput = {
  hook_event_name: string;
  tool_name?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tool_input?: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tool_response?: any;
  tool_use_id?: string;
  session_id?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

type HookOutput = {
  continue?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

type HookCallback = (
  input: HookInput,
  toolUseId: string | undefined,
  options: { signal: AbortSignal }
) => Promise<HookOutput>;

type HookCallbackMatcher = {
  matcher?: string;
  hooks: HookCallback[];
  timeout?: number;
};

/**
 * Storage for active tool runs, keyed by tool_use_id.
 * Used to correlate PreToolUse and PostToolUse hooks.
 */
const _activeToolRuns: Map<string, { run: RunTree; startTime: number }> =
  new Map();

/**
 * Storage for client-managed runs (subagent sessions and their child tools).
 * These are created when processing AssistantMessage content blocks and
 * closed when PostToolUse hook fires. Keyed by tool_use_id.
 */
const _clientManagedRuns: Map<string, RunTree> = new Map();

/**
 * Storage for subagent sessions, keyed by the Task tool's tool_use_id.
 * Used to parent LLM turns and tools to the correct subagent.
 */
const _subagentSessions: Map<string, RunTree> = new Map();

/**
 * Reference to the current parent run tree for tool tracing.
 * Set when a traced query starts, cleared when it ends.
 */
let _currentParentRun: RunTree | undefined;

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
 * PreToolUse hook that creates a tool span when a tool execution starts.
 * This traces ALL tools including built-in tools, external MCP tools, and SDK MCP tools.
 * Skips tools that are client-managed (subagent sessions and their children).
 */
async function _preToolUseHook(
  input: HookInput,
  toolUseId: string | undefined
): Promise<HookOutput> {
  if (!toolUseId) {
    return {};
  }

  // Skip if this tool run is already managed by the client (subagent or its children)
  if (_clientManagedRuns.has(toolUseId)) {
    return {};
  }

  const toolName = input.tool_name || "unknown_tool";
  const toolInput = input.tool_input;

  try {
    const parent = _currentParentRun || getCurrentRunTree();
    if (!parent) {
      return {};
    }

    const startTime = Date.now();
    const toolRun = await parent.createChild({
      name: toolName,
      run_type: "tool",
      inputs: toolInput ? { input: toolInput } : {},
    });

    await toolRun.postRun();

    _activeToolRuns.set(toolUseId, { run: toolRun, startTime });
  } catch (e) {
    // Silently fail - don't interrupt tool execution
  }

  return {};
}

/**
 * PostToolUse hook that ends the tool span when a tool execution completes.
 * Handles both regular tool runs and client-managed runs (subagents and their children).
 */
async function _postToolUseHook(
  input: HookInput,
  toolUseId: string | undefined
): Promise<HookOutput> {
  if (!toolUseId) {
    return {};
  }

  const toolResponse = input.tool_response;

  // Format outputs based on response type
  const formatOutputs = (
    response: unknown
  ): { outputs: Record<string, unknown>; isError: boolean } => {
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

    const isError =
      typeof response === "object" &&
      response !== null &&
      "is_error" in response &&
      (response as Record<string, unknown>).is_error === true;

    return { outputs, isError };
  };

  try {
    // Check if this is a client-managed run (subagent session or its children)
    const clientRun = _clientManagedRuns.get(toolUseId);
    if (clientRun) {
      _clientManagedRuns.delete(toolUseId);
      // Also remove from subagent sessions if it was a Task tool
      _subagentSessions.delete(toolUseId);

      const { outputs, isError } = formatOutputs(toolResponse);
      clientRun.end({
        outputs,
        error: isError ? outputs.output?.toString() : undefined,
      });
      await clientRun.patchRun();
      return {};
    }

    // Handle regular tool runs
    const runInfo = _activeToolRuns.get(toolUseId);
    if (!runInfo) {
      return {};
    }

    _activeToolRuns.delete(toolUseId);

    const { run: toolRun } = runInfo;
    const { outputs, isError } = formatOutputs(toolResponse);

    toolRun.end({
      outputs,
      error: isError ? outputs.output?.toString() : undefined,
    });

    await toolRun.patchRun();
  } catch (e) {
    // Silently fail - don't interrupt tool execution
  }

  return {};
}

/**
 * Creates hook matchers for LangSmith tracing.
 * Returns PreToolUse and PostToolUse hook configurations.
 */
function _createTracingHooks(): {
  PreToolUse: HookCallbackMatcher[];
  PostToolUse: HookCallbackMatcher[];
} {
  return {
    PreToolUse: [
      {
        matcher: undefined, // Match all tools
        hooks: [
          async (
            input: HookInput,
            toolUseId: string | undefined,
            _options: { signal: AbortSignal }
          ) => _preToolUseHook(input, toolUseId),
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
          ) => _postToolUseHook(input, toolUseId),
        ],
      },
    ],
  };
}

/**
 * Merges LangSmith tracing hooks with existing user hooks.
 */
function _mergeHooks(
  existingHooks: Record<string, HookCallbackMatcher[]> | undefined
): Record<string, HookCallbackMatcher[]> {
  const tracingHooks = _createTracingHooks();

  if (!existingHooks) {
    return tracingHooks;
  }

  const merged: Record<string, HookCallbackMatcher[]> = { ...existingHooks };

  // Prepend tracing hooks so they run first
  for (const [event, matchers] of Object.entries(tracingHooks)) {
    if (merged[event]) {
      merged[event] = [...matchers, ...merged[event]];
    } else {
      merged[event] = matchers;
    }
  }

  return merged;
}

/**
 * Processes tool uses in an AssistantMessage to detect and create subagent sessions.
 * This matches Python's _handle_assistant_tool_uses behavior.
 *
 * @param message - The AssistantMessage to process
 * @param parentRun - The parent run tree (main conversation chain)
 */
async function _handleAssistantToolUses(
  message: SDKMessage,
  parentRun: RunTree | undefined
): Promise<void> {
  if (!parentRun) return;

  const content = message.message?.content;
  if (!Array.isArray(content)) return;

  const parentToolUseId = message.parent_tool_use_id;

  for (const block of content) {
    if (!block || typeof block !== "object" || block.type !== "tool_use") {
      continue;
    }

    const toolUseId = block.id;
    const toolName = block.name || "unknown_tool";
    const toolInput = block.input || {};

    if (!toolUseId) continue;

    try {
      // Check if this is a Task tool (subagent) at the top level
      if (toolName === "Task" && !parentToolUseId) {
        // Extract subagent name from input
        const subagentName =
          toolInput.subagent_type ||
          (toolInput.description
            ? toolInput.description.split(" ")[0]
            : null) ||
          "unknown-agent";

        const subagentSession = await parentRun.createChild({
          name: subagentName,
          run_type: "chain",
          inputs: toolInput,
        });

        await subagentSession.postRun();

        // Store in both maps
        _subagentSessions.set(toolUseId, subagentSession);
        _clientManagedRuns.set(toolUseId, subagentSession);
      }
      // Check if tool use is within a subagent
      else if (parentToolUseId && _subagentSessions.has(parentToolUseId)) {
        const subagentSession = _subagentSessions.get(parentToolUseId)!;

        // Create tool run as child of subagent
        const toolRun = await subagentSession.createChild({
          name: toolName,
          run_type: "tool",
          inputs: toolInput ? { input: toolInput } : {},
        });

        await toolRun.postRun();
        _clientManagedRuns.set(toolUseId, toolRun);
      }
    } catch (e) {
      // Silently fail - don't interrupt message processing
    }
  }
}

/**
 * Clears all active tool runs and client-managed runs. Called when a conversation ends.
 */
function _clearActiveToolRuns(): void {
  // Clean up client-managed runs (subagents and their children)
  for (const [, run] of _clientManagedRuns) {
    try {
      run.end({ error: "Run not completed (conversation ended)" });
      run.patchRun().catch(() => {});
    } catch {
      // Ignore cleanup errors
    }
  }
  _clientManagedRuns.clear();
  _subagentSessions.clear();

  // Clean up regular tool runs
  for (const [, { run }] of _activeToolRuns) {
    try {
      run.end({ error: "Tool run not completed (conversation ended)" });
      run.patchRun().catch(() => {});
    } catch {
      // Ignore cleanup errors
    }
  }
  _activeToolRuns.clear();
}

/**
 * Wraps the Claude Agent SDK's query function to add LangSmith tracing.
 * Traces the entire agent interaction including all streaming messages.
 * Internal use only - use wrapClaudeAgentSDK instead.
 */
function wrapClaudeAgentQuery<
  T extends (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>
>(queryFn: T, defaultThis?: unknown, baseConfig?: WrapClaudeAgentSDKConfig): T {
  const proxy: T = new Proxy(queryFn, {
    apply(target, thisArg, argArray) {
      const params = (argArray[0] ?? {}) as {
        prompt?: string | AsyncIterable<SDKMessage>;
        options?: QueryOptions;
      };

      const { prompt, options = {} } = params;

      // Inject LangSmith tracing hooks into options
      const mergedHooks = _mergeHooks(options.hooks);
      const modifiedOptions = { ...options, hooks: mergedHooks };
      const modifiedParams = { ...params, options: modifiedOptions };
      const modifiedArgArray = [modifiedParams, ...argArray.slice(1)];

      // Create wrapped async generator that maintains trace context
      const wrappedGenerator = (async function* () {
        const finalResults: Array<{ content: unknown; role: string }> = [];

        // Track assistant messages by their message ID for proper streaming handling
        // Each message ID maps to { message, startTime } - we keep the latest streaming update
        const pendingMessages: Map<
          string,
          { message: SDKMessage; startTime: number }
        > = new Map();

        // Store child run promises for proper async handling
        const childRunEndPromises: Promise<void>[] = [];

        // Track usage from ResultMessage to patch into final LLM span
        let resultUsage: Record<string, unknown> | undefined;
        let resultMetadata: Record<string, unknown> | undefined;

        // Set the parent run for hook-based tool tracing
        _currentParentRun = getCurrentRunTree();

        // Create an LLM span for a specific message ID
        const createLLMSpanForId = async (messageId: string) => {
          const pending = pendingMessages.get(messageId);
          if (!pending) return;

          pendingMessages.delete(messageId);

          const finalMessageContent = await _createLLMSpanForMessages(
            [pending.message],
            prompt,
            finalResults,
            modifiedOptions,
            pending.startTime
          );

          if (finalMessageContent) {
            finalResults.push(finalMessageContent);
          }
        };

        const invocationTarget: unknown =
          thisArg === proxy || thisArg === undefined
            ? defaultThis ?? thisArg
            : thisArg;

        const generator: AsyncGenerator<SDKMessage, void, unknown> =
          Reflect.apply(
            target,
            invocationTarget,
            modifiedArgArray
          ) as AsyncGenerator<SDKMessage, void, unknown>;

        try {
          for await (const message of generator) {
            const currentTime = Date.now();

            // Handle assistant messages - group by message ID for streaming
            // Multiple messages with the same ID are streaming updates; use the last one
            if (message.type === "assistant") {
              const messageId = message.message?.id;

              if (messageId) {
                // Check if this is a new message or an update to existing
                const existing = pendingMessages.get(messageId);
                if (!existing) {
                  // New message - store it with current time
                  pendingMessages.set(messageId, {
                    message,
                    startTime: currentTime,
                  });
                } else {
                  // Streaming update - keep the start time, update the message
                  pendingMessages.set(messageId, {
                    message,
                    startTime: existing.startTime,
                  });
                }

                // Check if this message has a stop_reason (meaning it's complete)
                // If so, create the span now
                if (message.message?.stop_reason) {
                  const spanPromise = createLLMSpanForId(messageId);
                  childRunEndPromises.push(spanPromise);
                }
              }

              // Process tool uses for subagent detection (matches Python's _handle_assistant_tool_uses)
              await _handleAssistantToolUses(message, _currentParentRun);
            }

            // Handle UserMessage - add to conversation history (matches Python)
            if (message.type === "user" && message.content) {
              finalResults.push({
                content: flattenContentBlocks(message.content),
                role: "user",
              });
            }

            // Handle ResultMessage - extract usage and metadata (matches Python)
            if (message.type === "result") {
              if (message.usage) {
                resultUsage = _extractUsageFromMessage(message);
                // Add total_cost if available
                if (message.total_cost_usd != null) {
                  resultUsage.total_cost = message.total_cost_usd;
                }
                // Add per-model usage if available
                if (message.modelUsage) {
                  resultUsage.model_usage = message.modelUsage;
                }
              }

              // Extract conversation-level metadata
              resultMetadata = {};
              if (message.num_turns != null) {
                resultMetadata.num_turns = message.num_turns;
              }
              if (message.session_id != null) {
                resultMetadata.session_id = message.session_id;
              }
              if (message.duration_ms != null) {
                resultMetadata.duration_ms = message.duration_ms;
              }
              if (message.duration_api_ms != null) {
                resultMetadata.duration_api_ms = message.duration_api_ms;
              }
              if (message.is_error != null) {
                resultMetadata.is_error = message.is_error;
              }
              if (message.stop_reason != null) {
                resultMetadata.stop_reason = message.stop_reason;
              }
            }

            yield message;
          }

          // Create spans for any remaining pending messages (those without stop_reason)
          for (const messageId of pendingMessages.keys()) {
            const spanPromise = createLLMSpanForId(messageId);
            childRunEndPromises.push(spanPromise);
          }

          // Wait for all child runs to complete
          await Promise.all(childRunEndPromises);

          // Apply result metadata to the chain run (matches Python behavior)
          const currentRun = getCurrentRunTree();
          if (currentRun) {
            // Add usage metadata if available
            if (resultUsage && Object.keys(resultUsage).length > 0) {
              if (!currentRun.extra) {
                currentRun.extra = {};
              }
              if (!currentRun.extra.metadata) {
                currentRun.extra.metadata = {};
              }
              currentRun.extra.metadata.usage_metadata = resultUsage;
            }

            // Add conversation-level metadata if available
            if (resultMetadata && Object.keys(resultMetadata).length > 0) {
              if (!currentRun.extra) {
                currentRun.extra = {};
              }
              if (!currentRun.extra.metadata) {
                currentRun.extra.metadata = {};
              }
              Object.assign(currentRun.extra.metadata, resultMetadata);
            }
          }
        } finally {
          // Clean up parent run reference and any orphaned tool runs
          _currentParentRun = undefined;
          _clearActiveToolRuns();
        }
      })();

      return wrappedGenerator as ReturnType<T>;
    },
  });

  // Wrap the proxy in traceable
  return traceable(proxy, {
    name: "claude.conversation",
    run_type: "chain",
    ...baseConfig,
    metadata: {
      ...baseConfig?.metadata,
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  }) as any;
}

/**
 * Wraps a Claude Agent SDK tool definition to add LangSmith tracing for tool executions.
 * Internal use only - use wrapClaudeAgentSDK instead.
 */
function wrapClaudeAgentTool<T>(
  toolDef: SdkMcpToolDefinition<T>,
  baseConfig?: WrapClaudeAgentSDKConfig
): SdkMcpToolDefinition<T> {
  const originalHandler = toolDef.handler;

  const wrappedHandler = traceable(originalHandler, {
    name: toolDef.name,
    run_type: "tool",
    ...baseConfig,
  }) as ToolHandler<T>;

  return {
    ...toolDef,
    handler: wrappedHandler,
  };
}

/**
 * Builds the input array for an LLM span from the initial prompt and conversation history.
 */
function _buildLLMInput(
  prompt: string | AsyncIterable<SDKMessage> | undefined,
  conversationHistory: Array<{ content: unknown; role: string }>
): Array<{ content: unknown; role: string }> | undefined {
  const promptMessage =
    typeof prompt === "string" ? { content: prompt, role: "user" } : undefined;

  const inputParts = [
    ...(promptMessage ? [promptMessage] : []),
    ...conversationHistory,
  ];

  return inputParts.length > 0 ? inputParts : undefined;
}

/**
 * Extracts and normalizes usage metrics from a Claude Agent SDK message.
 */
function _extractUsageFromMessage(
  message: SDKMessage
): Record<string, unknown> {
  const metrics: Record<string, unknown> = {};

  // Assistant messages contain usage in message.message.usage
  // Result messages contain usage in message.usage
  let usage: unknown;
  if (message.type === "assistant") {
    usage = message.message?.usage;
  } else if (message.type === "result") {
    usage = message.usage;
  }

  if (!usage || typeof usage !== "object") {
    return metrics;
  }

  // Standard token counts - use LangSmith's expected field names
  const inputTokens = getNumberProperty(usage, "input_tokens") || 0;
  const outputTokens = getNumberProperty(usage, "output_tokens") || 0;

  // Get cache tokens
  const cacheRead = getNumberProperty(usage, "cache_read_input_tokens") || 0;
  const cacheCreation =
    getNumberProperty(usage, "cache_creation_input_tokens") || 0;

  // Build input_token_details if we have cache tokens
  if (cacheRead > 0 || cacheCreation > 0) {
    const inputTokenDetails = convertAnthropicUsageToInputTokenDetails(
      usage as Record<string, unknown>
    );
    if (Object.keys(inputTokenDetails).length > 0) {
      metrics.input_token_details = inputTokenDetails;
    }
  }

  // Sum cache tokens into input_tokens total (matching Python's sum_anthropic_tokens)
  const totalInputTokens = inputTokens + cacheRead + cacheCreation;

  metrics.input_tokens = totalInputTokens;
  metrics.output_tokens = outputTokens;
  metrics.total_tokens = totalInputTokens + outputTokens;

  return metrics;
}

/**
 * Creates an LLM span for a group of messages with the same message ID.
 * Returns the final message content to add to conversation history.
 * Handles subagent LLM turns by parenting them to the correct subagent session.
 */
async function _createLLMSpanForMessages(
  messages: SDKMessage[],
  prompt: string | AsyncIterable<SDKMessage> | undefined,
  conversationHistory: Array<{ content: unknown; role: string }>,
  options: QueryOptions,
  startTime: number
): Promise<{ content: unknown; role: string } | undefined> {
  if (messages.length === 0) return undefined;

  const lastMessage = messages[messages.length - 1];
  // Create LLM spans for all AssistantMessages, not just those with usage
  // (matches Python's behavior)
  if (lastMessage.type !== "assistant") {
    return undefined;
  }

  // Extract model from message first, fall back to options (matches Python)
  const model = lastMessage.message.model || options.model;
  const usage = _extractUsageFromMessage(lastMessage);
  const input = _buildLLMInput(prompt, conversationHistory);

  // Flatten content blocks for proper serialization (matches Python)
  const outputs = messages
    .map((m) =>
      m.message?.content && m.message?.role
        ? {
            content: flattenContentBlocks(m.message.content),
            role: m.message.role,
          }
        : undefined
    )
    .filter((c): c is { content: unknown; role: string } => c !== undefined);

  // Check if this message belongs to a subagent
  const parentToolUseId = lastMessage.parent_tool_use_id;
  const subagentParent = parentToolUseId
    ? _subagentSessions.get(parentToolUseId)
    : undefined;

  const endTime = Date.now();

  if (subagentParent) {
    // Create LLM run as child of subagent session with proper start and end time
    try {
      const llmRun = await subagentParent.createChild({
        name: "claude.assistant.turn",
        run_type: "llm",
        inputs: input ?? {},
        outputs: outputs[outputs.length - 1] || { content: outputs },
        start_time: startTime,
        end_time: endTime,
        extra: {
          metadata: {
            ...(model ? { ls_model_name: model } : {}),
            usage_metadata: usage,
          },
        },
      });
      await llmRun.postRun();
    } catch (e) {
      // Silently fail
    }
  } else {
    // Regular LLM turn under main conversation
    // Note: traceable doesn't support start_time config, so we use getCurrentRunTree
    // and manually create the child run to preserve timing
    const currentRun = getCurrentRunTree();
    if (currentRun) {
      try {
        const llmRun = await currentRun.createChild({
          name: "claude.assistant.turn",
          run_type: "llm",
          inputs: input ?? {},
          outputs: outputs[outputs.length - 1] || { content: outputs },
          start_time: startTime,
          end_time: endTime,
          extra: {
            metadata: {
              ...(model ? { ls_model_name: model } : {}),
              usage_metadata: usage,
            },
          },
        });
        await llmRun.postRun();
      } catch (e) {
        // Silently fail
      }
    }
  }

  // Return flattened content for conversation history
  return lastMessage.message?.content && lastMessage.message?.role
    ? {
        content: flattenContentBlocks(lastMessage.message.content),
        role: lastMessage.message.role,
      }
    : undefined;
}

/**
 * Wraps the Claude Agent SDK with LangSmith tracing. This returns wrapped versions
 * of query and tool that automatically trace all agent interactions.
 *
 * @param sdk - The Claude Agent SDK module
 * @param config - Optional LangSmith configuration
 * @returns Object with wrapped query, tool, and createSdkMcpServer functions
 *
 * @example
 * ```typescript
 * import * as claudeSDK from "@anthropic-ai/claude-agent-sdk";
 * import { wrapClaudeAgentSDK } from "langsmith/experimental/claude_agent_sdk";
 *
 * // Wrap once - returns { query, tool, createSdkMcpServer } with tracing built-in
 * const { query, tool, createSdkMcpServer } = wrapClaudeAgentSDK(claudeSDK);
 *
 * // Use normally - tracing is automatic
 * for await (const message of query({
 *   prompt: "Hello, Claude!",
 *   options: { model: "claude-haiku-4-5-20251001" }
 * })) {
 *   console.log(message);
 * }
 *
 * // Tools created with wrapped tool() are automatically traced
 * const calculator = tool("calculator", "Does math", schema, handler);
 * ```
 */
export function wrapClaudeAgentSDK<T extends object>(
  sdk: T,
  config?: WrapClaudeAgentSDKConfig
): T {
  const cache = new Map<PropertyKey, unknown>();

  return new Proxy(sdk, {
    get(target, prop, receiver) {
      if (cache.has(prop)) {
        return cache.get(prop);
      }

      const value = Reflect.get(target, prop, receiver);

      if (prop === "query" && typeof value === "function") {
        const wrappedQuery = wrapClaudeAgentQuery(
          value as (
            ...args: unknown[]
          ) => AsyncGenerator<SDKMessage, void, unknown>,
          target,
          config
        );
        cache.set(prop, wrappedQuery);
        return wrappedQuery;
      }

      if (prop === "tool" && typeof value === "function") {
        const toolFn = value as typeof value;

        const wrappedToolFactory = new Proxy(toolFn, {
          apply(toolTarget, thisArg, argArray) {
            const invocationTarget =
              thisArg === receiver || thisArg === undefined ? target : thisArg;

            const toolDef = Reflect.apply(
              toolTarget,
              invocationTarget,
              argArray
            );
            if (
              toolDef &&
              typeof toolDef === "object" &&
              "handler" in toolDef
            ) {
              return wrapClaudeAgentTool(
                toolDef as SdkMcpToolDefinition<unknown>,
                config
              );
            }
            return toolDef;
          },
        });

        cache.set(prop, wrappedToolFactory);
        return wrappedToolFactory;
      }

      if (typeof value === "function") {
        const bound = value.bind(target);
        cache.set(prop, bound);
        return bound;
      }

      return value;
    },
  }) as T;
}

function getNumberProperty(obj: unknown, key: string): number | undefined {
  if (!obj || typeof obj !== "object" || !(key in obj)) {
    return undefined;
  }
  const value = Reflect.get(obj, key);
  return typeof value === "number" ? value : undefined;
}

/**
 * Converts SDK content blocks into serializable objects.
 * Matches Python's flatten_content_blocks behavior.
 */
function flattenContentBlocks(
  content: ContentBlock[] | unknown
): Array<Record<string, unknown>> | unknown {
  if (!Array.isArray(content)) {
    return content;
  }

  return content.map((block) => {
    if (!block || typeof block !== "object" || !("type" in block)) {
      return block;
    }

    const blockType = block.type;

    switch (blockType) {
      case "text":
        return {
          type: "text",
          text: block.text || "",
        };
      case "thinking":
        return {
          type: "thinking",
          thinking: block.thinking || "",
          signature: block.signature || "",
        };
      case "tool_use":
        return {
          type: "tool_use",
          id: block.id,
          name: block.name,
          input: block.input,
        };
      case "tool_result":
        return {
          type: "tool_result",
          tool_use_id: block.tool_use_id,
          content: block.content,
          is_error: block.is_error || false,
        };
      default:
        return block;
    }
  });
}
