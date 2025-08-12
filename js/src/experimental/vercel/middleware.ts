/* eslint-disable import/no-extraneous-dependencies */
import type {
  LanguageModelV2Middleware,
  LanguageModelV2StreamPart,
  LanguageModelV2CallOptions,
  LanguageModelV2Message,
} from "@ai-sdk/provider";
import type { RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, traceable } from "../../traceable.js";
import { extractInputTokenDetails } from "../../utils/vercel.js";

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
const _formatTracedInputs = (params: Record<string, any>) => {
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const setUsageMetadataOnRunTree = (
  result: Record<string, any>,
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
  runTree.extra = {
    ...runTree.extra,
    metadata: {
      ...runTree.extra?.metadata,
      usage_metadata: {
        ...langsmithUsage,
        input_token_details: {
          ...inputTokenDetails,
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
  lsConfig?: Partial<Omit<RunTreeConfig, "inputs" | "outputs">>;
}): LanguageModelV2Middleware {
  const { name, modelId, lsConfig } = config ?? {};

  return {
    wrapGenerate: async ({ doGenerate, params }) => {
      const traceableFunc = traceable(
        async (_params: Record<string, any>) => {
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
          processInputs: (inputs) =>
            _formatTracedInputs(inputs as LanguageModelV2CallOptions),
          processOutputs: (outputs) => {
            return _formatTracedOutputs(outputs);
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
                      text: aggregated.text + chunk.delta,
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
                  text: "",
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
