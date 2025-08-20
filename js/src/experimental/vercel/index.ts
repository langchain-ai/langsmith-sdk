import { LangSmithMiddleware } from "./middleware.js";
import { convertMessageToTracedFormat, RETURN_FORMATTED } from "./utils.js";
import { isTraceableFunction, traceable } from "../../traceable.js";
import { RunTreeConfig } from "../../run_trees.js";

const _wrapTools = (
  tools?: Record<string, unknown>,
  lsConfig?: Partial<RunTreeConfig>
) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wrappedTools: Record<string, any> = {};
  if (tools) {
    for (const [key, tool] of Object.entries(tools)) {
      wrappedTools[key] = { ...(tool as Record<string, unknown>) };
      if (
        wrappedTools[key] != null &&
        typeof wrappedTools[key] === "object" &&
        "execute" in wrappedTools[key] &&
        typeof wrappedTools[key].execute === "function" &&
        !isTraceableFunction(wrappedTools[key].execute)
      ) {
        wrappedTools[key].execute = traceable(
          wrappedTools[key].execute.bind(wrappedTools[key]),
          {
            ...lsConfig,
            name: key,
            run_type: "tool",
          }
        );
      }
    }
  }
  return wrappedTools;
};

const _getModelDisplayName = (
  model: string | Record<string, unknown>
): string => {
  if (typeof model === "string") {
    return model;
  }

  if (
    model.config != null &&
    typeof model.config === "object" &&
    "provider" in model.config &&
    typeof model.config.provider === "string"
  ) {
    return model.config.provider;
  }

  if (model.modelId != null && typeof model.modelId === "string") {
    return model.modelId;
  }

  return "unknown";
};

const _getModelId = (model: string | Record<string, unknown>) => {
  if (typeof model === "string") {
    return model;
  }
  return typeof model.modelId === "string" ? model.modelId : undefined;
};

const _formatTracedInputs = (params: Record<string, unknown>) => {
  const { prompt, messages, model, tools, ...rest } = params;
  if (Array.isArray(prompt)) {
    return { ...rest, messages: prompt.map(convertMessageToTracedFormat) };
  } else if (Array.isArray(messages)) {
    return { ...rest, messages: messages.map(convertMessageToTracedFormat) };
  } else {
    return { ...rest, prompt, messages };
  }
};

const _mergeConfig = (
  baseConfig?: Partial<RunTreeConfig>,
  runtimeConfig?: Partial<RunTreeConfig>
): Record<string, any> => {
  return {
    ...baseConfig,
    ...runtimeConfig,
    metadata: {
      ...baseConfig?.metadata,
      ...runtimeConfig?.metadata,
    },
  };
};

export type WrapAISDKConfig = Partial<
  Omit<
    RunTreeConfig,
    | "inputs"
    | "outputs"
    | "run_type"
    | "child_runs"
    | "parent_run"
    | "error"
    | "serialized"
  >
> & {
  processInputs?: (inputs: {
    formatted: Record<string, unknown>;
    raw: Record<string, unknown>;
  }) => Record<string, unknown>;
  processOutputs?: (outputs: {
    formatted: Record<string, unknown>;
    raw: Record<string, unknown>;
  }) => Record<string, unknown>;
  childLLMRunProcessInputs?: (inputs: {
    formatted: Record<string, unknown>;
    raw: Record<string, unknown>;
  }) => Record<string, unknown>;
  childLLMRunProcessOutputs?: (outputs: {
    formatted: Record<string, unknown>;
    raw: Record<string, unknown>;
  }) => Record<string, unknown>;
};

const _extractChildRunConfig = (lsConfig?: WrapAISDKConfig) => {
  const {
    id,
    name,
    parent_run_id,
    start_time,
    end_time,
    attachments,
    dotted_order,
    processInputs,
    processOutputs,
    childLLMRunProcessInputs,
    childLLMRunProcessOutputs,
    ...inheritedConfig
  } = lsConfig ?? {};
  const childConfig: WrapAISDKConfig = inheritedConfig;
  if (childLLMRunProcessInputs) {
    childConfig.processInputs = childLLMRunProcessInputs;
  }
  if (childLLMRunProcessOutputs) {
    childConfig.processOutputs = childLLMRunProcessOutputs;
  }
  return childConfig;
};

