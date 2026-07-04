import type Anthropic from "@anthropic-ai/sdk";
import type { Stream } from "@anthropic-ai/sdk/streaming";
import type { MessageStream } from "@anthropic-ai/sdk/lib/MessageStream";
import type { RunTreeConfig } from "../index.js";
import {
  getCurrentRunTree,
  isTraceableFunction,
  traceable,
  TraceableConfig,
} from "../traceable.js";
import { KVMap } from "../schemas.js";
import { RunTree } from "../run_trees.js";
import { convertAnthropicUsageToInputTokenDetails } from "../utils/usage.js";
import type {
  BetaManagedAgentsStreamSessionEvents,
  BetaManagedAgentsSession,
} from "@anthropic-ai/sdk/resources/beta/sessions/index.mjs";

const TRACED_INVOCATION_KEYS = ["top_k", "top_p", "stream", "thinking"];

type ExtraRunTreeConfig = Pick<
  Partial<RunTreeConfig>,
  "name" | "metadata" | "tags"
>;

// Type definitions for Anthropic SDK
type MessagesNamespace = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  create: (...args: any[]) => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parse?: (...args: any[]) => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  stream: (...args: any[]) => any;
};

type ManagedAgentsEventsNamespace = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  stream: (...args: any[]) => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  send: (...args: any[]) => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  list?: (...args: any[]) => any;
};

type AnthropicType = {
  messages: MessagesNamespace;
  beta?: {
    messages?: MessagesNamespace;
    sessions?: {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      retrieve?: (...args: any[]) => any;
      events?: ManagedAgentsEventsNamespace;
    };
  };
};

type PatchedAnthropicClient<T extends AnthropicType> = T & {
  messages: T["messages"] & {
    create: {
      (
        arg: Anthropic.MessageCreateParamsStreaming,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        },
      ): Promise<Stream<Anthropic.MessageStreamEvent>>;
    } & {
      (
        arg: Anthropic.MessageCreateParamsNonStreaming,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        },
      ): Promise<Anthropic.Message>;
    };
    stream: {
      (
        arg: Anthropic.MessageStreamParams,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        },
      ): MessageStream;
    };
  };
};

/**
 * Create usage metadata from Anthropic's token usage format.
 */
export function createUsageMetadata(
  anthropicUsage: Partial<Anthropic.Messages.Usage> | undefined,
): KVMap | undefined {
  if (!anthropicUsage) {
    return undefined;
  }

  const inputTokens =
    typeof anthropicUsage.input_tokens === "number"
      ? anthropicUsage.input_tokens
      : 0;
  const outputTokens =
    typeof anthropicUsage.output_tokens === "number"
      ? anthropicUsage.output_tokens
      : 0;

  const inputTokenDetails: Record<string, number> =
    convertAnthropicUsageToInputTokenDetails(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      anthropicUsage as Record<string, any>,
    );

  // Anthropic cache tokens are ADDITIVE (not subsets of input_tokens like OpenAI).
  // Sum them into input_tokens so the backend cost calculation is correct.
  const cacheTokenSum = Object.values(inputTokenDetails).reduce(
    (sum, v) => sum + (v ?? 0),
    0,
  );
  const adjustedInputTokens = inputTokens + cacheTokenSum;
  const adjustedTotalTokens = adjustedInputTokens + outputTokens;

  return {
    input_tokens: adjustedInputTokens,
    output_tokens: outputTokens,
    total_tokens: adjustedTotalTokens,
    ...(Object.keys(inputTokenDetails).length > 0 && {
      input_token_details: inputTokenDetails,
    }),
  };
}

/**
 * Process Anthropic message outputs
 */
function processMessageOutput(outputs: KVMap): KVMap {
  const message = outputs as Anthropic.Message;

  const result: KVMap = { ...message };
  delete result.type;

  if (message.usage) {
    result.usage_metadata = createUsageMetadata(message.usage);
    delete result.usage;
  }

  return result;
}

/**
 * Accumulate a single content block delta into the content array.
 */
function accumulateContentBlockDelta(
  content: Anthropic.ContentBlock[],
  event: Anthropic.ContentBlockDeltaEvent,
): void {
  const block = content[event.index];
  if (!block) return;

  if (block.type === "text" && event.delta.type === "text_delta") {
    (block as Anthropic.TextBlock).text += event.delta.text;
  } else if (
    block.type === "tool_use" &&
    event.delta.type === "input_json_delta"
  ) {
    // Accumulate JSON input for tool use
    const toolBlock = block as Anthropic.ToolUseBlock & {
      _partial_json?: string;
    };
    toolBlock._partial_json =
      (toolBlock._partial_json ?? "") + event.delta.partial_json;
  }
}

