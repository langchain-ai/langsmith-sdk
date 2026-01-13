import {
  traceable,
  getCurrentRunTree,
  isTraceableFunction,
} from "../../traceable.js";
import type { RunTree } from "../../run_trees.js";
import type Anthropic from "@anthropic-ai/sdk";
import { convertAnthropicUsageToInputTokenDetails } from "../../utils/usage.js";
import {
  AgentSDKContext,
  HookInput,
  HookOutput,
  SDKHookEvents,
  HookCallbackMatcher,
  SDKAssistantMessage,
  SDKMessage,
  QueryOptions,
  SdkMcpToolDefinition,
  ToolHandler,
  SDKModelUsage,
  WrapClaudeAgentSDKConfig,
} from "./types.js";
import { getNumberProperty } from "./utils.js";

const createQueryContext = (): AgentSDKContext => ({
  activeToolRuns: new Map(),
  clientManagedRuns: new Map(),
  subagentSessions: new Map(),
  activeSubagentToolUseId: undefined,
  currentParentRun: undefined,
});

/**
 * PreToolUse hook that creates a tool span when a tool execution starts.
 * This traces ALL tools including built-in tools, external MCP tools, and SDK MCP tools.
 * Skips tools that are client-managed (subagent sessions and their children).
 */
async function preToolUseHook(
  input: HookInput,
  toolUseId: string | undefined,
  context: AgentSDKContext
): Promise<HookOutput> {
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
      inputs: toolInput ? { input: toolInput } : {},
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
  input: HookInput,
  toolUseId: string | undefined,
  context: AgentSDKContext
): Promise<HookOutput> {
  if (!toolUseId) return {};
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
    const clientRun = context.clientManagedRuns.get(toolUseId);
    if (clientRun) {
      context.clientManagedRuns.delete(toolUseId);

      const { outputs, isError } = formatOutputs(toolResponse);
      await clientRun.end({
        outputs,
        error: isError ? outputs.output?.toString() : undefined,
      });
      await clientRun.patchRun();
      return {};
    }

    // Handle regular tool runs
    const runInfo = context.activeToolRuns.get(toolUseId);
    if (!runInfo) {
      return {};
    }

    context.activeToolRuns.delete(toolUseId);

    const { run: toolRun } = runInfo;
    const { outputs, isError } = formatOutputs(toolResponse);

    await toolRun.end({
      outputs,
      error: isError ? outputs.output?.toString() : undefined,
    });

    await toolRun.patchRun();
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
          ) => preToolUseHook(input, toolUseId, context),
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
          ) => postToolUseHook(input, toolUseId, context),
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
  } satisfies Partial<Record<SDKHookEvents, HookCallbackMatcher[]>>;
}

/**
 * Merges LangSmith tracing hooks with existing user hooks.
 */
function mergeHooks(
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

/**
 * Type assertion to check if a tool is a Task tool
 * @param tool - The tool to check
 * @returns True if the tool is a Task tool, false otherwise
 */
function isTaskTool(tool: Anthropic.Beta.BetaToolUseBlock): tool is {
  id: string;
  input: {
    description: string;
    prompt: string;
    subagent_type: string;
    agent_type?: string;
  };
  name: "Task";
  type: "tool_use";
} {
  return tool.type === "tool_use" && tool.name === "Task";
}

/**
 * Type-assertion to check for tool blocks
 */
function isToolBlock(
  block: Anthropic.Beta.BetaContentBlock
): block is Anthropic.Beta.BetaToolUseBlock {
  if (!block || typeof block !== "object") return false;
  return block.type === "tool_use";
}

/**
 * Processes tool uses in an AssistantMessage to detect and create subagent sessions.
 * This matches Python's _handle_assistant_tool_uses behavior.
 *
 * @param message - The AssistantMessage to process
 * @param parentRun - The parent run tree (main conversation chain)
 */
async function handleAssistantToolUses(
  message: SDKAssistantMessage,
  parentRun: RunTree | undefined,
  context: AgentSDKContext
): Promise<void> {
  if (!parentRun) return;

  const content = message.message?.content;
  if (!Array.isArray(content)) return;

  const parentToolUseId = message.parent_tool_use_id;

  for (const block of content) {
    if (!isToolBlock(block) || !block.id) continue;

    try {
      // Check if this is a Task tool (subagent) at the top level
      if (isTaskTool(block) && !parentToolUseId) {
        // Extract subagent name from input
        const subagentName =
          block.input.subagent_type ||
          block.input.agent_type ||
          (block.input.description
            ? block.input.description.split(" ")[0]
            : null) ||
          "unknown-agent";

        const subagentSession = await parentRun.createChild({
          name: subagentName,
          run_type: "chain",
          inputs: block.input,
        });

        // Post the run to start it, but DON'T end it yet
        // It will be ended when we receive the tool result or at cleanup
        await subagentSession.postRun();

        // Store in both maps
        context.subagentSessions.set(block.id, subagentSession);
        context.clientManagedRuns.set(block.id, subagentSession);
      }
      // Check if tool use is within a subagent
      else if (
        parentToolUseId &&
        context.subagentSessions.has(parentToolUseId)
      ) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        const subagentSession = context.subagentSessions.get(parentToolUseId)!;

        // Create tool run as child of subagent
        const toolRun = await subagentSession.createChild({
          name: block.name || "unknown_tool",
          run_type: "tool",
          inputs: block.input ? { input: block.input } : {},
        });

        await toolRun.postRun();
        context.clientManagedRuns.set(block.id, toolRun);
      }
    } catch {
      // Silently fail - don't interrupt message processing
    }
  }
}

