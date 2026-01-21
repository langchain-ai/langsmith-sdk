import {
  traceable,
  getCurrentRunTree,
  isTraceableFunction,
} from "../../traceable.js";
import type { RunTree } from "../../run_trees.js";
import type Anthropic from "@anthropic-ai/sdk";
import { convertAnthropicUsageToInputTokenDetails } from "../../utils/usage.js";
import {
  type AgentSDKContext,
  type WrapClaudeAgentSDKConfig,
  clearActiveToolRuns,
  createQueryContext,
} from "./context.js";
import { getNumberProperty } from "./utils.js";
import type {
  SDKUserMessage,
  SDKMessage,
  SDKAssistantMessage,
  Options as QueryOptions,
  ModelUsage,
  createSdkMcpServer,
} from "@anthropic-ai/claude-agent-sdk";
import { mergeHooks } from "./hooks.js";
import {
  convertFromAnthropicMessage,
  flattenContentBlocks,
} from "./messages.js";

type SdkMcpToolDefinition = Exclude<
  Parameters<typeof createSdkMcpServer>[0]["tools"],
  undefined
>[number];

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
function handleAssistantToolUses(
  message: SDKAssistantMessage,
  parentRun: RunTree | undefined,
  context: AgentSDKContext
): void {
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

        const subagentSession = parentRun.createChild({
          name: subagentName,
          run_type: "chain",
          inputs: block.input,
        });

        // Post the run to start it, but DON'T end it yet
        // It will be ended when we receive the tool result or at cleanup
        context.promiseQueue.push(subagentSession.postRun());

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
        const toolRun = subagentSession.createChild({
          name: block.name || "unknown_tool",
          run_type: "tool",
          inputs: block.input ? { input: block.input } : {},
        });

        context.promiseQueue.push(toolRun.postRun());
        context.clientManagedRuns.set(block.id, toolRun);
      }
    } catch {
      // Silently fail - don't interrupt message processing
    }
  }
}

/**
 * Wraps the Claude Agent SDK's query function to add LangSmith tracing.
 * Traces the entire agent interaction including all streaming messages.
 * Internal use only - use wrapClaudeAgentSDK instead.
 */
