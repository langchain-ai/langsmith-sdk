/* eslint-disable import/no-extraneous-dependencies */
import type {
  LanguageModelV2Middleware,
  LanguageModelV2StreamPart,
  LanguageModelV2CallOptions,
  LanguageModelV2Message,
  LanguageModelV2Usage,
  SharedV2ProviderMetadata,
  LanguageModelV2FinishReason,
} from "@ai-sdk/provider";
import type { RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, traceable } from "../../traceable.js";
import {
  extractInputTokenDetails,
  extractOutputTokenDetails,
} from "../../utils/vercel.js";
import { convertMessageToTracedFormat } from "./utils.js";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _formatTracedInputs = (params: LanguageModelV2CallOptions) => {
  const { prompt, ...rest } = params;
  if (prompt == null) {
    return params;
  }
  if (Array.isArray(prompt)) {
    return {
      ...rest,
      messages: prompt.map((message) => convertMessageToTracedFormat(message)),
    };
  }
  return rest;
};

const _formatTracedOutputs = (
  outputs: Record<string, unknown>,
  includeHttpDetails = false
) => {
  let formattedOutputs: Record<string, unknown>;

  if (includeHttpDetails) {
    // Include all fields including raw request/response/usage
    formattedOutputs = { ...outputs };
  } else {
    // Extract only the fields we want to trace, excluding raw request/response/usage
    const { request: _, response: __, ...messageFields } = outputs;
    formattedOutputs = { ...messageFields };
  }

  if (formattedOutputs.role == null) {
    formattedOutputs.role = formattedOutputs.type ?? "assistant";
  }
  return convertMessageToTracedFormat(
    formattedOutputs as LanguageModelV2Message
  );
};

const setUsageMetadataOnRunTree = (
  result: {
    usage?: LanguageModelV2Usage;
    providerMetadata?: SharedV2ProviderMetadata;
  },
  runTree: RunTree
) => {
  if (result.usage == null || typeof result.usage !== "object") {
    return;
  }
  // Shim for AI SDK 4
  const inputTokens =
    result.usage?.inputTokens ??
    (result.usage as Record<string, number | undefined>)?.promptTokens;
  const outputTokens =
    result.usage?.outputTokens ??
    (result.usage as Record<string, number | undefined>)?.completionTokens;
  let totalTokens = result.usage?.totalTokens;
  if (
    typeof totalTokens !== "number" &&
    typeof inputTokens === "number" &&
    typeof outputTokens === "number"
  ) {
    totalTokens = inputTokens + outputTokens;
  }
  const langsmithUsage = {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: totalTokens,
  };
  const inputTokenDetails = extractInputTokenDetails(
    result.usage,
    result.providerMetadata
  );
  const outputTokenDetails = extractOutputTokenDetails(
    result.usage,
    result.providerMetadata
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

export type AggregatedDoStreamOutput = {
  content: string;
  role: "assistant";
  tool_calls: {
    id: string;
    type: "function";
    function: {
      name: string;
      arguments: string;
    };
  }[];
  providerMetadata?: SharedV2ProviderMetadata;
  finishReason?: LanguageModelV2FinishReason;
};

/**
 * AI SDK middleware that wraps an AI SDK 5 model and adds LangSmith tracing.
 */
export function LangSmithMiddleware(config?: {
  name: string;
  modelId?: string;
  lsConfig?: Partial<Omit<RunTreeConfig, "inputs" | "outputs" | "run_type">> & {
    processInputs?: (
      inputs: Record<string, unknown>
    ) => Record<string, unknown>;
    processOutputs?: (
      outputs: Record<string, unknown>
    ) => Record<string, unknown> | Promise<Record<string, unknown>>;
    traceRawHttp?: boolean;
  };
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
            const inputFormatter =
              lsConfig?.processInputs ?? _formatTracedInputs;
            return inputFormatter(typedInputs);
          },
          processOutputs: (outputs) => {
            const typedOutputs = outputs as Awaited<
              ReturnType<typeof doGenerate>
            >;
            if (lsConfig?.processOutputs) {
              return lsConfig.processOutputs(typedOutputs);
            }
            return _formatTracedOutputs(typedOutputs, lsConfig?.traceRawHttp);
          },
        }
      );
      const res = await traceableFunc(params);
      return res;
    },
    wrapStream: async ({ doStream, params }) => {
      const parentRunTree = getCurrentRunTree(true);
      let runTree: RunTree | undefined;
      if (
        parentRunTree != null &&
        typeof parentRunTree === "object" &&
        typeof parentRunTree.createChild === "function"
      ) {
        const inputFormatter = lsConfig?.processInputs ?? _formatTracedInputs;
        const formattedInputs = inputFormatter(params);
        runTree = parentRunTree?.createChild({
          ...lsConfig,
          name: name ?? "ai.doStream",
          run_type: "llm",
          metadata: {
            ls_model_name: modelId,
            ai_sdk_method: "ai.doStream",
            ...lsConfig?.metadata,
          },
          inputs: formattedInputs,
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
                (aggregated: AggregatedDoStreamOutput, chunk) => {
                  if (chunk.type === "text-delta") {
                    if (chunk.delta != null) {
                      return {
                        ...aggregated,
                        content: aggregated.content + chunk.delta,
                      };
                    } else if (
                      "textDelta" in chunk &&
                      chunk.textDelta != null
                    ) {
                      // AI SDK 4 shim
                      return {
                        ...aggregated,
                        content: aggregated.content + chunk.textDelta,
                      };
                    } else {
                      return aggregated;
                    }
                  } else if (chunk.type === "tool-call") {
                    const matchingToolCall = aggregated.tool_calls.find(
                      (call) => call.id === chunk.toolCallId
                    );
                    if (matchingToolCall != null) {
                      return aggregated;
                    }
                    let chunkArgs = chunk.input;
                    if (
                      chunkArgs == null &&
                      "args" in chunk &&
                      typeof chunk.args === "string"
                    ) {
                      chunkArgs = chunk.args;
                    }
                    return {
                      ...aggregated,
                      tool_calls: [
                        ...aggregated.tool_calls,
                        {
                          id: chunk.toolCallId,
                          type: "function" as const,
                          function: {
                            name: chunk.toolName,
                            arguments: chunkArgs,
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
                  role: "assistant",
                  tool_calls: [],
                }
              );
              const outputFormatter =
                lsConfig?.processOutputs ?? convertMessageToTracedFormat;
              const formattedOutputs = await outputFormatter(output);
              await runTree?.end(formattedOutputs);
            } catch (error: any) {
              await runTree?.end(undefined, error.message ?? String(error));
              throw error;
            } finally {
              await runTree?.patchRun({
                excludeInputs: true,
              });
            }
          },
        });

        return {
          stream: stream.pipeThrough(transformStream),
          ...rest,
        };
      } catch (error: any) {
        await runTree?.end(undefined, error.message ?? String(error));
        await runTree?.patchRun({
          excludeInputs: true,
        });
        throw error;
      }
    },
  };
}
