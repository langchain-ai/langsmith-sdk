import { createRequire } from "module";
import type { JSONValue } from "ai";

function _getPackageVersion(packageName: string): string | undefined {
  try {
    const req = createRequire(process.cwd() + "/package.json");
    return (req(`${packageName}/package.json`) as { version?: string }).version;
  } catch {
    return undefined;
  }
}
import type {
  LanguageModelV2,
  LanguageModelV2CallOptions,
} from "@ai-sdk/provider";

import {
  type AggregatedDoStreamOutput,
  LangSmithMiddleware,
} from "./middleware.js";
import { convertMessageToTracedFormat } from "./utils.js";
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
      wrappedTools[key] = Object.assign(
        Object.create(Object.getPrototypeOf(tool)),
        tool
      );
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

const _formatTracedInputs = async (params: Record<string, unknown>) => {
  const { prompt, messages, model, tools, output, ...rest } = params;
  let processedInputs: Record<string, unknown> = {};
  if (Array.isArray(prompt)) {
    processedInputs = {
      ...rest,
      messages: prompt.map((message) => convertMessageToTracedFormat(message)),
    };
  } else if (Array.isArray(messages)) {
    processedInputs = {
      ...rest,
      messages: messages.map((message) =>
        convertMessageToTracedFormat(message)
      ),
    };
  } else {
    processedInputs = { ...rest, prompt, messages };
  }
  try {
    if (
      output != null &&
      typeof output === "object" &&
      "responseFormat" in output
    ) {
      const responseFormat = await output.responseFormat;
      processedInputs.output = responseFormat;
    } else {
      processedInputs.output = output;
    }
  } catch {
    // Could not extract response format from output for tracing
    processedInputs.output = output;
  }
  return processedInputs;
};

const _mergeConfig = (
  baseConfig?: Partial<RunTreeConfig>,
  runtimeConfig?: Partial<RunTreeConfig>
): Record<string, unknown> => {
  return {
    ...baseConfig,
    ...runtimeConfig,
    metadata: {
      ...baseConfig?.metadata,
      ...runtimeConfig?.metadata,
    },
  };
};

export type { AggregatedDoStreamOutput };

