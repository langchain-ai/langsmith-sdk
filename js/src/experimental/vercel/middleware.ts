/* eslint-disable import/no-extraneous-dependencies */
import type {
  LanguageModelV2Middleware,
  LanguageModelV2StreamPart,
  LanguageModelV2CallOptions,
  LanguageModelV2Message,
  LanguageModelV2Usage,
  SharedV2ProviderMetadata,
} from "@ai-sdk/provider";
import type { RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, traceable } from "../../traceable.js";
import {
  extractInputTokenDetails,
  extractOutputTokenDetails,
} from "../../utils/vercel.js";

export const populateToolCallsForTracing = (
  message: LanguageModelV2Message
) => {
  const formattedMessage: LanguageModelV2Message & Record<string, unknown> = {
    ...message,
  };
  if (formattedMessage.role !== "assistant") {
    return formattedMessage;
  }
  if (Array.isArray(formattedMessage.content)) {
    const toolCalls = formattedMessage.content
      .filter((block) => {
        return (
          block != null &&
          typeof block === "object" &&
          block.type == "tool-call"
        );
      })
      .map((block) => {
        return {
          id: block.toolCallId,
          type: "function",
          function: {
            name: block.toolName,
            arguments:
              typeof block.input !== "string"
                ? JSON.stringify(block.input)
                : block.input,
          },
        };
      });
    if (toolCalls.length > 0) {
      formattedMessage.tool_calls = toolCalls;
    }
  }
  return formattedMessage;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _formatTracedInputs = (params: LanguageModelV2CallOptions) => {
  const { prompt, ...rest } = params;
  if (prompt == null) {
    return params;
  }
  if (Array.isArray(prompt)) {
    return { ...rest, messages: prompt.map(populateToolCallsForTracing) };
  }
  return rest;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _formatTracedOutputs = (outputs: Record<string, any>) => {
  const { request, response, ...rest } = outputs;
  const formattedOutputs = { ...rest };
  if (formattedOutputs.role == null) {
    formattedOutputs.role = formattedOutputs.type ?? "assistant";
  }
  return populateToolCallsForTracing(
    formattedOutputs as LanguageModelV2Message
  );
};

const setUsageMetadataOnRunTree = (
  result: {
    usage?: LanguageModelV2Usage | null;
    providerMetadata?: SharedV2ProviderMetadata | null;
  },
  runTree: RunTree
) => {
  if (result.usage == null || typeof result.usage !== "object") {
    return;
  }
  const langsmithUsage = {
    input_tokens: result.usage?.inputTokens,
    output_tokens: result.usage?.outputTokens,
    total_tokens: result.usage?.totalTokens,
  };
  const inputTokenDetails = extractInputTokenDetails(
    result.providerMetadata ?? {},
    result.usage?.cachedInputTokens
  );
  const outputTokenDetails = extractOutputTokenDetails(
    result.usage?.reasoningTokens
  );
  runTree.extra = {
    ...runTree.extra,
    metadata: {
      ...runTree.extra?.metadata,
      usage_metadata: {
        ...langsmithUsage,
        input_token_details: {
          ...inputTokenDetails,
        },
        output_token_details: {
          ...outputTokenDetails,
        },
      },
    },
  };
};

/**
 * AI SDK middleware that wraps an AI SDK 5 model and adds LangSmith tracing.
 */
export function LangSmithMiddleware(config?: {
  name: string;
  modelId?: string;
  lsConfig?: Partial<Omit<RunTreeConfig, "inputs" | "outputs" | "run_type">>;
}): LanguageModelV2Middleware {
  const { name, modelId, lsConfig } = config ?? {};

  return {
    wrapGenerate: async ({ doGenerate, params }) => {
      const traceableFunc = traceable(
        async (_params: typeof params) => {
          const result = await doGenerate();
          const currentRunTree = getCurrentRunTree(true);
          if (currentRunTree !== undefined) {
            setUsageMetadataOnRunTree(result, currentRunTree);
          }
          return result;
        },
        {
          ...lsConfig,
          name: name ?? "ai.doGenerate",
          run_type: "llm",
          metadata: {
            ls_model_name: modelId,
            ai_sdk_method: "ai.doGenerate",
            ...lsConfig?.metadata,
          },
          processInputs: (inputs) => {
            const typedInputs = inputs as LanguageModelV2CallOptions;
            return _formatTracedInputs(typedInputs);
          },
          processOutputs: (outputs) => {
            const typedOutputs = outputs as Awaited<
              ReturnType<typeof doGenerate>
            >;
            return _formatTracedOutputs(typedOutputs);
          },
        }
      );
      return traceableFunc(params);
    },
    wrapStream: async ({ doStream, params }) => {
      const parentRunTree = getCurrentRunTree(true);
      let runTree: RunTree | undefined;
      if (
        parentRunTree != null &&
        typeof parentRunTree === "object" &&
        typeof parentRunTree.createChild === "function"
      ) {
        runTree = parentRunTree?.createChild({
          ...lsConfig,
          name: name ?? "ai.doStream",
          run_type: "llm",
          metadata: {
            ls_model_name: modelId,
            ai_sdk_method: "ai.doStream",
            ...lsConfig?.metadata,
          },
          inputs: _formatTracedInputs(params),
        });
      }

      await runTree?.postRun();
      try {
        const { stream, ...rest } = await doStream();
        const chunks: LanguageModelV2StreamPart[] = [];
        const transformStream = new TransformStream({
          async transform(chunk: LanguageModelV2StreamPart, controller) {
            if (
              chunk.type === "tool-input-start" ||
              chunk.type === "text-start"
            ) {
              // Only necessary to log the first token event
              if (
                runTree?.events == null ||
                (Array.isArray(runTree.events) && runTree.events.length === 0)
              ) {
                runTree?.addEvent({ name: "new_token" });
              }
            } else if (chunk.type === "finish") {
              runTree?.addEvent({ name: "end" });
            }
            chunks.push(chunk);
            controller.enqueue(chunk);
          },

          async flush() {
            try {
              const output = chunks.reduce(
                (aggregated, chunk) => {
                  if (chunk.type === "text-delta") {
                    if (chunk.delta == null) {
                      return aggregated;
                    }
                    return {
                      ...aggregated,
                      content: aggregated.content + chunk.delta,
                    };
                  } else if (chunk.type === "tool-call") {
                    const matchingToolCall = aggregated.tool_calls.find(
                      (call) => call.id === chunk.toolCallId
                    );
                    if (matchingToolCall != null) {
                      return aggregated;
                    }
                    return {
                      ...aggregated,
                      tool_calls: [
                        ...aggregated.tool_calls,
                        {
                          id: chunk.toolCallId,
                          type: "function",
                          function: {
                            name: chunk.toolName,
                            arguments: chunk.input,
                          },
                        },
                      ],
                    };
                  } else if (chunk.type === "finish") {
                    if (runTree != null) {
                      setUsageMetadataOnRunTree(chunk, runTree);
                    }
                    return {
                      ...aggregated,
                      providerMetadata: chunk.providerMetadata,
                      finishReason: chunk.finishReason,
                    };
                  } else {
                    return aggregated;
                  }
                },
                {
                  content: "",
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  tool_calls: [] as Record<string, any>[],
                }
              );
              await runTree?.end(_formatTracedOutputs(output));
            } catch (error: any) {
              await runTree?.end(undefined, error.message ?? String(error));
              throw error;
            } finally {
              await runTree?.patchRun();
            }
          },
        });

        return {
          stream: stream.pipeThrough(transformStream),
          ...rest,
        };
      } catch (error: any) {
        await runTree?.end(undefined, error.message ?? String(error));
        await runTree?.patchRun();
        throw error;
      }
    },
  };
}