/**
 * Aggregate streaming chunks into a complete message response
 */
const messageAggregator = (chunks: Anthropic.MessageStreamEvent[]): KVMap => {
  if (!chunks || chunks.length === 0) {
    return {
      role: "assistant",
      content: [],
    };
  }

  let message: Partial<Anthropic.Message> = {
    role: "assistant",
    content: [],
    model: "",
    stop_reason: null,
    stop_sequence: null,
  };

  // Track usage
  let usage: Partial<Anthropic.Messages.Usage> = {
    input_tokens: 0,
    output_tokens: 0,
  };

  for (const chunk of chunks) {
    switch (chunk.type) {
      case "message_start":
        // Initialize message
        message = {
          id: chunk.message.id,
          role: chunk.message.role,
          content: [],
          model: chunk.message.model,
          stop_reason: chunk.message.stop_reason,
          stop_sequence: chunk.message.stop_sequence,
        };
        // Capture initial usage
        if (chunk.message.usage) {
          usage = chunk.message.usage;
        }
        break;

      case "content_block_start":
        // Add new content block
        if (message.content) {
          (message.content as Anthropic.ContentBlock[])[chunk.index] =
            chunk.content_block as Anthropic.ContentBlock;
        }
        break;

      case "content_block_delta":
        // Accumulate delta
        if (message.content) {
          accumulateContentBlockDelta(
            message.content as Anthropic.ContentBlock[],
            chunk,
          );
        }
        break;

      case "content_block_stop":
        // Finalize content block
        if (message.content) {
          const block = (message.content as Anthropic.ContentBlock[])[
            chunk.index
          ];
          if (block?.type === "tool_use") {
            const toolBlock = block as Anthropic.ToolUseBlock & {
              _partial_json?: string;
            };
            if (toolBlock._partial_json) {
              try {
                toolBlock.input = JSON.parse(toolBlock._partial_json);
              } catch {
                // Keep partial JSON as-is if parsing fails
                toolBlock.input = toolBlock._partial_json;
              }
              delete toolBlock._partial_json;
            }
          }
        }
        break;

      case "message_delta":
        // Update message metadata
        message.stop_reason = chunk.delta.stop_reason;
        message.stop_sequence = chunk.delta.stop_sequence ?? null;
        if (chunk.usage) {
          // Override only non-null keys
          for (const [key, value] of Object.entries(chunk.usage)) {
            if (value != null) {
              (usage as Record<string, unknown>)[key] = value;
            }
          }
        }
        break;

      case "message_stop":
        // Message complete
        break;
    }
  }

  // Build final output
  const result: KVMap = {
    ...message,
  };
  delete result.type;

  // Add usage metadata
  result.usage_metadata = createUsageMetadata(usage);

  return result;
};

type OnlyType<TType extends BetaManagedAgentsStreamSessionEvents["type"]> =
  BetaManagedAgentsStreamSessionEvents extends infer TEvent
    ? TEvent extends { type: TType }
      ? TEvent
      : never
    : never;

function processManagedAgentStreamInputs(inputs: KVMap): KVMap {
  const args = Array.isArray(inputs.args) ? inputs.args : [];
  const [sessionID, params, requestOptions] =
    args.length > 0 ? args : [inputs.input, undefined, undefined];
  return {
    session_id: sessionID,
    ...(params ? { stream_params: params } : {}),
    ...(requestOptions ? { request_options: requestOptions } : {}),
  };
}

function getManagedAgentText(content: unknown): string {
  if (!Array.isArray(content)) return "";
  return content
    .map((block) => {
      if (
        typeof block === "object" &&
        block != null &&
        "type" in block &&
        block.type === "text" &&
        "text" in block &&
        typeof block.text === "string"
      ) {
        return block.text;
      }
      return "";
    })
    .join("");
}

