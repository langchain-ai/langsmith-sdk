import type Anthropic from "@anthropic-ai/sdk";
import type { Stream } from "@anthropic-ai/sdk/streaming";
import type { MessageStream } from "@anthropic-ai/sdk/lib/MessageStream";
import type { RunTreeConfig } from "../index.js";
import {
  isTraceableFunction,
  traceable,
  TraceableConfig,
} from "../traceable.js";
import { KVMap } from "../schemas.js";
import { convertAnthropicUsageToInputTokenDetails } from "../utils/usage.js";

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
  stream: (...args: any[]) => any;
};

type AnthropicType = {
  messages: MessagesNamespace;
  beta?: {
    messages?: MessagesNamespace;
  };
};

type PatchedAnthropicClient<T extends AnthropicType> = T & {
  messages: T["messages"] & {
    create: {
      (
        arg: Anthropic.MessageCreateParamsStreaming,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        }
      ): Promise<Stream<Anthropic.MessageStreamEvent>>;
    } & {
      (
        arg: Anthropic.MessageCreateParamsNonStreaming,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        }
      ): Promise<Anthropic.Message>;
    };
    stream: {
      (
        arg: Anthropic.MessageStreamParams,
        arg2?: Anthropic.RequestOptions & {
          langsmithExtra?: ExtraRunTreeConfig;
        }
      ): MessageStream;
    };
  };
};

/**
 * Create usage metadata from Anthropic's token usage format.
 */
function createUsageMetadata(
  anthropicUsage: Partial<Anthropic.Messages.Usage>
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
  const totalTokens = inputTokens + outputTokens;

  const inputTokenDetails: Record<string, number> =
    convertAnthropicUsageToInputTokenDetails(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      anthropicUsage as Record<string, any>
    );

  return {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: totalTokens,
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
  event: Anthropic.ContentBlockDeltaEvent
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
            chunk
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
              usage[key as keyof typeof usage] = value;
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
  options?: Partial<RunTreeConfig>
): PatchedAnthropicClient<T> => {
  if (
    isTraceableFunction(anthropic.messages.create) ||
    isTraceableFunction(anthropic.messages.stream)
  ) {
    throw new Error(
      "This instance of Anthropic client has been already wrapped once."
    );
  }

  const tracedAnthropicClient = { ...anthropic };

  // Common configuration for messages.create
  const messagesCreateConfig: TraceableConfig<
    typeof anthropic.messages.create
  > = {
    name: "ChatAnthropic",
    run_type: "llm",
    aggregator: messageAggregator,
    argsConfigPath: [1, "langsmithExtra"],
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
        ls_invocation_params,
      };
    },
    processOutputs: processMessageOutput,
    ...options,
  };

  // Create a new messages object preserving the prototype
  tracedAnthropicClient.messages = Object.create(
    Object.getPrototypeOf(anthropic.messages)
  );

  // Copy all own properties
  Object.assign(tracedAnthropicClient.messages, anthropic.messages);

  // Wrap messages.create
  tracedAnthropicClient.messages.create = traceable(
    anthropic.messages.create.bind(anthropic.messages),
    messagesCreateConfig
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
      getInvocationParams: messagesCreateConfig.getInvocationParams,
      processOutputs: processMessageOutput,
      ...options,
    }
  );

  // Wrap beta.messages if it exists
  if (
    anthropic.beta &&
    anthropic.beta.messages &&
    typeof anthropic.beta.messages.create === "function"
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tracedBeta = { ...anthropic.beta } as any;
    tracedBeta.messages = Object.create(
      Object.getPrototypeOf(anthropic.beta.messages)
    );
    Object.assign(tracedBeta.messages, anthropic.beta.messages);

    // Wrap beta.messages.create
    tracedBeta.messages.create = traceable(
      anthropic.beta.messages.create.bind(anthropic.beta.messages),
      messagesCreateConfig
    );

    // Wrap beta.messages.stream if it exists
    if (typeof anthropic.beta.messages.stream === "function") {
      tracedBeta.messages.stream = traceable(
        wrapStreamMethod(
          anthropic.beta.messages.stream.bind(anthropic.beta.messages)
        ),
        {
          name: "ChatAnthropic",
          run_type: "llm",
          aggregator: messageAggregator,
          argsConfigPath: [1, "langsmithExtra"],
          getInvocationParams: messagesCreateConfig.getInvocationParams,
          processOutputs: processMessageOutput,
          ...options,
        }
      );
    }

    tracedAnthropicClient.beta = tracedBeta;
  }

  return tracedAnthropicClient as PatchedAnthropicClient<T>;
};