export type WrapAISDKConfig<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  T extends (...args: any[]) => any = (...args: any[]) => any
> = Partial<
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
  /**
   * Apply transformations to AI SDK inputs before logging.
   * This function should NOT mutate the inputs.
   * Receives both "raw" and LangSmith-suggested "formatted" inputs,
   * and should combine them into a single LangSmith-formatted input.
   *
   * ```ts
   * import {
   *   wrapAISDK,
   *   createLangSmithProviderOptions,
   * } from "langsmith/experimental/vercel";
   * import * as ai from "ai";
   * import { openai } from "@ai-sdk/openai";
   *
   * const { generateText } = wrapAISDK(ai);
   *
   * const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
   *   processInputs: (inputs) => {
   *     const { messages } = inputs;
   *     return {
   *       messages: messages?.map((message) => ({
   *         providerMetadata: message.providerOptions,
   *         role: "assistant",
   *         content: "REDACTED",
   *       })),
   *       prompt: "REDACTED",
   *     };
   *   },
   * });
   * const { text } = await generateText({
   *   model: openai("gpt-5-nano"),
   *   prompt: "What is the capital of France?",
   *   providerOptions: {
   *     langsmith: lsConfig,
   *   },
   * });
   * ```
   *
   * This function is not inherited by nested LLM runs or tool calls.
   * Pass `processChildLLMRunInputs` to override child LLM run
   * input processing or wrap your tool's `execute` method in a
   * separate `traceable` for tool calls.
   *
   * @param inputs Key-value map of the function inputs.
   * @param inputs.formatted - Inputs formatted for LangSmith.
   * @param inputs.raw - Raw inputs from the AI SDK.
   * @returns A single combined key-value map of processed inputs.
   */
  processInputs?: (inputs: Parameters<T>[0]) => Record<string, unknown>;
  /**
   * Apply transformations to AI SDK outputs before logging.
   * This function should NOT mutate the outputs.
   * Receives both "raw" and LangSmith-suggested "formatted" outputs,
   * and should combine them into a single LangSmith-formatted output.
   *
   * ```ts
   * import {
   *   wrapAISDK,
   *   createLangSmithProviderOptions,
   * } from "langsmith/experimental/vercel";
   * import * as ai from "ai";
   * import { openai } from "@ai-sdk/openai";
   *
   * const { generateText } = wrapAISDK(ai);
   *
   * const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
   *   processOutputs: (outputs) => {
   *     return {
   *       providerMetadata: outputs.providerMetadata,
   *       role: "assistant",
   *       content: "REDACTED",
   *     };
   *   },
   * });
   * const { text } = await generateText({
   *   model: openai("gpt-5-nano"),
   *   prompt: "What is the capital of France?",
   *   providerOptions: {
   *     langsmith: lsConfig,
   *   },
   * });
   * ```
   *
   * This function is not inherited by nested LLM runs or tool calls.
   * Pass `processChildLLMRunOutputs` to override child LLM run
   * output processing or wrap your tool's `execute` method in a
   * separate `traceable` for tool calls.
   *
   * @param outputs Key-value map of the function inputs.
   * @param outputs.formatted - Outputs formatted for LangSmith.
   * @param outputs.raw - Raw outputs from the AI SDK.
   * @returns A single combined key-value map of processed outputs.
   */
  processOutputs?: (
    // TODO: Unnest this typing on minor bump
    outputs: { outputs: Awaited<ReturnType<T>> }
  ) => Record<string, unknown> | Promise<Record<string, unknown>>;
  /**
   * Apply transformations to AI SDK child LLM run inputs before logging.
   * This function should NOT mutate the inputs.
   * Receives both "raw" and LangSmith-suggested "formatted" inputs,
   * and should combine them into a single LangSmith-formatted input.
   *
   * ```ts
   * import {
   *   wrapAISDK,
   *   createLangSmithProviderOptions,
   * } from "langsmith/experimental/vercel";
   * import * as ai from "ai";
   * import { openai } from "@ai-sdk/openai";
   *
   * const { generateText } = wrapAISDK(ai);
   *
   * const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
   *   processChildLLMRunInputs: (inputs) => {
   *     const { prompt } = inputs;
   *     return {
   *       messages: prompt.map((message) => ({
   *         ...message,
   *         content: "REDACTED CHILD INPUTS",
   *       })),
   *     };
   *   },
   * });
   * const { text } = await generateText({
   *   model: openai("gpt-5-nano"),
   *   prompt: "What is the capital of France?",
   *   providerOptions: {
   *     langsmith: lsConfig,
   *   },
   * });
   * ```
   *
   * @param inputs Key-value map of the function inputs.
   * @param inputs.formatted - Inputs formatted for LangSmith.
   * @param inputs.raw - Raw inputs from the AI SDK.
   * @returns A single combined key-value map of processed inputs.
   */
  processChildLLMRunInputs?: (
    inputs: LanguageModelV2CallOptions
  ) => Record<string, unknown>;
  /**
   * Apply transformations to AI SDK child LLM run outputs before logging.
   * This function should NOT mutate the outputs.
   * Receives both "raw" and LangSmith-suggested "formatted" outputs,
   * and should combine them into a single LangSmith-formatted output.
   *
   * ```ts
   * import {
   *   wrapAISDK,
   *   createLangSmithProviderOptions,
   * } from "langsmith/experimental/vercel";
   * import * as ai from "ai";
   * import { openai } from "@ai-sdk/openai";
   *
   * const { generateText } = wrapAISDK(ai);
   *
   * const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
   *   processChildLLMRunOutputs: (outputs) => {
   *     return {
   *       providerMetadata: outputs.providerMetadata,
   *       content: "REDACTED CHILD OUTPUTS",
   *       role: "assistant",
   *     };
   *   },
   * });
   * const { text } = await generateText({
   *   model: openai("gpt-5-nano"),
   *   prompt: "What is the capital of France?",
   *   providerOptions: {
   *     langsmith: lsConfig,
   *   },
   * });
   * ```
   *
   * @param outputs Key-value map of the function inputs.
   * @param outputs.formatted - Outputs formatted for LangSmith.
   * @param outputs.raw - Raw outputs from the AI SDK.
   * @returns A single combined key-value map of processed outputs.
   */
  processChildLLMRunOutputs?: (
    outputs: "fullStream" extends keyof Awaited<ReturnType<T>>
      ? AggregatedDoStreamOutput
      : Awaited<ReturnType<LanguageModelV2["doGenerate"]>>
  ) => Record<string, unknown>;

  /**
   * Whether to include additional fields such as intermediate steps in traced
   * output messages.
   * @default false
   */
  traceResponseMetadata?: boolean;

  /**
   * Whether to include raw HTTP request and response details in traces from the
   * underlying model calls (doGenerate/doStream).
   *
   * When enabled, traces will include the full HTTP request body, response body,
   * headers, and other low-level details. This can be useful for debugging provider
   * issues but creates very verbose traces.
   *
   * @default false
   */
  traceRawHttp?: boolean;
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
    processChildLLMRunInputs,
    processChildLLMRunOutputs,
    ...inheritedConfig
  } = lsConfig ?? {};
  const childConfig: WrapAISDKConfig = inheritedConfig;
  if (processChildLLMRunInputs) {
    childConfig.processInputs = processChildLLMRunInputs;
  }
  if (processChildLLMRunOutputs) {
    // TODO: Fix this typing on minor bump
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    childConfig.processOutputs = processChildLLMRunOutputs as any;
  }
  return childConfig;
};