function managedAgentSessionEventsAggregator(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): KVMap {
  const messages: KVMap[] = [];
  const toolCalls: KVMap[] = [];
  const toolResults: KVMap[] = [];
  const errors: KVMap[] = [];
  const modelRequests: KVMap[] = [];
  const previews = new Map<string, Map<number, string>>();

  let status: string | undefined;
  let stopReason: unknown;
  const usage = {
    input_tokens: 0,
    output_tokens: 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
  };

  for (const event of chunks) {
    switch (event.type) {
      case "agent.message": {
        event.content;
        messages.push({
          id: event.id,
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
          processed_at: event.processed_at,
        });
        if (typeof event.id === "string") previews.delete(event.id);
        break;
      }
      case "agent.tool_use":
      case "agent.mcp_tool_use":
      case "agent.custom_tool_use": {
        toolCalls.push({ ...event });
        break;
      }
      case "agent.tool_result":
      case "agent.mcp_tool_result": {
        toolResults.push({ ...event });
        break;
      }
      case "span.model_request_end": {
        const modelUsage = event.model_usage;
        if (modelUsage) {
          for (const key of Object.keys(usage) as Array<keyof typeof usage>) {
            const value = modelUsage[key];
            if (typeof value === "number") usage[key] += value;
          }
          modelRequests.push({
            id: event.id,
            is_error: event.is_error,
            model_request_start_id: event.model_request_start_id,
            model_usage: modelUsage,
            processed_at: event.processed_at,
          });
        }
        previews.clear();
        break;
      }
      case "session.error":
        errors.push({ ...event });
        break;
      case "session.status_running":
      case "session.status_idle":
      case "session.status_rescheduled":
      case "session.status_terminated":
        status = event.type;
        if (event.type === "session.status_idle") {
          stopReason = event.stop_reason;
        }
        break;
      case "agent.thinking":
      case "agent.thread_context_compacted":
      case "agent.thread_message_received":
      case "agent.thread_message_sent":
      case "session.deleted":
      case "session.thread_created":
      case "session.thread_status_idle":
      case "session.thread_status_running":
      case "session.thread_status_terminated":
      case "session.thread_status_rescheduled":
      case "span.model_request_start":
      case "session.updated":
      case "span.outcome_evaluation_start":
      case "span.outcome_evaluation_ongoing":
      case "span.outcome_evaluation_end":
      case "user.custom_tool_result":
      case "user.define_outcome":
      case "user.interrupt":
      case "user.message":
      case "user.tool_confirmation":
      case "user.tool_result":
        break;
    }
  }

  const unreconciledPreviews = [...previews.entries()].map(
    ([eventID, byIndex]) => ({
      id: eventID,
      text: [...byIndex.entries()]
        .sort(([left], [right]) => left - right)
        .map(([, text]) => text)
        .join(""),
    }),
  );
  const messageEvents = chunks.filter(
    (event) => event.type === "agent.message",
  );
  return {
    content: messageEvents.flatMap((message) =>
      Array.isArray(message.content) ? message.content : [],
    ),
    messages: getManagedAgentAssistantOutputMessages(chunks),
    tool_calls: toolCalls,
    tool_results: toolResults,
    errors,
    model_requests: modelRequests,
    status,
    stop_reason: stopReason,
    events: chunks,
    ...(unreconciledPreviews.length > 0
      ? { unreconciled_previews: unreconciledPreviews }
      : {}),
  };
}

function getManagedAgentInputEvents(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): BetaManagedAgentsStreamSessionEvents[] {
  return chunks
    .filter(
      (event) =>
        typeof event.type === "string" &&
        (event.type.startsWith("user.") || event.type.startsWith("system.")),
    )
    .map((event) => ({ ...event }));
}

function contentBlocksToChatContent(content: unknown): unknown {
  if (!Array.isArray(content)) return content;
  const text = getManagedAgentText(content);
  return text.length > 0 &&
    content.every((block) => {
      return (
        typeof block === "object" &&
        block != null &&
        "type" in block &&
        block.type === "text"
      );
    })
    ? text
    : content;
}

function managedAgentToolUseToContentBlock(
  event: OnlyType<
    "agent.tool_use" | "agent.mcp_tool_use" | "agent.custom_tool_use"
  >,
): KVMap {
  return {
    type: "tool_use",
    id: event.id,
    name: event.name,
    input: event.input,
    ...(event.type === "agent.mcp_tool_use"
      ? { mcp_server_name: event.mcp_server_name }
      : {}),
  };
}