function wrapClaudeAgentQuery<
  T extends (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>
>(queryFn: T, defaultThis?: unknown, baseConfig?: WrapClaudeAgentSDKConfig): T {
  const getModifiedArgs = (args: unknown[], context: AgentSDKContext) => {
    const params = (args[0] ?? {}) as {
      prompt?: string | AsyncIterable<SDKMessage>;
      options?: QueryOptions;
    };

    const { prompt, options = {} } = params;

    // Inject LangSmith tracing hooks into options
    const mergedHooks = mergeHooks(options.hooks, context);
    const modifiedOptions = { ...options, hooks: mergedHooks };
    const modifiedParams = { ...params, options: modifiedOptions };
    return {
      prompt,
      options: modifiedOptions,
      modifiedArgs: [modifiedParams, ...args.slice(1)],
    };
  };

  async function* generator(
    originalGenerator: AsyncGenerator<SDKMessage, void, unknown>,
    prompt: string | AsyncIterable<SDKMessage> | undefined,
    options: QueryOptions,
    context: AgentSDKContext
  ) {
    // Track usage from ResultMessage to add to the parent span
    let resultUsage: Record<string, unknown> | undefined;

    // Track additional metadata from the SDK
    const extraMetadata: [key: string, value: unknown][] = [];

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

    // Create an LLM span for a specific message ID
    const createLLMSpanForId = async (messageId: string) => {
      // Skip if we've already created a span for this message ID
      if (context.completedMessageIds.has(messageId)) {
        return;
      }

      const pending = context.pendingMessages.get(messageId);
      if (!pending) return;

      context.pendingMessages.delete(messageId);
      context.completedMessageIds.add(messageId);

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
        pending.messageHistory,
        [pending.message],
        options,
        pending.startTime,
        context
      );

      if (finalMessageContent) context.messageHistory.push(finalMessageContent);
    };

    try {
      for await (const message of originalGenerator) {
        const currentTime = Date.now();

        if (message.type === "system") {
          const content = getLatestInput(prompt);
          if (content != null) context.messageHistory.push(content);
        }

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

          // Check if this is a new message or an update to existing
          const existing = context.pendingMessages.get(messageId);
          if (!existing) {
            // New message arrived - finalize all OTHER pending messages first
            // (they must be complete if we're seeing a new message)
            for (const [otherId] of context.pendingMessages) {
              if (otherId !== messageId) {
                context.promiseQueue.push(createLLMSpanForId(otherId));
              }
            }
          }

          context.pendingMessages.set(message.message.id, {
            message,
            messageHistory: context.messageHistory.slice(0),
            startTime: existing?.startTime ?? currentTime,
          });

          // Push the message to the final results,
          // Used to create spans with the full chat history as input
          if ("content" in message.message && message.message.content) {
            context.messageHistory.push({
              content: flattenContentBlocks(message.message.content),
              role: "assistant",
            });
          }

          // Check if this message has a stop_reason (meaning it's complete)
          // If so, create the span now (createLLMSpanForId will skip if already created)
          if (message.message?.stop_reason) {
            context.promiseQueue.push(createLLMSpanForId(messageId));
          }

          // Process tool uses for subagent detection (matches Python's _handle_assistant_tool_uses)
          await handleAssistantToolUses(
            message,
            context.currentParentRun,
            context
          );
        } else if (message.type === "user") {
          context.messageHistory.push(...convertFromAnthropicMessage(message));

          // If this is a tool result for a Task tool (subagent), we're entering the subagent's execution
          // The subagent's assistant messages will come AFTER this result
          if (
            message.parent_tool_use_id &&
            context.subagentSessions.has(message.parent_tool_use_id)
          ) {
            context.activeSubagentToolUseId = message.parent_tool_use_id;
          }
        } else if (message.type === "result") {
          // If modelUsage is available, aggregate from it (includes ALL models)
          // Otherwise fall back to top-level usage field
          if (message.modelUsage) {
            // Aggregate usage from modelUsage (includes ALL models)
            resultUsage = aggregateUsageFromModelUsage(message.modelUsage);

            // Patch token counts for pending messages using modelUsage
            // This handles the SDK limitation where the last assistant message
            // doesn't receive final streaming updates with accurate token counts
            for (const [, { message: pendingMsg }] of context.pendingMessages) {
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

          // Add conversation-level metadata
          if (message.is_error != null) {
            extraMetadata.push(["is_error", message.is_error]);
          }
          if (message.num_turns != null) {
            extraMetadata.push(["num_turns", message.num_turns]);
          }
          if (message.session_id != null) {
            extraMetadata.push(["session_id", message.session_id]);
          }

          if (message.duration_ms != null) {
            extraMetadata.push(["duration_ms", message.duration_ms]);
          }
          if (message.duration_api_ms != null) {
            extraMetadata.push(["duration_api_ms", message.duration_api_ms]);
          }
        }

        yield message;
      }

      // Create spans for any remaining pending messages (those without stop_reason)
      for (const messageId of context.pendingMessages.keys()) {
        context.promiseQueue.push(createLLMSpanForId(messageId));
      }

      // Wait for all child runs to complete
      await Promise.allSettled(context.promiseQueue);

      // Apply usage metadata to the chain run using LangSmith's standard fields
      const currentRun = getCurrentRunTree();
      if (currentRun && (resultUsage || extraMetadata.length > 0)) {
        // Initialize metadata object if needed
        currentRun.extra ||= {};
        currentRun.extra.metadata ||= {};

        if (resultUsage) {
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

        for (const [key, value] of extraMetadata) {
          currentRun.extra.metadata[key] = value;
        }
      }
    } finally {
      // Clean up parent run reference and any orphaned tool runs
      context.currentParentRun = undefined;
      clearActiveToolRuns(context);
    }
  }

  const wrapped = (...args: unknown[]) => {
    const context = createQueryContext();
    context.currentParentRun = getCurrentRunTree();

    const { prompt, options, modifiedArgs } = getModifiedArgs(args, context);
    const actualGenerator = queryFn.call(defaultThis, ...modifiedArgs);
    const wrappedGenerator = generator(
      actualGenerator,
      prompt,
      options,
      context
    );

    for (const method of Object.getOwnPropertyNames(
      Object.getPrototypeOf(actualGenerator)
    ).filter(
      (method) => !["constructor", "next", "throw", "return"].includes(method)
    )) {
      Object.defineProperty(wrappedGenerator, method, {
        get() {
          const getValue =
            actualGenerator?.[method as keyof typeof actualGenerator];
          if (typeof getValue === "function")
            return getValue.bind(actualGenerator);
          return getValue;
        },
      });
    }

    return wrappedGenerator;
  };

  const processInputs = async (rawInputs: unknown) => {
    const inputs = rawInputs as {
      prompt: string | AsyncIterable<SDKUserMessage>;
      options: QueryOptions;
    };

    const newInputs = { ...inputs };
    return Object.assign(newInputs, {
      toJSON: () => {
        const toJSON = (value: unknown) => {
          if (typeof value !== "object" || value == null) return value;
          const fn = (value as Record<string, unknown>)?.toJSON;
          if (typeof fn === "function") return fn();
          return value;
        };

        const prompt = toJSON(inputs.prompt) as
          | string
          | Iterable<SDKUserMessage>
          | undefined;
        const options = toJSON(inputs.options) as QueryOptions | undefined;

        const messages = (() => {
          if (prompt == null) return undefined;

          const result: Array<{ content: unknown; role: string }> = [];
          if (typeof prompt === "string") {
            result.push({ content: prompt, role: "user" });
          } else {
            for (const { message } of prompt) {
              if (!message) continue;
              result.push({
                content: flattenContentBlocks(message.content),
                role: message.role,
              });
            }
          }

          return result;
        })();

        return { messages, options };
      },
    });
  };

  const processOutputs = (rawOutputs: Record<string, unknown>) => {
    if ("outputs" in rawOutputs && Array.isArray(rawOutputs.outputs)) {
      const sdkMessages = rawOutputs.outputs as SDKMessage[];
      const messages = sdkMessages.flatMap(convertFromAnthropicMessage);

      return { output: { messages } };
    }
    return rawOutputs;
  };

  // Wrap in traceable
  return traceable(wrapped, {
    name: "claude.conversation",
    run_type: "chain",
    ...baseConfig,
    metadata: { ...baseConfig?.metadata },
    __deferredSerializableArgOptions: { maxDepth: 1 },
    processInputs,
    processOutputs,
  }) as unknown as T;
}

/**
 * Wraps a Claude Agent SDK tool definition to add LangSmith tracing for tool executions.
 * Internal use only - use wrapClaudeAgentSDK instead.
 */
function wrapClaudeAgentTool(
  toolDef: SdkMcpToolDefinition,
  baseConfig?: WrapClaudeAgentSDKConfig
): SdkMcpToolDefinition {
  return {
    ...toolDef,
    handler: traceable(toolDef.handler, {
      name: toolDef.name,
      run_type: "tool",
      ...baseConfig,
    }),
  };
}

/**
 * Aggregates usage from modelUsage breakdown (includes all models, including hidden ones).
 * This provides accurate totals when multiple models are used.
 */
function aggregateUsageFromModelUsage(
  modelUsage: Record<string, ModelUsage>
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

function getLatestInput(
  arg: string | AsyncIterable<SDKMessage> | undefined
): { content: unknown; role: string } | undefined {
  const value = (() => {
    if (typeof arg !== "object" || arg == null) return arg;

    const toJSON = (arg as unknown as Record<string, unknown>)["toJSON"];
    if (typeof toJSON !== "function") return undefined;
    const latest = toJSON();
    return latest?.at(-1);
  })();

  if (typeof value == null) return undefined;
  if (typeof value === "string") return { content: value, role: "user" };

  const userMessage = value as SDKUserMessage | string | undefined;
  if (typeof userMessage === "string") {
    return { content: userMessage, role: "user" };
  }

  if (typeof userMessage !== "object" || userMessage == null) {
    return undefined;
  }

  return {
    role: userMessage.message.role || "user",
    content: flattenContentBlocks(userMessage.message.content),
  };
}

/**
 * Creates an LLM span for a group of messages with the same message ID.
 * Returns the final message content to add to conversation history.
 * Handles subagent LLM turns by parenting them to the correct subagent session.
 */
function createLLMSpanForMessages(
  input: Array<{ content: unknown; role: string }>,
  output: SDKMessage[],
  options: QueryOptions,
  startTime: number,
  context: AgentSDKContext
): { content: unknown; role: string } | undefined {
  const lastMessage = output.at(-1);
  if (!lastMessage || lastMessage.type !== "assistant") return undefined;

  // Extract model from message first, fall back to options (matches Python)
  const model = lastMessage.message.model || options.model;
  const usage = extractUsageFromMessage(lastMessage);

  // Flatten content blocks for proper serialization (matches Python)
  const outputs = output
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

  const parent = (() => {
    let subagentParent = parentToolUseId
      ? context.subagentSessions.get(parentToolUseId)
      : undefined;

    // If no explicit parent, check if we're in an active subagent context
    if (!subagentParent && context.activeSubagentToolUseId) {
      subagentParent = context.subagentSessions.get(
        context.activeSubagentToolUseId
      );
    }

    if (subagentParent) return subagentParent;
    return getCurrentRunTree();
  })();

  context.promiseQueue.push(
    parent
      .createChild({
        name: "claude.assistant.turn",
        run_type: "llm",
        inputs: { messages: input },
        outputs: outputs[outputs.length - 1] || { content: outputs },
        start_time: startTime,
        end_time: Date.now(),
        extra: {
          metadata: {
            ...(model ? { ls_model_name: model } : {}),
            usage_metadata: usage,
          },
        },
      })
      .postRun()
  );

  return outputs.at(-1);
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
        return wrapClaudeAgentTool(toolDef as SdkMcpToolDefinition, config);
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