/**
 * Clears all active tool runs and client-managed runs. Called when a conversation ends.
 */
function clearActiveToolRuns(context: AgentSDKContext): void {
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

/**
 * Wraps the Claude Agent SDK's query function to add LangSmith tracing.
 * Traces the entire agent interaction including all streaming messages.
 * Internal use only - use wrapClaudeAgentSDK instead.
 */
function wrapClaudeAgentQuery<
  T extends (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>
>(queryFn: T, defaultThis?: unknown, baseConfig?: WrapClaudeAgentSDKConfig): T {
  const wrapped = async function* (...args: unknown[]) {
    const context = createQueryContext();
    const params = (args[0] ?? {}) as {
      prompt?: string | AsyncIterable<SDKMessage>;
      options?: QueryOptions;
    };

    const { prompt, options = {} } = params;

    // Inject LangSmith tracing hooks into options
    const mergedHooks = mergeHooks(options.hooks, context);
    const modifiedOptions = { ...options, hooks: mergedHooks };
    const modifiedParams = { ...params, options: modifiedOptions };
    const modifiedArgs = [modifiedParams, ...args.slice(1)];

    const finalResults: Array<{ content: unknown; role: string }> = [];

    // Track assistant messages by their message ID for proper streaming handling
    // Each message ID maps to { message, startTime } - we keep the latest streaming update
    const pendingMessages: Map<
      string,
      {
        message: SDKAssistantMessage;
        messageHistory: Array<{ content: unknown; role: string }>;
        startTime: number;
      }
    > = new Map();

    // Track which message IDs have already had spans created
    // This prevents creating duplicate spans when the SDK sends multiple updates
    // for the same message ID with stop_reason set
    const completedMessageIds = new Set<string>();

    // Store child run promises for proper async handling
    const childRunEndPromises: Promise<void>[] = [];

    // Track usage from ResultMessage to add to the parent span
    let resultUsage: Record<string, unknown> | undefined;

    // Track usage from completed assistant message spans (by model)
    // Used to calculate remaining tokens for pending messages
    const completedUsageByModel = new Map<
      string,
      {
        inputTokens: number;
        outputTokens: number;
        cacheReadTokens: number;
        cacheCreationTokens: number;
      }
    >();

    // Set the parent run for hook-based tool tracing
    context.currentParentRun = getCurrentRunTree();

    // Create an LLM span for a specific message ID
    const createLLMSpanForId = async (messageId: string) => {
      // Skip if we've already created a span for this message ID
      if (completedMessageIds.has(messageId)) {
        return;
      }

      const pending = pendingMessages.get(messageId);
      if (!pending) return;

      pendingMessages.delete(messageId);
      completedMessageIds.add(messageId);

      // Track the usage before creating the span
      const model = pending.message.message?.model;
      const usage = pending.message.message?.usage;
      if (model && usage) {
        const existing = completedUsageByModel.get(model) || {
          inputTokens: 0,
          outputTokens: 0,
          cacheReadTokens: 0,
          cacheCreationTokens: 0,
        };
        existing.inputTokens += usage.input_tokens || 0;
        existing.outputTokens += usage.output_tokens || 0;
        existing.cacheReadTokens += usage.cache_read_input_tokens || 0;
        existing.cacheCreationTokens += usage.cache_creation_input_tokens || 0;
        completedUsageByModel.set(model, existing);
      }

      const finalMessageContent = await createLLMSpanForMessages(
        [pending.message],
        prompt,
        pending.messageHistory,
        modifiedOptions,
        pending.startTime,
        context
      );

      if (finalMessageContent) finalResults.push(finalMessageContent);
    };

    const generator: AsyncGenerator<SDKMessage, void, unknown> =
      await queryFn.call(defaultThis, ...modifiedArgs);

    try {
      for await (const message of generator) {
        const currentTime = Date.now();

        // Handle assistant messages - group by message ID for streaming
        // Multiple messages with the same ID are streaming updates; use the last one
        if (message.type === "assistant") {
          const messageId = message.message?.id;

          // If we have an active subagent context and this message doesn't have parent_tool_use_id,
          // check if this is a new main conversation message (which would end the subagent execution)
          if (context.activeSubagentToolUseId && !message.parent_tool_use_id) {
            // Check if this message contains tool uses - if it does, it's part of main conversation
            const content = message.message?.content;
            if (Array.isArray(content)) {
              const hasToolUse = content.some(
                (block) =>
                  block &&
                  typeof block === "object" &&
                  block.type === "tool_use"
              );
              // If this message has tool uses and none are within the subagent, it's a new turn
              if (hasToolUse) {
                // Clean up the subagent session
                context.subagentSessions.delete(
                  context.activeSubagentToolUseId
                );
                context.activeSubagentToolUseId = undefined;
              }
            }
          }

          if (messageId) {
            // Check if this is a new message or an update to existing
            const existing = pendingMessages.get(messageId);
            if (!existing) {
              // New message arrived - finalize all OTHER pending messages first
              // (they must be complete if we're seeing a new message)

              // Finalize all other pending messages
              for (const [otherId] of pendingMessages) {
                if (otherId !== messageId) {
                  const spanPromise = createLLMSpanForId(otherId);
                  childRunEndPromises.push(spanPromise);
                }
              }

              pendingMessages.set(messageId, {
                message,
                messageHistory: finalResults.slice(0),
                startTime: currentTime,
              });
            } else {
              // Streaming update - keep the start time, update the message
              pendingMessages.set(messageId, {
                message,
                messageHistory: finalResults.slice(0),
                startTime: existing.startTime,
              });
            }

            // We need to push the assistant message as well
            if ("content" in message.message && message.message.content) {
              finalResults.push({
                content: flattenContentBlocks(message.message.content),
                role: "assistant",
              });
            }

            // Check if this message has a stop_reason (meaning it's complete)
            // If so, create the span now (createLLMSpanForId will skip if already created)
            if (message.message?.stop_reason) {
              const spanPromise = createLLMSpanForId(messageId);
              childRunEndPromises.push(spanPromise);
            }
          }

          // Process tool uses for subagent detection (matches Python's _handle_assistant_tool_uses)
          await handleAssistantToolUses(
            message,
            context.currentParentRun,
            context
          );
        }

        // Handle UserMessage - add to conversation history (matches Python)
        if (message.type === "user") {
          if ("content" in message.message && message.message.content) {
            finalResults.push({
              content: flattenContentBlocks(message.message.content),
              role: "user",
            });
          }

          // If this is a tool result for a Task tool (subagent), we're entering the subagent's execution
          // The subagent's assistant messages will come AFTER this result
          if (
            message.parent_tool_use_id &&
            context.subagentSessions.has(message.parent_tool_use_id)
          ) {
            context.activeSubagentToolUseId = message.parent_tool_use_id;
          }
        }

        // Handle ResultMessage - extract usage and metadata
        if (message.type === "result") {
          // If modelUsage is available, aggregate from it (includes ALL models)
          // Otherwise fall back to top-level usage field
          if (message.modelUsage) {
            // Aggregate usage from modelUsage (includes ALL models)
            resultUsage = aggregateUsageFromModelUsage(message.modelUsage);

            // Patch token counts for pending messages using modelUsage
            // This handles the SDK limitation where the last assistant message
            // doesn't receive final streaming updates with accurate token counts
            for (const [, { message: pendingMsg }] of pendingMessages) {
              const model = pendingMsg.message?.model;
              if (
                model &&
                message.modelUsage[model] &&
                pendingMsg.message?.usage
              ) {
                const modelStats = message.modelUsage[model];
                const completed = completedUsageByModel.get(model) || {
                  inputTokens: 0,
                  outputTokens: 0,
                  cacheReadTokens: 0,
                  cacheCreationTokens: 0,
                };

                // Calculate remaining tokens = total - completed
                const remainingOutput =
                  (modelStats.outputTokens || 0) - completed.outputTokens;
                const remainingInput =
                  (modelStats.inputTokens || 0) - completed.inputTokens;
                const remainingCacheRead =
                  (modelStats.cacheReadInputTokens || 0) -
                  completed.cacheReadTokens;
                const remainingCacheCreation =
                  (modelStats.cacheCreationInputTokens || 0) -
                  completed.cacheCreationTokens;

                // Update the pending message's usage with remaining tokens
                pendingMsg.message.usage.output_tokens = Math.max(
                  0,
                  remainingOutput
                );
                pendingMsg.message.usage.input_tokens = Math.max(
                  0,
                  remainingInput
                );

                if (remainingCacheRead > 0) {
                  pendingMsg.message.usage.cache_read_input_tokens =
                    remainingCacheRead;
                }
                if (remainingCacheCreation > 0) {
                  pendingMsg.message.usage.cache_creation_input_tokens =
                    remainingCacheCreation;
                }
              }
            }
          } else if (message.usage) {
            // Fall back to top-level usage if modelUsage not available
            resultUsage = extractUsageFromMessage(message);
          }

          // Add total_cost if available (LangSmith standard field)
          if (message.total_cost_usd != null && resultUsage) {
            resultUsage.total_cost = message.total_cost_usd;
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

      // Apply usage metadata to the chain run using LangSmith's standard fields
      const currentRun = getCurrentRunTree();
      if (currentRun && resultUsage) {
        // Initialize metadata object if needed
        if (!currentRun.extra) {
          currentRun.extra = {};
        }
        if (!currentRun.extra.metadata) {
          currentRun.extra.metadata = {};
        }

        // Add LangSmith-standard usage fields directly to metadata
        if (resultUsage.input_tokens !== undefined) {
          currentRun.extra.metadata.input_tokens = resultUsage.input_tokens;
        }
        if (resultUsage.output_tokens !== undefined) {
          currentRun.extra.metadata.output_tokens = resultUsage.output_tokens;
        }
        if (resultUsage.total_tokens !== undefined) {
          currentRun.extra.metadata.total_tokens = resultUsage.total_tokens;
        }
        if (resultUsage.input_token_details) {
          currentRun.extra.metadata.input_token_details =
            resultUsage.input_token_details;
        }
        if (resultUsage.total_cost !== undefined) {
          currentRun.extra.metadata.total_cost = resultUsage.total_cost;
        }
      }
    } finally {
      // Clean up parent run reference and any orphaned tool runs
      context.currentParentRun = undefined;
      clearActiveToolRuns(context);
    }
  } as T;

  // Wrap in traceable
  return traceable(wrapped, {
    name: "claude.conversation",
    run_type: "chain",
    ...baseConfig,
    metadata: { ...baseConfig?.metadata },
  }) as T;
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
function buildLLMInput(
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
 * Aggregates usage from modelUsage breakdown (includes all models, including hidden ones).
 * This provides accurate totals when multiple models are used.
 */
function aggregateUsageFromModelUsage(
  modelUsage: Record<string, SDKModelUsage>
): Record<string, unknown> {
  const metrics: Record<string, unknown> = {};

  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalCacheReadTokens = 0;
  let totalCacheCreationTokens = 0;

  // Aggregate across all models
  for (const modelStats of Object.values(modelUsage)) {
    totalInputTokens += modelStats.inputTokens || 0;
    totalOutputTokens += modelStats.outputTokens || 0;
    totalCacheReadTokens += modelStats.cacheReadInputTokens || 0;
    totalCacheCreationTokens += modelStats.cacheCreationInputTokens || 0;
  }

  // Build input_token_details if we have cache tokens
  if (totalCacheReadTokens > 0 || totalCacheCreationTokens > 0) {
    metrics.input_token_details = {
      cache_read: totalCacheReadTokens,
      cache_creation: totalCacheCreationTokens,
    };
  }

  // Sum all input tokens (new + cache read + cache creation)
  const totalPromptTokens =
    totalInputTokens + totalCacheReadTokens + totalCacheCreationTokens;

  metrics.input_tokens = totalPromptTokens;
  metrics.output_tokens = totalOutputTokens;
  metrics.total_tokens = totalPromptTokens + totalOutputTokens;

  return metrics;
}

/**
 * Extracts and normalizes usage metrics from a Claude Agent SDK message.
 */
function extractUsageFromMessage(message: SDKMessage): Record<string, unknown> {
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
async function createLLMSpanForMessages(
  messages: SDKMessage[],
  prompt: string | AsyncIterable<SDKMessage> | undefined,
  conversationHistory: Array<{ content: unknown; role: string }>,
  options: QueryOptions,
  startTime: number,
  context: AgentSDKContext
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
  const usage = extractUsageFromMessage(lastMessage);
  const input = buildLLMInput(prompt, conversationHistory);

  // Flatten content blocks for proper serialization (matches Python)
  const outputs = messages
    .map((m) => {
      if (!("message" in m) || !("role" in m.message)) return undefined;
      return {
        content: flattenContentBlocks(m.message.content),
        role: m.message.role as "assistant" | "user",
      };
    })
    .filter((c) => c !== undefined);

  // Check if this message belongs to a subagent
  // First check if message has explicit parent_tool_use_id
  const parentToolUseId = lastMessage.parent_tool_use_id;
  let subagentParent = parentToolUseId
    ? context.subagentSessions.get(parentToolUseId)
    : undefined;

  // If no explicit parent, check if we're in an active subagent context
  if (!subagentParent && context.activeSubagentToolUseId) {
    subagentParent = context.subagentSessions.get(
      context.activeSubagentToolUseId
    );
  }

  const endTime = Date.now();

  // Format inputs: if we have a single input, use it directly; otherwise wrap as messages
  const formattedInputs =
    input && input.length === 1 ? input[0] : input ? { messages: input } : {};

  if (subagentParent) {
    // Create LLM run as child of subagent session with proper start and end time
    try {
      const llmRun = await subagentParent.createChild({
        name: "claude.assistant.turn",
        run_type: "llm",
        inputs: formattedInputs,
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
    } catch {
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
          inputs: formattedInputs,
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
      } catch {
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
 * Converts SDK content blocks into serializable objects.
 * Matches Python's flatten_content_blocks behavior.
 */
function flattenContentBlocks(
  content: Anthropic.Beta.BetaContentBlock[] | unknown
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
        return { type: "text", text: block.text || "" };
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
  type TypedSdk = T & {
    query?: (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>;
    tool?: (...args: unknown[]) => unknown;
    createSdkMcpServer?: () => unknown;

    unstable_v2_createSession?: (...args: unknown[]) => unknown;
    unstable_v2_prompt?: (...args: unknown[]) => unknown;
    unstable_v2_resumeSession?: (...args: unknown[]) => unknown;
  };

  const inputSdk = sdk as TypedSdk;
  const wrappedSdk = { ...sdk } as TypedSdk;

  if ("query" in inputSdk && isTraceableFunction(inputSdk.query)) {
    throw new Error(
      "This instance of Claude Agent SDK has been already wrapped by `wrapClaudeAgentSDK`."
    );
  }

  // Wrap the query method if it exists
  if ("query" in inputSdk && typeof inputSdk.query === "function") {
    wrappedSdk.query = wrapClaudeAgentQuery(inputSdk.query, inputSdk, config);
  }

  // Wrap the tool method if it exists
  if ("tool" in inputSdk && typeof inputSdk.tool === "function") {
    const originalTool = inputSdk.tool;
    wrappedSdk.tool = function (...args) {
      const toolDef = originalTool.apply(sdk, args);
      if (toolDef && typeof toolDef === "object" && "handler" in toolDef) {
        return wrapClaudeAgentTool(
          toolDef as SdkMcpToolDefinition<unknown>,
          config
        );
      }
      return toolDef;
    };
  }

  // Keep createSdkMcpServer and other methods as-is (bound to original SDK)
  if (
    "createSdkMcpServer" in inputSdk &&
    typeof inputSdk.createSdkMcpServer === "function"
  ) {
    wrappedSdk.createSdkMcpServer = inputSdk.createSdkMcpServer.bind(inputSdk);
  }

  if (
    "unstable_v2_createSession" in inputSdk &&
    typeof inputSdk.unstable_v2_createSession === "function"
  ) {
    wrappedSdk.unstable_v2_createSession = (
      ...args: Parameters<typeof inputSdk.unstable_v2_createSession>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_createSession` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_createSession?.(...args);
    };
  }
  if (
    "unstable_v2_prompt" in inputSdk &&
    typeof inputSdk.unstable_v2_prompt === "function"
  ) {
    wrappedSdk.unstable_v2_prompt = (
      ...args: Parameters<typeof inputSdk.unstable_v2_prompt>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_prompt` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_prompt?.(...args);
    };
  }
  if (
    "unstable_v2_resumeSession" in inputSdk &&
    typeof inputSdk.unstable_v2_resumeSession === "function"
  ) {
    wrappedSdk.unstable_v2_resumeSession = (
      ...args: Parameters<typeof inputSdk.unstable_v2_resumeSession>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_resumeSession` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_resumeSession?.(...args);
    };
  }

  return wrappedSdk as T;
}