function getManagedAgentChatMessages(
  events: BetaManagedAgentsStreamSessionEvents[],
): KVMap[] {
  const messages: KVMap[] = [];
  for (const event of events) {
    switch (event.type) {
      case "user.message":
        messages.push({
          role: "user",
          content: contentBlocksToChatContent(event.content),
        });
        break;
      case "agent.message":
        messages.push({
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
        });
        break;
      case "agent.tool_use":
      case "agent.mcp_tool_use":
      case "agent.custom_tool_use":
        messages.push({
          role: "assistant",
          content: [managedAgentToolUseToContentBlock(event)],
        });
        break;
      case "agent.tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
      case "agent.mcp_tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.mcp_tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
      case "user.custom_tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.custom_tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
    }
  }
  return messages;
}

function getManagedAgentAssistantOutputMessages(
  events: BetaManagedAgentsStreamSessionEvents[],
): KVMap[] {
  return events.flatMap((event) => {
    if (event.type === "agent.message") {
      return [
        {
          id: event.id,
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
          processed_at: event.processed_at,
        },
      ];
    }
    if (
      event.type === "agent.tool_use" ||
      event.type === "agent.mcp_tool_use" ||
      event.type === "agent.custom_tool_use"
    ) {
      return [
        {
          id: event.id,
          role: "assistant",
          content: [managedAgentToolUseToContentBlock(event)],
          processed_at: event.processed_at,
        },
      ];
    }
    return [];
  });
}

function getManagedAgentStreamError(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): string | undefined {
  const errorEvent = chunks.find((event) => event.type === "session.error");
  const error = errorEvent?.error;
  if (typeof error === "object" && error != null && "message" in error) {
    return String(error.message);
  }
  return undefined;
}

function stripLangSmithExtraFromRequestOptions<T>(options: T): T {
  if (
    typeof options === "object" &&
    options != null &&
    "langsmithExtra" in options
  ) {
    const { langsmithExtra: _langsmithExtra, ...rest } = options;
    return rest as T;
  }
  return options;
}

function getProcessedAtMillis(
  event: BetaManagedAgentsStreamSessionEvents,
): number | undefined {
  return typeof event.processed_at === "string"
    ? Date.parse(event.processed_at)
    : undefined;
}

async function postCompletedChildRun(
  childRun: RunTree,
  outputs: KVMap,
  error?: string,
  endTime?: number,
): Promise<void> {
  await childRun.end(outputs, error, endTime);
  await childRun.postRun();
}