const _resolveConfigs = (
  baseLsConfig?: WrapAISDKConfig,
  runtimeLsConfig?: WrapAISDKConfig
): {
  resolvedLsConfig: WrapAISDKConfig;
  resolvedChildLLMRunConfig: WrapAISDKConfig;
  resolvedToolConfig: WrapAISDKConfig;
} => {
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

const _getGenerateTextWrapperConfig = ({
  model,
  runName,
  aiSdkMethodName,
  resolvedLsConfig,
  hasExplicitOutput,
  hasExplicitExperimentalOutput,
  traceResponseMetadata,
}: {
  model: any;
  runName?: string;
  aiSdkMethodName?: string;
  resolvedLsConfig: WrapAISDKConfig;
  hasExplicitOutput: boolean;
  hasExplicitExperimentalOutput?: boolean;
  traceResponseMetadata?: boolean;
}) => {
  return {
    name: runName ?? _getModelDisplayName(model),
    ...resolvedLsConfig,
    metadata: {
      ai_sdk_method: aiSdkMethodName ?? "ai.generateText",
      ...resolvedLsConfig?.metadata,
    },
    processInputs: async (inputs: any) => {
      const inputFormatter =
        resolvedLsConfig?.processInputs ?? _formatTracedInputs;
      return inputFormatter(inputs);
    },
    processOutputs: async (outputs: any) => {
      if (resolvedLsConfig?.processOutputs) {
        const processedOutputs = await resolvedLsConfig.processOutputs(
          // TODO: Fix this typing on minor bump
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          outputs as any
        );
        return processedOutputs;
      }
      if (outputs.outputs == null || typeof outputs.outputs !== "object") {
        return outputs;
      }
      // If output or experimental_output (legacy) was explicitly provided, return it directly at top level (like generateObject)
      // Note: In AI SDK 6, experimental_output/output is always available as a getter, so we need to check if it was explicitly provided
      if (hasExplicitOutput) {
        try {
          // Try new 'output' property first, then fall back to 'experimental_output' for backwards compatibility
          if ("output" in outputs.outputs) {
            const output = outputs.outputs.output;
            if (output != null && typeof output === "object") {
              if (Array.isArray(output)) {
                return { outputs: output };
              }
              return output;
            }
          }
        } catch {
          // output not accessible, continue with normal processing
        }
      } else if (hasExplicitExperimentalOutput) {
        try {
          if ("experimental_output" in outputs.outputs) {
            const experimentalOutput = outputs.outputs.experimental_output;
            if (experimentalOutput != null) {
              return experimentalOutput;
            }
          }
        } catch {
          // experimental_output not accessible, continue with normal processing
        }
      }
      const { steps } = outputs.outputs;
      if (Array.isArray(steps)) {
        const lastStep = steps.at(-1);
        if (lastStep == null || typeof lastStep !== "object") {
          return outputs;
        }
        const { content } = lastStep;
        return convertMessageToTracedFormat(
          {
            content: content ?? outputs.outputs.text,
            role: "assistant",
          },
          resolvedLsConfig?.traceResponseMetadata ?? traceResponseMetadata
            ? { steps }
            : undefined
        );
      } else {
        return outputs;
      }
    },
  };
};

const _getStreamTextWrapperConfig = ({
  model,
  runName,
  aiSdkMethodName,
  resolvedLsConfig,
  hasExplicitOutput,
  hasExplicitExperimentalOutput,
  traceResponseMetadata,
}: {
  model: any;
  runName?: string;
  aiSdkMethodName?: string;
  resolvedLsConfig: WrapAISDKConfig;
  hasExplicitOutput: boolean;
  hasExplicitExperimentalOutput?: boolean;
  traceResponseMetadata?: boolean;
}) => {
  return {
    name: runName ?? _getModelDisplayName(model),
    ...resolvedLsConfig,
    metadata: {
      ai_sdk_method: aiSdkMethodName ?? "ai.streamText",
      ...resolvedLsConfig?.metadata,
    },
    processInputs: async (inputs: any) => {
      const inputFormatter =
        resolvedLsConfig?.processInputs ?? _formatTracedInputs;
      return inputFormatter(inputs);
    },
    processOutputs: async (outputs: any) => {
      try {
        if (resolvedLsConfig?.processOutputs) {
          const processedOutputs = await resolvedLsConfig.processOutputs(
            // TODO: Fix this typing on minor bump
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            outputs as any
          );
          return processedOutputs;
        }
        if (outputs.outputs == null || typeof outputs.outputs !== "object") {
          return outputs;
        }
        // Important: Even accessing this property creates a promise.
        // This must be awaited.
        let content = await outputs.outputs.content;
        if (content == null) {
          // AI SDK 4 shim
          content = await outputs.outputs.text;
        }
        if (content == null || !["object", "string"].includes(typeof content)) {
          return outputs;
        }
        try {
          if (hasExplicitOutput || hasExplicitExperimentalOutput) {
            const textContent = await outputs.outputs.text;
            return JSON.parse(textContent);
          }
        } catch {
          // experimental_partialOutputStream not specified, continue with normal processing
        }
        let responseMetadata: Record<string, unknown> | undefined = undefined;
        if (resolvedLsConfig?.traceResponseMetadata ?? traceResponseMetadata) {
          try {
            const steps = await outputs.outputs.steps;
            responseMetadata = { steps };
          } catch {
            // Do nothing if step parsing fails
          }
        }
        return convertMessageToTracedFormat(
          {
            content,
            role: "assistant",
          },
          responseMetadata
        );
      } catch {
        // Handle parsing failures without a log
        return outputs;
      }
    },
  };
};

/**
 * Wraps LangSmith config in a way that matches AI SDK provider types.
 *
 * ```ts
 * import { createLangSmithProviderOptions } from "langsmith/experimental/vercel";
 * import * as ai from "ai";
 *
 * const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
 *   // Will have appropriate typing
 *   processInputs: (inputs) => {
 *     const { messages } = inputs;
 *     return {
 *       messages: messages?.map((message) => ({
 *         ...message,
 *         content: "REDACTED",
 *       })),
 *       prompt: "REDACTED",
 *     };
 *   },
 * });
 * ```
 *
 * Note: AI SDK expects only JSON values in an object for
 * provider options, but LangSmith's config may contain non-JSON values.
 * These are not passed to the underlying AI SDK model, so it is safe to
 * cast the typing here.
 */
export const createLangSmithProviderOptions = <
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  T extends (...args: any[]) => any
>(
  lsConfig?: WrapAISDKConfig<T>
) => {
  return (lsConfig ?? {}) as Record<string, JSONValue>;
};

/**
 * Wraps Vercel AI SDK 6 or AI SDK 5 functions with LangSmith tracing capabilities.
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
  T extends {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    wrapLanguageModel: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    generateText: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    streamText: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    streamObject?: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    generateObject?: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ToolLoopAgent?: any;
  }
>(
  ai: T,
  baseLsConfig?: WrapAISDKConfig
) => {
  const _baseLsConfig: WrapAISDKConfig = {
    ...baseLsConfig,
    metadata: { ls_integration: "vercel-ai-sdk", ls_integration_version: _getPackageVersion("ai"), ...baseLsConfig?.metadata },
  };
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
    ...args: Parameters<typeof ai.generateText>
  ) => {
    const params = args[0];
    const { langsmith: runtimeLsConfig, ...providerOptions } =
      params.providerOptions ?? {};
    const { resolvedLsConfig, resolvedChildLLMRunConfig, resolvedToolConfig } =
      _resolveConfigs(_baseLsConfig, runtimeLsConfig);
    const hasExplicitOutput = "output" in params;
    const hasExplicitExperimentalOutput = "experimental_output" in params;
    const traceableFunc = traceable(
      async (
        ...args: Parameters<typeof ai.generateText>
      ): Promise<ReturnType<typeof ai.generateText>> => {
        const [params, ...rest] = args;
        const wrappedModel = ai.wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            // TODO: Fix this typing on minor bump
            lsConfig: resolvedChildLLMRunConfig as Record<string, unknown>,
          }),
        });
        return ai.generateText(
          {
            ...params,
            providerOptions,
            tools: _wrapTools(params.tools, resolvedToolConfig),
            model: wrappedModel,
          },
          ...rest
        );
      },
      _getGenerateTextWrapperConfig({
        model: params.model,
        resolvedLsConfig,
        hasExplicitOutput,
        hasExplicitExperimentalOutput,
      })
    ) as (
      ...args: Parameters<typeof ai.generateText>
    ) => Promise<ReturnType<typeof ai.generateText>>;
    return traceableFunc(...args);
  };

  let wrappedGenerateObject;
  if (typeof ai.generateObject === "function") {
    const generateObject = ai.generateObject;
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
    wrappedGenerateObject = async (
      ...args: Parameters<typeof generateObject>
    ) => {
      const params = args[0];
      const { langsmith: runtimeLsConfig, ...providerOptions } =
        params.providerOptions ?? {};
      const { resolvedLsConfig, resolvedChildLLMRunConfig } = _resolveConfigs(
        _baseLsConfig,
        runtimeLsConfig
      );
      const traceableFunc = traceable(
        async (
          ...args: Parameters<typeof generateObject>
        ): Promise<ReturnType<typeof generateObject>> => {
          const [params, ...rest] = args;
          const wrappedModel = ai.wrapLanguageModel({
            model: params.model,
            middleware: LangSmithMiddleware({
              name: _getModelDisplayName(params.model),
              modelId: _getModelId(params.model),
              // TODO: Fix this typing on minor bump
              lsConfig: resolvedChildLLMRunConfig as Record<string, unknown>,
            }),
          });
          return generateObject(
            {
              ...params,
              providerOptions,
              model: wrappedModel,
            },
            ...rest
          ) as ReturnType<typeof generateObject>;
        },
        {
          name: _getModelDisplayName(params.model),
          ...resolvedLsConfig,
          metadata: {
            ai_sdk_method: "ai.generateObject",
            ...resolvedLsConfig?.metadata,
          },
          processInputs: async (inputs) => {
            const inputFormatter =
              resolvedLsConfig?.processInputs ?? _formatTracedInputs;
            return inputFormatter(inputs);
          },
          processOutputs: async (outputs) => {
            if (resolvedLsConfig?.processOutputs) {
              const processedOutputs = await resolvedLsConfig.processOutputs(
                // TODO: Fix this typing on minor bump
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                outputs as any
              );
              return processedOutputs;
            }
            if (
              outputs.outputs == null ||
              typeof outputs.outputs !== "object"
            ) {
              return outputs;
            }
            return outputs.outputs.object ?? outputs;
          },
        }
      ) as (
        ...args: Parameters<typeof generateObject>
      ) => Promise<ReturnType<typeof generateObject>>;
      return traceableFunc(...args);
    };
  }

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
  const wrappedStreamText = (...args: Parameters<typeof ai.streamText>) => {
    const params = args[0];
    const { langsmith: runtimeLsConfig, ...providerOptions } =
      params.providerOptions ?? {};
    const { resolvedLsConfig, resolvedChildLLMRunConfig, resolvedToolConfig } =
      _resolveConfigs(_baseLsConfig, runtimeLsConfig);
    const hasExplicitOutput = "output" in params;
    const hasExplicitExperimentalOutput = "experimental_output" in params;
    const traceableFunc = traceable(
      (
        ...args: Parameters<typeof ai.streamText>
      ): ReturnType<typeof ai.streamText> => {
        const [params, ...rest] = args;
        const wrappedModel = ai.wrapLanguageModel({
          model: params.model,
          middleware: LangSmithMiddleware({
            name: _getModelDisplayName(params.model),
            modelId: _getModelId(params.model),
            // TODO: Fix this typing on minor bump
            lsConfig: resolvedChildLLMRunConfig as Record<string, unknown>,
          }),
        });
        return ai.streamText(
          {
            ...params,
            providerOptions,
            tools: _wrapTools(params.tools, resolvedToolConfig),
            model: wrappedModel,
          },
          ...rest
        ) as ReturnType<typeof ai.streamText>;
      },
      _getStreamTextWrapperConfig({
        model: params.model,
        resolvedLsConfig,
        hasExplicitOutput,
        hasExplicitExperimentalOutput,
      })
    ) as (
      ...args: Parameters<typeof ai.streamText>
    ) => ReturnType<typeof ai.streamText>;
    return traceableFunc(...args);
  };

  let wrappedStreamObject;
  if (typeof ai.streamObject === "function") {
    const streamObject = ai.streamObject;
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
    wrappedStreamObject = (...args: Parameters<typeof streamObject>) => {
      const params = args[0];
      const { langsmith: runtimeLsConfig, ...providerOptions } =
        params.providerOptions ?? {};
      const { resolvedLsConfig, resolvedChildLLMRunConfig } = _resolveConfigs(
        _baseLsConfig,
        runtimeLsConfig
      );
      const traceableFunc = traceable(
        (
          ...args: Parameters<typeof streamObject>
        ): ReturnType<typeof streamObject> => {
          const [params, ...rest] = args;
          const wrappedModel = ai.wrapLanguageModel({
            model: params.model,
            middleware: LangSmithMiddleware({
              name: _getModelDisplayName(params.model),
              modelId: _getModelId(params.model),
              // TODO: Fix this typing on minor bump
              lsConfig: resolvedChildLLMRunConfig as Record<string, unknown>,
            }),
          });
          return streamObject(
            {
              ...params,
              providerOptions,
              model: wrappedModel,
            },
            ...rest
          ) as ReturnType<typeof ai.streamObject>;
        },
        {
          name: _getModelDisplayName(params.model),
          ...resolvedLsConfig,
          metadata: {
            ai_sdk_method: "ai.streamObject",
            ...resolvedLsConfig?.metadata,
          },
          processInputs: async (inputs) => {
            const inputFormatter =
              resolvedLsConfig?.processInputs ?? _formatTracedInputs;
            return inputFormatter(inputs);
          },
          processOutputs: async (outputs) => {
            try {
              if (resolvedLsConfig?.processOutputs) {
                const processedOutputs = await resolvedLsConfig.processOutputs(
                  // TODO: Fix this typing on minor bump
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  outputs as any
                );
                return processedOutputs;
              }
              if (
                outputs.outputs == null ||
                typeof outputs.outputs !== "object"
              ) {
                return outputs;
              }
              const object = await outputs.outputs.object;
              if (object == null || typeof object !== "object") {
                return outputs;
              }
              return object;
            } catch {
              // Handle parsing failures without a log
              return outputs;
            }
          },
        }
      ) as (
        ...args: Parameters<typeof streamObject>
      ) => ReturnType<typeof streamObject>;
      return traceableFunc(...args);
    };
  }

  let wrappedToolLoopAgentClass;
  if (ai.ToolLoopAgent != null) {
    try {
      const wrapToolLoopAgent = (ToolLoopAgent: any) => {
        return new Proxy(ToolLoopAgent, {
          construct(ToolLoopAgent, args) {
            const params = args[0] ?? {};
            const { langsmith: runtimeLsConfig } = params.providerOptions ?? {};
            const {
              resolvedLsConfig,
              resolvedChildLLMRunConfig,
              resolvedToolConfig,
            } = _resolveConfigs(_baseLsConfig, runtimeLsConfig);
            let wrappedModel = params.model;
            if (wrappedModel != null) {
              wrappedModel = ai.wrapLanguageModel({
                model: params.model,
                middleware: LangSmithMiddleware({
                  name: _getModelDisplayName(params.model),
                  modelId: _getModelId(params.model),
                  // TODO: Fix this typing on minor bump
                  lsConfig: resolvedChildLLMRunConfig as Record<
                    string,
                    unknown
                  >,
                }),
              });
            }
            let wrappedTools = params.tools;
            if (wrappedTools != null) {
              wrappedTools = _wrapTools(params.tools, resolvedToolConfig);
            }
            const instance = new ToolLoopAgent(
              ...[
                { ...params, model: wrappedModel, tools: wrappedTools },
                ...args.slice(1),
              ]
            );
            if (typeof instance.generate === "function") {
              instance.generate = traceable(
                instance.generate.bind(instance),
                _getGenerateTextWrapperConfig({
                  model: wrappedModel,
                  runName: "ToolLoopAgent",
                  aiSdkMethodName: "ai.ToolLoopAgent.generate",
                  resolvedLsConfig,
                  hasExplicitOutput:
                    "output" in params && params.output != null,
                  traceResponseMetadata: true,
                })
              );
            }
            if (typeof instance.stream === "function") {
              instance.stream = traceable(
                instance.stream.bind(instance),
                _getStreamTextWrapperConfig({
                  model: wrappedModel,
                  runName: "ToolLoopAgent",
                  aiSdkMethodName: "ai.ToolLoopAgent.stream",
                  resolvedLsConfig,
                  hasExplicitOutput:
                    "output" in params && params.output != null,
                  traceResponseMetadata: true,
                })
              );
            }
            return instance;
          },
        });
      };
      wrappedToolLoopAgentClass = wrapToolLoopAgent(ai.ToolLoopAgent);
    } catch (e) {
      console.error("Failed to wrap passed ToolLoopAgent:", e);
      wrappedToolLoopAgentClass = ai.ToolLoopAgent;
    }
  }

  return {
    ...ai,
    generateText: wrappedGenerateText,
    generateObject: wrappedGenerateObject,
    streamText: wrappedStreamText,
    streamObject: wrappedStreamObject,
    ToolLoopAgent: wrappedToolLoopAgentClass,
  } as T;
};

export { wrapAISDK };

export { convertMessageToTracedFormat };