const _resolveConfigs = (
  baseLsConfig?: WrapAISDKConfig,
  runtimeLsConfig?: WrapAISDKConfig
) => {
  const baseChildRunConfig = _extractChildRunConfig(baseLsConfig);
  const runtimeChildLLMRunConfig = _extractChildRunConfig(runtimeLsConfig);
  const resolvedLsConfig = _mergeConfig(baseLsConfig, runtimeLsConfig);
  const resolvedChildLLMRunConfig = _mergeConfig(
    baseChildRunConfig,
    runtimeChildLLMRunConfig
  );
  const {
    processInputs: _processInputs,
    processOutputs: _processOutputs,
    ...resolvedToolConfig
  } = resolvedChildLLMRunConfig;

  return {
    resolvedLsConfig,
    resolvedChildLLMRunConfig,
    resolvedToolConfig,
  };
};

/**
 * Wraps Vercel AI SDK 5 functions with LangSmith tracing capabilities.
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
  GenerateTextType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  StreamTextType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  GenerateObjectType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  StreamObjectType extends (...args: any[]) => any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  WrapLanguageModelType extends (...args: any[]) => any
>(
  {
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
  },
  baseLsConfig?: WrapAISDKConfig
) => {
  /**
   * Wrapped version of AI SDK 5's generateText with LangSmith tracing.
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
  const wrappedGenerateText = async (...args: Parameters<GenerateTextType>) => {
    const params = args[0];
    const runtimeLsConfig = params.providerMetadata?.langsmith;
    const { resolvedLsConfig, resolvedChildLLMRunConfig, resolvedToolConfig } =
      _resolveConfigs(baseLsConfig, runtimeLsConfig);
    const traceableFunc = traceable(
      async (
        ...args: Parameters<GenerateTextType>
      ): Promise<ReturnType<GenerateTextType>> => {
        const [params, ...rest] = args;
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            lsConfig: resolvedChildLLMRunConfig,
          }),
        });
        return generateText(
          {
            ...params,
            tools: _wrapTools(params.tools, resolvedToolConfig),
            model: wrappedModel,
          },
          ...rest
        ) as ReturnType<GenerateTextType>;
      },
      {
        name: _getModelDisplayName(params.model),
        ...resolvedLsConfig,
        metadata: {
          ai_sdk_method: "ai.generateText",
          ...resolvedLsConfig?.metadata,
        },
        processInputs: (inputs) => {
          const formatInputs =
            resolvedLsConfig?.processInputs?.(inputs) ?? RETURN_FORMATTED;
          return formatInputs({
            formatted: _formatTracedInputs(inputs),
            raw: inputs,
          });
        },
        processOutputs: (outputs) => {
          const formatOutputs =
            resolvedLsConfig?.processOutputs?.(outputs) ?? RETURN_FORMATTED;
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          const { steps } = outputs.outputs;
          if (Array.isArray(steps)) {
            const lastStep = steps.at(-1);
            if (lastStep == null || typeof lastStep !== "object") {
              return formatOutputs({ formatted: outputs, raw: outputs });
            }
            const { content } = lastStep;
            return formatOutputs({
              formatted: convertMessageToTracedFormat({
                content,
                role: "assistant",
              }),
              raw: outputs,
            });
          } else {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
        },
      }
    ) as (
      ...args: Parameters<GenerateTextType>
    ) => Promise<ReturnType<GenerateTextType>>;
    return traceableFunc(...args);
  };

  /**
   * Wrapped version of AI SDK 5's generateObject with LangSmith tracing.
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
    ...args: Parameters<GenerateObjectType>
  ) => {
    const params = args[0];
    const runtimeLsConfig = params.providerMetadata?.langsmith;
    const { resolvedLsConfig, resolvedChildLLMRunConfig } = _resolveConfigs(
      baseLsConfig,
      runtimeLsConfig
    );
    const traceableFunc = traceable(
      async (
        ...args: Parameters<GenerateObjectType>
      ): Promise<ReturnType<GenerateObjectType>> => {
        const [params, ...rest] = args;
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            lsConfig: resolvedChildLLMRunConfig,
          }),
        });
        return generateObject(
          {
            ...params,
            model: wrappedModel,
          },
          ...rest
        ) as ReturnType<GenerateObjectType>;
      },
      {
        name: _getModelDisplayName(params.model),
        ...resolvedLsConfig,
        metadata: {
          ai_sdk_method: "ai.generateObject",
          ...resolvedLsConfig?.metadata,
        },
        processInputs: (inputs) => {
          const formatInputs =
            resolvedLsConfig?.processInputs?.(inputs) ?? RETURN_FORMATTED;
          return formatInputs({
            formatted: _formatTracedInputs(inputs),
            raw: inputs,
          });
        },
        processOutputs: (outputs) => {
          const formatOutputs =
            resolvedLsConfig?.processOutputs?.(outputs) ?? RETURN_FORMATTED;
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          return formatOutputs({
            formatted: outputs.outputs.object ?? outputs,
            raw: outputs,
          });
        },
      }
    ) as (
      ...args: Parameters<GenerateObjectType>
    ) => Promise<ReturnType<GenerateObjectType>>;
    return traceableFunc(...args);
  };

  /**
   * Wrapped version of AI SDK 5's streamText with LangSmith tracing.
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
  const wrappedStreamText = (...args: Parameters<StreamTextType>) => {
    const params = args[0];
    const runtimeLsConfig = params.providerMetadata?.langsmith;
    const { resolvedLsConfig, resolvedChildLLMRunConfig, resolvedToolConfig } =
      _resolveConfigs(baseLsConfig, runtimeLsConfig);
    const traceableFunc = traceable(
      (...args: Parameters<StreamTextType>): ReturnType<StreamTextType> => {
        const [params, ...rest] = args;
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            lsConfig: resolvedChildLLMRunConfig,
          }),
        });
        return streamText(
          {
            ...params,
            tools: _wrapTools(params.tools, resolvedToolConfig),
            model: wrappedModel,
          },
          ...rest
        ) as ReturnType<StreamTextType>;
      },
      {
        name: _getModelDisplayName(params.model),
        ...resolvedLsConfig,
        metadata: {
          ai_sdk_method: "ai.streamText",
          ...resolvedLsConfig?.metadata,
        },
        processInputs: (inputs) => {
          const formatInputs =
            resolvedLsConfig?.processInputs?.(inputs) ?? RETURN_FORMATTED;
          return formatInputs({
            formatted: _formatTracedInputs(inputs),
            raw: inputs,
          });
        },
        processOutputs: async (outputs) => {
          const formatOutputs =
            resolvedLsConfig?.processOutputs?.(outputs) ?? RETURN_FORMATTED;
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          const content = await outputs.outputs.content;
          if (content == null || typeof content !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          return formatOutputs({
            formatted: convertMessageToTracedFormat({
              content,
              role: "assistant",
            }),
            raw: outputs,
          });
        },
      }
    ) as (...args: Parameters<StreamTextType>) => ReturnType<StreamTextType>;
    return traceableFunc(...args);
  };

  /**
   * Wrapped version of AI SDK 5's streamObject with LangSmith tracing.
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
  const wrappedStreamObject = (...args: Parameters<StreamObjectType>) => {
    const params = args[0];
    const runtimeLsConfig = params.providerMetadata?.langsmith;
    const { resolvedLsConfig, resolvedChildLLMRunConfig } = _resolveConfigs(
      baseLsConfig,
      runtimeLsConfig
    );
    const traceableFunc = traceable(
      (...args: Parameters<StreamObjectType>): ReturnType<StreamObjectType> => {
        const [params, ...rest] = args;
        const wrappedModel = wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            lsConfig: resolvedChildLLMRunConfig,
          }),
        });
        return streamObject(
          {
            ...params,
            model: wrappedModel,
          },
          ...rest
        ) as ReturnType<StreamObjectType>;
      },
      {
        name: _getModelDisplayName(params.model),
        ...resolvedLsConfig,
        metadata: {
          ai_sdk_method: "ai.streamObject",
          ...resolvedLsConfig?.metadata,
        },
        processInputs: (inputs) => {
          const formatInputs =
            resolvedLsConfig?.processInputs?.(inputs) ?? RETURN_FORMATTED;
          return formatInputs({
            formatted: _formatTracedInputs(inputs),
            raw: inputs,
          });
        },
        processOutputs: async (outputs) => {
          const formatOutputs =
            resolvedLsConfig?.processOutputs?.(outputs) ?? RETURN_FORMATTED;
          if (outputs.outputs == null || typeof outputs.outputs !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          const object = await outputs.outputs.object;
          if (object == null || typeof object !== "object") {
            return formatOutputs({ formatted: outputs, raw: outputs });
          }
          return formatOutputs({ formatted: object, raw: outputs });
        },
      }
    ) as (
      ...args: Parameters<StreamObjectType>
    ) => ReturnType<StreamObjectType>;
    return traceableFunc(...args);
  };

  return {
    generateText: wrappedGenerateText as GenerateTextType,
    generateObject: wrappedGenerateObject as GenerateObjectType,
    streamText: wrappedStreamText as StreamTextType,
    streamObject: wrappedStreamObject as StreamObjectType,
  };
};

export { wrapAISDK };