async function createManagedAgentChildRuns(
  parentRun: RunTree,
  chunks: BetaManagedAgentsStreamSessionEvents[],
  metadata: KVMap,
  modelConfig?: KVMap,
): Promise<void> {
  const modelName =
    typeof modelConfig?.id === "string" ? modelConfig.id : undefined;
  const modelRequestStarts = new Map<
    string,
    BetaManagedAgentsStreamSessionEvents
  >();
  const childSpecs: Array<{
    startTime: number;
    index: number;
    createAndPost: () => Promise<void>;
  }> = [];

  const toolUseEvents = new Map<
    string,
    OnlyType<"agent.tool_use" | "agent.mcp_tool_use" | "agent.custom_tool_use">
  >();
  const toolResultEvents = new Map<
    string,
    OnlyType<
      "agent.tool_result" | "agent.mcp_tool_result" | "user.custom_tool_result"
    >
  >();

  for (const event of chunks) {
    if (
      event.type === "span.model_request_start" &&
      typeof event.id === "string"
    ) {
      modelRequestStarts.set(event.id, event);
    } else if (event.type === "span.model_request_end") {
      const startID =
        typeof event.model_request_start_id === "string"
          ? event.model_request_start_id
          : undefined;

      const startEvent = startID ? modelRequestStarts.get(startID) : undefined;
      const startIndex = startEvent ? chunks.indexOf(startEvent) : -1;
      const endIndex = chunks.indexOf(event);
      const eventsBeforeRequest =
        startIndex >= 0 ? chunks.slice(0, startIndex) : [];
      const eventsInRequest =
        startIndex >= 0 && endIndex >= startIndex
          ? chunks.slice(startIndex, endIndex + 1)
          : [event];
      const messageEvents = eventsInRequest.filter(
        (candidate) => candidate.type === "agent.message",
      );
      const messages = getManagedAgentAssistantOutputMessages(eventsInRequest);
      const toolCalls = eventsInRequest.filter(
        (candidate) =>
          candidate.type === "agent.tool_use" ||
          candidate.type === "agent.mcp_tool_use" ||
          candidate.type === "agent.custom_tool_use",
      );
      const content = messageEvents.flatMap((message) =>
        Array.isArray(message.content) ? message.content : [],
      );

      const usageMetadata = createUsageMetadata(event.model_usage);
      const startTime = startEvent
        ? (getProcessedAtMillis(startEvent) ?? Date.now())
        : Date.now();
      childSpecs.push({
        startTime,
        index: startIndex >= 0 ? startIndex : endIndex,
        createAndPost: async () => {
          const childRun = parentRun.createChild({
            name: "ClaudeManagedAgentModelRequest",
            run_type: "llm",
            inputs: {
              events: eventsBeforeRequest,
              messages: getManagedAgentChatMessages(eventsBeforeRequest),
              ...(startEvent ? { model_request_start: startEvent } : {}),
            },
            metadata: {
              ...metadata,
              ...(modelName ? { ls_model_name: modelName } : {}),
              ...(modelConfig
                ? {
                    ls_invocation_params: {
                      ...((metadata.ls_invocation_params as
                        | KVMap
                        | undefined) ?? {}),
                      model_config: modelConfig,
                    },
                  }
                : {}),
              ...(usageMetadata ? { usage_metadata: usageMetadata } : {}),
            },
            start_time: startTime,
          });
          await postCompletedChildRun(
            childRun,
            {
              content,
              messages,
              tool_calls: toolCalls,
              model_request_end: event,
              ...(event.model_usage ? { model_usage: event.model_usage } : {}),
              ...(usageMetadata ? { usage_metadata: usageMetadata } : {}),
            },
            event.is_error ? "Model request failed" : undefined,
            getProcessedAtMillis(event),
          );
        },
      });
    } else if (
      (event.type === "agent.tool_use" ||
        event.type === "agent.mcp_tool_use" ||
        event.type === "agent.custom_tool_use") &&
      typeof event.id === "string"
    ) {
      toolUseEvents.set(event.id, event);
    } else if (
      event.type === "agent.tool_result" &&
      typeof event.tool_use_id === "string"
    ) {
      toolResultEvents.set(event.tool_use_id, event);
    } else if (
      event.type === "agent.mcp_tool_result" &&
      typeof event.mcp_tool_use_id === "string"
    ) {
      toolResultEvents.set(event.mcp_tool_use_id, event);
    } else if (
      event.type === "user.custom_tool_result" &&
      typeof event.custom_tool_use_id === "string"
    ) {
      toolResultEvents.set(event.custom_tool_use_id, event);
    }
  }

  for (const [toolUseID, toolUse] of toolUseEvents.entries()) {
    const result = toolResultEvents.get(toolUseID);
    const toolName =
      typeof toolUse.name === "string" ? toolUse.name : "ManagedAgentTool";
    const startTime = getProcessedAtMillis(toolUse) ?? Date.now();
    childSpecs.push({
      startTime,
      index: chunks.indexOf(toolUse),
      createAndPost: async () => {
        const childRun = parentRun.createChild({
          name: toolName,
          run_type: "tool",
          inputs: {
            id: toolUseID,
            name: toolUse.name,
            input: toolUse.input,
            event: toolUse,
          },
          metadata,
          start_time: startTime,
        });
        await postCompletedChildRun(
          childRun,
          result ? { event: result, content: result.content } : {},
          result?.is_error ? "Tool execution failed" : undefined,
          result ? getProcessedAtMillis(result) : undefined,
        );
      },
    });
  }

  childSpecs.sort(
    (left, right) =>
      left.startTime - right.startTime || left.index - right.index,
  );
  for (const childSpec of childSpecs) {
    await childSpec.createAndPost();
  }
}

/**
 * Wraps an Anthropic client's completion methods, enabling automatic LangSmith
 * tracing. Method signatures are unchanged, with the exception that you can pass
 * an additional and optional "langsmithExtra" field within the second parameter.
 *
 * @param anthropic An Anthropic client instance.
 * @param options LangSmith options.
 * @returns The wrapped client.
 *
 * @example
 * ```ts
 * import Anthropic from "@anthropic-ai/sdk";
 * import { wrapAnthropic } from "langsmith/wrappers/anthropic";
 *
 * const anthropic = wrapAnthropic(new Anthropic());
 *
 * // Non-streaming
 * const message = await anthropic.messages.create({
 *   model: "claude-sonnet-4-20250514",
 *   max_tokens: 1024,
 *   messages: [{ role: "user", content: "Hello!" }],
 * });
 *
 * // Streaming
 * const messageStream = anthropic.messages.stream({
 *   model: "claude-sonnet-4-20250514",
 *   max_tokens: 1024,
 *   messages: [{ role: "user", content: "Hello!" }],
 * });
 * const finalMessage = await messageStream.finalMessage();
 * ```
 */
