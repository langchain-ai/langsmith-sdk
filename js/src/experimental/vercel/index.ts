/* eslint-disable import/no-extraneous-dependencies */
import {
  LangSmithMiddleware,
  populateToolCallsForTracing,
} from "./middleware.js";
import { traceable } from "../../traceable.js";

const _wrapTools = (tools?: Record<string, unknown>) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wrappedTools: Record<string, any> = {};
  if (tools) {
    for (const [key, tool] of Object.entries(tools)) {
      wrappedTools[key] = tool;
      if (
        tool != null &&
        typeof tool === "object" &&
        "execute" in tool &&
        typeof tool.execute === "function"
      ) {
        wrappedTools[key].execute = traceable(tool.execute.bind(tool), {
          name: key,
          run_type: "tool",
        });
      }
    }
  }
  return wrappedTools;
};

/* eslint-disable @typescript-eslint/no-explicit-any */
const _getModelDisplayName = (model: string | Record<string, any>) => {
  if (typeof model === "string") {
    return model;
  }
  if (
    model.config != null &&
    typeof model.config === "object" &&
    typeof model.config.provider === "string"
  ) {
    return model.config.provider;
  }
  return model.modelId ?? "unknown";
};

/* eslint-disable @typescript-eslint/no-explicit-any */
const _getModelId = (model: string | Record<string, unknown>) => {
  if (typeof model === "string") {
    return model;
  }
  return typeof model.modelId === "string" ? model.modelId : undefined;
};

const _formatTracedInputs = (params: Record<string, any>) => {
  const { prompt, messages, model, tools, ...rest } = params;
  if (Array.isArray(prompt)) {
    return { ...rest, messages: prompt.map(populateToolCallsForTracing) };
  } else if (Array.isArray(messages)) {
    return { ...rest, messages: messages.map(populateToolCallsForTracing) };
  } else {
    return { ...rest, prompt, messages };
  }
};

/**
 * Wraps Vercel AI SDK functions with LangSmith tracing capabilities.
 *
 * @param methods - Object containing AI SDK methods to wrap
 * @param methods.wrapLanguageModel - AI SDK's wrapLanguageModel function
 * @param methods.generateText - AI SDK's generateText function
 * @param methods.streamText - AI SDK's streamText function
 * @param methods.streamObject - AI SDK's streamObject function
 * @param methods.generateObject - AI SDK's generateObject function
 *
 * @returns Object containing wrapped versions of the AI SDK functions with LangSmith tracing
 * @returns returns.generateText - Wrapped generateText function that traces calls to LangSmith
 * @returns returns.generateObject - Wrapped generateObject function that traces calls to LangSmith
 * @returns returns.streamText - Wrapped streamText function that traces calls to LangSmith
 * @returns returns.streamObject - Wrapped streamObject function that traces calls to LangSmith
 */
