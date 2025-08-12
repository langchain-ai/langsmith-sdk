/* eslint-disable import/no-extraneous-dependencies */
import type {
  LanguageModelV2Middleware,
  LanguageModelV2StreamPart,
  LanguageModelV2CallOptions,
  LanguageModelV2Message,
} from "@ai-sdk/provider";
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
    formattedMessage.tool_calls = formattedMessage.content
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
  const { request, response, providerMetadata, ...rest } = outputs;
  const formattedOutputs = { ...rest };
  if (formattedOutputs.role == null) {
    formattedOutputs.role = formattedOutputs.type ?? "assistant";
  }
  return populateToolCallsForTracing(
    formattedOutputs as LanguageModelV2Message
  );
};

/**
 * AI SDK middleware that wraps an AI SDK 5 model and adds LangSmith tracing.
 */
export function LangSmithMiddleware(config?: {
  name: string;
  modelId?: string;
}): LanguageModelV2Middleware {
  const { name, modelId } = config ?? {};

  return {
    wrapGenerate: async ({ doGenerate, params }) => {
      const traceableFunc = traceable(
        async (_params: Record<string, any>) => {
          const result = await doGenerate();
          const langsmithUsage = {
            input_tokens: result.usage?.inputTokens,
            output_tokens: result.usage?.outputTokens,
            total_tokens: result.usage?.totalTokens,
          };
          const inputTokenDetails = extractInputTokenDetails(
            result.providerMetadata ?? {},
            result.usage?.cachedInputTokens
          );
          const currentRunTree = getCurrentRunTree(true);
          if (currentRunTree) {
            currentRunTree.extra = {
              ...currentRunTree.extra,
              metadata: {
                ...currentRunTree.extra?.metadata,
                usage_metadata: {
                  ...langsmithUsage,
                  input_token_details: {
                    ...inputTokenDetails,
                  },
                },
              },
            };
          }
          return result;
        },
        {
          name: name ?? "ai.doGenerate",
          run_type: "llm",
          metadata: {
            ls_model_name: modelId,
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
      const currentRunTree = getCurrentRunTree(true);
      const runTree = currentRunTree?.createChild({
        name: name ?? "ai.doStream",
        run_type: "llm",
        metadata: {
          ls_model_name: modelId,
        },
        inputs: _formatTracedInputs(params),
      });

      await runTree?.postRun();
      try {
        const { stream, ...rest } = await doStream();
        const chunks: LanguageModelV2StreamPart[] = [];
        const transformStream = new TransformStream({
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          async transform(chunk: LanguageModelV2StreamPart, controller: any) {
            chunks.push(chunk);
            controller.enqueue(chunk);
          },

          async flush() {
            try {
              // Log the final aggregated result when stream completes
              const generatedText = chunks
                .filter((chunk) => chunk.type === "text-delta")
                .map((chunk) => chunk.delta)
                .join("");
              console.log(chunks);
              const output: unknown = generatedText
                ? [{ type: "text", text: generatedText }]
                : [];
              await runTree?.end({ outputs: output });
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