export const wrapAnthropic = <T extends AnthropicType>(
  anthropic: T,
  options?: Partial<RunTreeConfig>,
): PatchedAnthropicClient<T> => {
  if (
    isTraceableFunction(anthropic.messages.create) ||
    isTraceableFunction(anthropic.messages.stream) ||
    (anthropic.beta?.sessions?.events?.stream &&
      isTraceableFunction(anthropic.beta.sessions.events.stream)) ||
    (anthropic.beta?.sessions?.events?.send &&
      isTraceableFunction(anthropic.beta.sessions.events.send))
  ) {
    throw new Error(
      "This instance of Anthropic client has been already wrapped once.",
    );
  }

  const tracedAnthropicClient = { ...anthropic };

  // Extract ls_invocation_params from metadata
  const prepopulatedInvocationParams =
    typeof options?.metadata?.ls_invocation_params === "object"
      ? options.metadata.ls_invocation_params
      : {};

  // Remove ls_invocation_params from metadata to avoid duplication
  const { ls_invocation_params, ...restMetadata } = options?.metadata ?? {};
  const cleanedOptions = {
    ...options,
    metadata: restMetadata,
  };

  const createManagedAgentStreamRun = (
    sessionID: string,
    params?: KVMap,
    requestOptions?: { langsmithExtra?: Partial<RunTreeConfig> },
  ) => {
    const runtimeConfig = requestOptions?.langsmithExtra ?? {};
    const parentRun = getCurrentRunTree(true);
    const runConfig: RunTreeConfig = {
      ...cleanedOptions,
      ...runtimeConfig,
      name: runtimeConfig.name ?? cleanedOptions.name ?? "ClaudeManagedAgent",
      run_type: "chain",
      inputs: { session_id: sessionID },
      tags: [
        ...new Set([
          ...(cleanedOptions.tags ?? []),
          ...(runtimeConfig.tags ?? []),
        ]),
      ],
      metadata: {
        ...cleanedOptions.metadata,
        ...runtimeConfig.metadata,
        ls_provider: "anthropic",
        ls_model_type: "chat",
        thread_id: sessionID,
        ls_invocation_params: {
          ...prepopulatedInvocationParams,
          session_id: sessionID,
          ...(params ?? {}),
        },
      },
    };
    return parentRun
      ? parentRun.createChild(runConfig)
      : new RunTree(runConfig);
  };

  /**
   * Transform system parameter into visible message for playground editability.
   * This provides parity with the Python SDK behavior and enables system prompts
   * to be viewed and edited in the LangSmith playground.
   */
  function processSystemMessage(
    params: Record<string, unknown>,
  ): Record<string, unknown> {
    if (!params.system) {
      return params;
    }

    const processed = { ...params };

    // Handle both string and ContentBlock[] formats
    const systemContent = Array.isArray(params.system)
      ? params.system
          .map((block: string | { text: string; type?: string }) =>
            typeof block === "string" ? block : block.text,
          )
          .join("\n")
      : params.system;

    // Transform into first message
    processed.messages = [
      { role: "system" as const, content: systemContent },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ...((params as any).messages || []),
    ];

    delete processed.system;

    return processed;
  }

  // Common configuration for messages.create
  const messagesCreateConfig: TraceableConfig<
    typeof anthropic.messages.create
  > = {
    name: "ChatAnthropic",
    run_type: "llm",
    aggregator: messageAggregator,
    argsConfigPath: [1, "langsmithExtra"],
    processInputs: processSystemMessage,
    getInvocationParams: (payload: unknown) => {
      if (typeof payload !== "object" || payload == null) return undefined;
      const params = payload as Anthropic.MessageCreateParams;

      const ls_stop =
        (typeof params.stop_sequences === "string"
          ? [params.stop_sequences]
          : params.stop_sequences) ?? undefined;

      const ls_invocation_params: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(params)) {
        if (TRACED_INVOCATION_KEYS.includes(key)) {
          ls_invocation_params[key] = value;
        }
      }

      return {
        ls_provider: "anthropic",
        ls_model_type: "chat",
        ls_model_name: params.model,
        ls_max_tokens: params.max_tokens ?? undefined,
        ls_temperature: params.temperature ?? undefined,
        ls_stop,
        ls_invocation_params: {
          ...prepopulatedInvocationParams,
          ...ls_invocation_params,
        },
      };
    },
    processOutputs: processMessageOutput,
    ...cleanedOptions,
  };

  // Create a new messages object preserving the prototype
  tracedAnthropicClient.messages = Object.create(
    Object.getPrototypeOf(anthropic.messages),
  );

  // Copy all own properties
  Object.assign(tracedAnthropicClient.messages, anthropic.messages);

  // Wrap messages.create
  tracedAnthropicClient.messages.create = traceable(
    anthropic.messages.create.bind(anthropic.messages),
    messagesCreateConfig,
  );

  // Shared function to wrap stream methods
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wrapStreamMethod = (originalStreamFn: (...args: any[]) => any) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return function (...args: any[]) {
      const stream = originalStreamFn(...args);
      if (
        "finalMessage" in stream &&
        typeof stream.finalMessage === "function"
      ) {
        const originalFinalMessage = stream.finalMessage.bind(stream);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        stream.finalMessage = async (...args: any[]) => {
          if ("done" in stream && typeof stream.done === "function") {
            await stream.done();
          }
          for await (const _ of stream) {
            // Finish consuming the stream if it has not already been consumed
            // It should be relatively uncommon to consume an iterator after calling
            // .finalMessage()
          }
          return originalFinalMessage(...args);
        };
      }
      return stream;
    };
  };

  // Wrap messages.stream
  tracedAnthropicClient.messages.stream = traceable(
    wrapStreamMethod(anthropic.messages.stream.bind(anthropic.messages)),
    {
      name: "ChatAnthropic",
      run_type: "llm",
      aggregator: messageAggregator,
      argsConfigPath: [1, "langsmithExtra"],
      processInputs: processSystemMessage,
      getInvocationParams: messagesCreateConfig.getInvocationParams,
      processOutputs: processMessageOutput,
      ...cleanedOptions,
    },
  );

  if (anthropic.beta) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tracedBeta = { ...anthropic.beta } as any;

    // Wrap beta.messages if it exists
    if (
      anthropic.beta.messages &&
      typeof anthropic.beta.messages.create === "function"
    ) {
      tracedBeta.messages = Object.create(
        Object.getPrototypeOf(anthropic.beta.messages),
      );
      Object.assign(tracedBeta.messages, anthropic.beta.messages);

      // Wrap beta.messages.create
      tracedBeta.messages.create = traceable(
        anthropic.beta.messages.create.bind(anthropic.beta.messages),
        messagesCreateConfig,
      );

      // Wrap beta.messages.parse if it exists
      if (typeof anthropic.beta.messages.parse === "function") {
        tracedBeta.messages.parse = traceable(
          anthropic.beta.messages.parse.bind(anthropic.beta.messages),
          messagesCreateConfig,
        );
      }

      // Wrap beta.messages.stream if it exists
      if (typeof anthropic.beta.messages.stream === "function") {
        tracedBeta.messages.stream = traceable(
          wrapStreamMethod(
            anthropic.beta.messages.stream.bind(anthropic.beta.messages),
          ),
          {
            name: "ChatAnthropic",
            run_type: "llm",
            aggregator: messageAggregator,
            argsConfigPath: [1, "langsmithExtra"],
            processInputs: processSystemMessage,
            getInvocationParams: messagesCreateConfig.getInvocationParams,
            processOutputs: processMessageOutput,
            ...cleanedOptions,
          },
        );
      }
    }

    // Wrap Claude Managed Agents session event methods if they exist.
    if (anthropic.beta.sessions?.events) {
      tracedBeta.sessions = Object.create(
        Object.getPrototypeOf(anthropic.beta.sessions),
      );
      Object.assign(tracedBeta.sessions, anthropic.beta.sessions);
      tracedBeta.sessions.events = Object.create(
        Object.getPrototypeOf(anthropic.beta.sessions.events),
      );
      Object.assign(tracedBeta.sessions.events, anthropic.beta.sessions.events);

      if (typeof anthropic.beta.sessions.events.stream === "function") {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const streamManagedAgentEvents = async function (...args: any[]) {
          const [sessionID, params, requestOptions] = args as [
            string,
            KVMap | undefined,
            ({ langsmithExtra?: Partial<RunTreeConfig> } & Record<
              string,
              unknown
            >)?,
          ];
          const sanitizedArgs = [...args];
          sanitizedArgs[2] = stripLangSmithExtraFromRequestOptions(
            sanitizedArgs[2],
          );
          while (
            sanitizedArgs.length > 1 &&
            sanitizedArgs[sanitizedArgs.length - 1] === undefined
          ) {
            sanitizedArgs.pop();
          }

          const runTree = createManagedAgentStreamRun(
            sessionID,
            params,
            requestOptions,
          );

          const sessionPromise: Promise<BetaManagedAgentsSession | undefined> =
            anthropic.beta?.sessions?.retrieve
              ? anthropic.beta.sessions.retrieve
                  .bind(anthropic.beta.sessions)(sessionID)
                  .catch(() => undefined)
              : Promise.resolve(undefined);

          const stream = await anthropic.beta?.sessions?.events?.stream.bind(
            anthropic.beta.sessions.events,
          )(...sanitizedArgs);

          const iterator: AsyncIterator<BetaManagedAgentsStreamSessionEvents> =
            stream[Symbol.asyncIterator]();

          const chunks: BetaManagedAgentsStreamSessionEvents[] = [];
          let finalized = false;

          const finalize = async (error?: string) => {
            if (finalized) return;
            finalized = true;
            const outputs = managedAgentSessionEventsAggregator(chunks);
            const inputEvents = getManagedAgentInputEvents(chunks);
            runTree.inputs = {
              ...processManagedAgentStreamInputs({
                args: [sessionID, params, sanitizedArgs[2]],
              }),
              ...(inputEvents.length > 0
                ? {
                    events: inputEvents,
                    messages: getManagedAgentChatMessages(inputEvents),
                  }
                : {}),
            };
            const finalError = error ?? getManagedAgentStreamError(chunks);
            const session = await sessionPromise;

            const modelConfig =
              typeof session?.agent?.model === "object" &&
              session.agent.model != null
                ? (session.agent.model as KVMap)
                : undefined;
            await runTree.end(outputs, finalError);
            await runTree.postRun();
            await createManagedAgentChildRuns(
              runTree,
              chunks,
              runTree.extra.metadata ?? {},
              modelConfig,
            );
          };

          stream[Symbol.asyncIterator] = () => ({
            async next() {
              try {
                const result = await iterator.next();
                if (result.done) {
                  await finalize();
                  return result;
                }
                chunks.push(result.value);
                if (
                  result.value.type === "session.status_idle" ||
                  result.value.type === "session.status_terminated" ||
                  result.value.type === "session.deleted" ||
                  result.value.type === "session.error"
                ) {
                  await finalize();
                }
                return result;
              } catch (error) {
                await finalize(String(error));
                throw error;
              }
            },
            async return(value?: unknown) {
              if (!finalized) {
                await iterator.return?.(value);
                await finalize("Cancelled");
              } else {
                await iterator.return?.(value);
              }
              return { done: true, value };
            },
            async throw(error?: unknown) {
              await finalize(String(error));
              if (iterator.throw) return iterator.throw(error);
              throw error;
            },
          });
          return stream;
        };
        Object.defineProperty(streamManagedAgentEvents, "langsmith:traceable", {
          value: { name: "ClaudeManagedAgent", run_type: "chain" },
        });
        tracedBeta.sessions.events.stream = streamManagedAgentEvents;
      }

      if (typeof anthropic.beta.sessions.events.send === "function") {
        // Do not trace `send` as a separate run. The API returns the submitted
        // user events, which makes the run output look like a duplicate of the
        // input. Instead, annotate the active stream run for the same session.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        tracedBeta.sessions.events.send = function sendManagedAgentEvents(
          ...args: any[]
        ) {
          const sanitizedArgs = [...args];
          if (
            typeof sanitizedArgs[2] === "object" &&
            sanitizedArgs[2] != null &&
            "langsmithExtra" in sanitizedArgs[2]
          ) {
            const { langsmithExtra: _langsmithExtra, ...rest } =
              sanitizedArgs[2];
            sanitizedArgs[2] = rest;
          }
          return anthropic.beta?.sessions?.events?.send.bind(
            anthropic.beta.sessions.events,
          )(...sanitizedArgs);
        };
      }
    }

    tracedAnthropicClient.beta = tracedBeta;
  }

  return tracedAnthropicClient as PatchedAnthropicClient<T>;
};