const wrapAISDK = <
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  WrapLanguageModelType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  GenerateTextType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  StreamTextType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  StreamObjectType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  GenerateObjectType extends (...args: any[]) => any
>({
  wrapLanguageModel,
  generateText,
  streamText,
  streamObject,
  generateObject,
}: {
  wrapLanguageModel: WrapLanguageModelType;
  generateText: GenerateTextType;
  streamText: StreamTextType;
  streamObject: StreamObjectType;
  generateObject: GenerateObjectType;
}) => {
  /**
   * Wrapped version of AI SDK's generateText with LangSmith tracing.
   *
   * This function has the same signature and behavior as the original generateText,
   * but adds automatic tracing to LangSmith for observability.
   *
   * ```ts
   * import * as ai from "ai";
   * import { wrapAISDK } from "langsmith/experimental/vercel";
   *
   * const { generateText } = wrapAISDK(ai);
   * const { text } = await generateText(...);
   * ```
   *
   * @see {@link https://sdk.vercel.ai/docs/ai-sdk-core/generating-text} Original generateText documentation
   * @param params - Same parameters as the original generateText function
   * @returns Promise resolving to the same result as generateText, with tracing applied
   */
  const wrappedGenerateText = async (
    params: Parameters<GenerateTextType>[0]
  ) => {
    const traceableFunc = traceable(
      async (
        params: Parameters<GenerateTextType>[0]
      ): Promise<ReturnType<GenerateTextType>> => {
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: params.model.modelId,
          }),
        });
        return generateText({
          ...params,
          tools: _wrapTools(params.tools),
          model: wrappedModel,
        }) as ReturnType<GenerateTextType>;
      },
      {
        name: _getModelDisplayName(params.model),
        processInputs: (inputs) => _formatTracedInputs(inputs),
        processOutputs: (outputs) => {
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return outputs;
          }
          const { steps } = outputs.outputs;
          if (Array.isArray(steps)) {
            const lastStep = steps.at(-1);
            if (lastStep == null || typeof lastStep !== "object") {
              return outputs;
            }
            const { content } = lastStep;
            return populateToolCallsForTracing({
              content,
              role: "assistant",
            });
          } else {
            return outputs;
          }
        },
      }
    ) as (
      params: Parameters<GenerateTextType>[0]
    ) => Promise<ReturnType<GenerateTextType>>;
    return traceableFunc(params);
  };

  /**
   * Wrapped version of AI SDK's generateObject with LangSmith tracing.
   *
   * This function has the same signature and behavior as the original generateObject,
   * but adds automatic tracing to LangSmith for observability.
   *
   * ```ts
   * import * as ai from "ai";
   * import { wrapAISDK } from "langsmith/experimental/vercel";
   *
   * const { generateObject } = wrapAISDK(ai);
   * const { object } = await generateObject(...);
   * ```
   *
   * @see {@link https://sdk.vercel.ai/docs/ai-sdk-core/generating-structured-data} Original generateObject documentation
   * @param params - Same parameters as the original generateObject function
   * @returns Promise resolving to the same result as generateObject, with tracing applied
   */
  const wrappedGenerateObject = async (
    params: Parameters<GenerateObjectType>[0]
  ) => {
    if (typeof params.model === "string") {
      throw new Error("Model must be a LanguageModelV2 instance");
    }
    const traceableFunc = traceable(
      async (
        params: Parameters<GenerateObjectType>[0]
      ): Promise<ReturnType<GenerateObjectType>> => {
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
          }),
        });
        return generateObject({
          ...params,
          model: wrappedModel,
        }) as ReturnType<GenerateObjectType>;
      },
      {
        name: _getModelDisplayName(params.model),
        processInputs: (inputs) => _formatTracedInputs(inputs),
        processOutputs: (outputs) => {
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return outputs;
          }
          return outputs.outputs.object ?? outputs;
        },
      }
    ) as (
      params: Parameters<GenerateObjectType>[0]
    ) => Promise<ReturnType<GenerateObjectType>>;
    return traceableFunc(params);
  };

  /**
   * Wrapped version of AI SDK's streamText with LangSmith tracing.
   *
   * Must be called with `await`, but otherwise behaves the same as the
   * original streamText and adds adds automatic tracing to LangSmith
   * for observability.
   *
   * ```ts
   * import * as ai from "ai";
   * import { wrapAISDK } from "langsmith/experimental/vercel";
   *
   * const { streamText } = wrapAISDK(ai);
   * const { textStream } = await streamText(...);
   * ```
   *
   * @see {@link https://sdk.vercel.ai/docs/ai-sdk-core/generating-text} Original streamText documentation
   * @param params - Same parameters as the original streamText function
   * @returns Promise resolving to the same result as streamText, with tracing applied
   */
  const wrappedStreamText = async (params: Parameters<StreamTextType>[0]) => {
    if (typeof params.model === "string") {
      throw new Error("Model must be a LanguageModelV2 instance");
    }
    const traceableFunc = traceable(
      async (
        params: Parameters<StreamTextType>[0]
      ): Promise<ReturnType<StreamTextType>> => {
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
          }),
        });
        return streamText({
          ...params,
          tools: _wrapTools(params.tools),
          model: wrappedModel,
        }) as ReturnType<StreamTextType>;
      },
      {
        name: _getModelDisplayName(params.model),
        processInputs: (inputs) => _formatTracedInputs(inputs),
      }
    ) as (params: Parameters<StreamTextType>[0]) => ReturnType<StreamTextType>;
    return traceableFunc(params);
  };

  /**
   * Wrapped version of AI SDK's streamObject with LangSmith tracing.
   *
   * Must be called with `await`, but otherwise behaves the same as the
   * original streamObject and adds adds automatic tracing to LangSmith
   * for observability.
   *
   * ```ts
   * import * as ai from "ai";
   * import { wrapAISDK } from "langsmith/experimental/vercel";
   *
   * const { streamObject } = wrapAISDK(ai);
   * const { partialObjectStream } = await streamObject(...);
   * ```
   *
   * @see {@link https://sdk.vercel.ai/docs/ai-sdk-core/generating-structured-data} Original streamObject documentation
   * @param params - Same parameters as the original streamObject function
   * @returns Promise resolving to the same result as streamObject, with tracing applied
   */
  const wrappedStreamObject = async (
    params: Parameters<StreamObjectType>[0]
  ) => {
    if (typeof params.model === "string") {
      throw new Error("Model must be a LanguageModelV2 instance");
    }
    const traceableFunc = traceable(
      async (
        params: Parameters<StreamObjectType>[0]
      ): Promise<ReturnType<StreamObjectType>> => {
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
          }),
        });
        return streamObject({
          ...params,
          model: wrappedModel,
        }) as ReturnType<StreamObjectType>;
      },
      {
        name: _getModelDisplayName(params.model),
        processInputs: (inputs) => _formatTracedInputs(inputs),
      }
    ) as (
      params: Parameters<StreamObjectType>[0]
    ) => ReturnType<StreamObjectType>;
    return traceableFunc(params);
  };

  return {
    generateText: wrappedGenerateText,
    generateObject: wrappedGenerateObject,
    streamText: wrappedStreamText,
    streamObject: wrappedStreamObject,
  };
};

export { wrapAISDK };
