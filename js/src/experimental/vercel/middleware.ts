/* eslint-disable import/no-extraneous-dependencies */
import { LanguageModelV2Middleware } from "@ai-sdk/provider";
import { getCurrentRunTree, traceable } from "../../traceable.js";

/**
 * AI SDK middleware that wraps an AI SDK 5 model and adds LangSmith tracing.
 */
export function LangSmithMiddleware(config?: {
  name: string;
}): LanguageModelV2Middleware {
  const { name } = config ?? {};

  return {
    wrapGenerate: async ({ doGenerate, params }) => {
      const traceableFunc = traceable(
        async (_params: Record<string, any>) => {
          return await doGenerate();
        },
        {
          name: name ?? "ai.doStream",
          run_type: "llm",
        }
      );
      return traceableFunc(params);
    },
    wrapStream: async ({ doStream, params }) => {
      const currentRunTree = getCurrentRunTree(true);
      const runTree = currentRunTree?.createChild({
        name: name ?? "ai.doStream",
        run_type: "llm",
        inputs: params,
      });

      await runTree?.postRun();
      try {
        const { stream, ...rest } = await doStream();

        const textChunks: string[] = [];
        const transformStream = new TransformStream({
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          async transform(chunk: any, controller: any) {
            try {
              // Collect text deltas
              if (chunk.type === "text-delta" && chunk.delta) {
                textChunks.push(chunk.delta);
              }
              controller.enqueue(chunk);
            } catch (error: any) {
              // Log stream processing error
              await runTree?.end(undefined, error.message ?? String(error));
              await runTree?.patchRun();
              controller.error(error);
            }
          },

          async flush() {
            try {
              // Log the final aggregated result when stream completes
              const generatedText = textChunks.join("");
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
