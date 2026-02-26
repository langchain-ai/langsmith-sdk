import { createRequire } from "module";
import { traceable, isTraceableFunction } from "../../traceable.js";
import { StreamManager, type WrapClaudeAgentSDKConfig } from "./context.js";
import { convertFromAnthropicMessage } from "./messages.js";
import type { SDKMessage, SDKUserMessage, QueryOptions } from "./types.js";

function _getPackageVersion(packageName: string): string | undefined {
  try {
    const req = createRequire(process.cwd() + "/package.json");
    return (req(`${packageName}/package.json`) as { version?: string }).version;
  } catch {
    return undefined;
  }
}

/**
 * Wraps the Claude Agent SDK's query function to add LangSmith tracing.
 * Traces the entire agent interaction including all streaming messages.
 * @internal Use `wrapClaudeAgentSDK` instead.
 */
function wrapClaudeAgentQuery<
  T extends (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>
>(queryFn: T, defaultThis?: unknown, baseConfig?: WrapClaudeAgentSDKConfig): T {
  async function* generator(
    originalGenerator: AsyncGenerator<SDKMessage, void, unknown>,
    prompt: string | AsyncIterable<SDKMessage> | undefined
  ) {
    const streamManager = new StreamManager();
    try {
      let systemCount = 0;
      for await (const message of originalGenerator) {
        if (message.type === "system") {
          const content = getLatestInput(prompt, systemCount);
          systemCount += 1;

          if (content != null) streamManager.addMessage(content);
        }

        streamManager.addMessage(message);
        yield message;
      }
    } finally {
      await streamManager.finish();
    }
  }

  function getLatestInput(
    arg: string | AsyncIterable<SDKMessage> | undefined,
    systemCount: number
  ): SDKUserMessage | undefined {
    const value = (() => {
      if (typeof arg !== "object" || arg == null) return arg;

      const toJSON = (arg as unknown as Record<string, unknown>)["toJSON"];
      if (typeof toJSON !== "function") return undefined;
      const latest = toJSON();
      return latest?.at(systemCount);
    })();

    if (value == null) return undefined;
    if (typeof value === "string") {
      return {
        type: "user" as const,
        message: { content: value, role: "user" },
        parent_tool_use_id: null,
        session_id: "",
      };
    }

    return typeof value === "object" && value != null ? value : undefined;
  }

  async function processInputs(rawInputs: unknown) {
    const inputs = rawInputs as {
      prompt: string | AsyncIterable<SDKUserMessage>;
      options: QueryOptions;
    };

    const newInputs = { ...inputs } as {
      prompt: string | AsyncIterable<SDKUserMessage>;
      options: Record<string, unknown>;
    };

    return Object.assign(newInputs, {
      toJSON: () => {
        const toJSON = (value: unknown) => {
          if (typeof value !== "object" || value == null) return value;
          const fn = (value as Record<string, unknown>)?.toJSON;
          if (typeof fn === "function") return fn();
          return value;
        };

        const prompt = toJSON(inputs.prompt) as
          | string
          | Iterable<SDKUserMessage>
          | undefined;

        const options: Record<string, unknown> | undefined =
          inputs.options != null
            ? ({ ...inputs.options } as QueryOptions)
            : undefined;

        if (options?.mcpServers != null) {
          options.mcpServers = Object.fromEntries(
            Object.entries(options.mcpServers ?? {}).map(([key, value]) => [
              key,
              { name: value.name, type: value.type },
            ])
          );
        }

        return { messages: convertFromAnthropicMessage(prompt), options };
      },
    });
  }

  function processOutputs(rawOutputs: Record<string, unknown>) {
    if ("outputs" in rawOutputs && Array.isArray(rawOutputs.outputs)) {
      const sdkMessages = rawOutputs.outputs as SDKMessage[];
      const messages = sdkMessages
        .filter((message) => {
          if (!("message" in message)) return true;
          return message.parent_tool_use_id == null;
        })
        .flatMap(convertFromAnthropicMessage);

      return { output: { messages } };
    }
    return rawOutputs;
  }

  return traceable(
    (
      params: {
        prompt: string | AsyncIterable<SDKMessage>;
        options: QueryOptions;
      },
      ...args: unknown[]
    ) => {
      const actualGenerator = queryFn.call(defaultThis, params, ...args);
      const wrappedGenerator = generator(actualGenerator, params.prompt);

      for (const method of Object.getOwnPropertyNames(
        Object.getPrototypeOf(actualGenerator)
      ).filter(
        (method) => !["constructor", "next", "throw", "return"].includes(method)
      )) {
        Object.defineProperty(wrappedGenerator, method, {
          get() {
            const getValue =
              actualGenerator?.[method as keyof typeof actualGenerator];
            if (typeof getValue === "function")
              return getValue.bind(actualGenerator);
            return getValue;
          },
        });
      }

      return wrappedGenerator;
    },
    {
      name: "claude.conversation",
      run_type: "chain",
      ...baseConfig,
      metadata: {
        ls_integration: "claude-agent-sdk",
        ls_integration_version: _getPackageVersion(
          "@anthropic-ai/claude-agent-sdk"
        ),
        ...baseConfig?.metadata,
      },
      __deferredSerializableArgOptions: { maxDepth: 1 },
      processInputs,
      processOutputs,
    }
  ) as unknown as T;
}

/**
 * Wraps the Claude Agent SDK with LangSmith tracing. This returns wrapped versions
 * of query and tool that automatically trace all agent interactions.
 *
 * @param sdk - The Claude Agent SDK module
 * @param config - Optional LangSmith configuration
 * @returns Object with wrapped query, tool, and createSdkMcpServer functions
 *
 * @example
 * ```typescript
 * import * as claudeSDK from "@anthropic-ai/claude-agent-sdk";
 * import { wrapClaudeAgentSDK } from "langsmith/experimental/claude_agent_sdk";
 *
 * // Wrap once - returns { query, tool, createSdkMcpServer } with tracing built-in
 * const { query, tool, createSdkMcpServer } = wrapClaudeAgentSDK(claudeSDK);
 *
 * // Use normally - tracing is automatic
 * for await (const message of query({
 *   prompt: "Hello, Claude!",
 *   options: { model: "claude-haiku-4-5-20251001" }
 * })) {
 *   console.log(message);
 * }
 *
 * // Tools created with wrapped tool() are automatically traced
 * const calculator = tool("calculator", "Does math", schema, handler);
 * ```
 */
export function wrapClaudeAgentSDK<T extends object>(
  sdk: T,
  config?: WrapClaudeAgentSDKConfig
): T {
  type TypedSdk = T & {
    query?: (...args: unknown[]) => AsyncGenerator<SDKMessage, void, unknown>;
    tool?: (...args: unknown[]) => unknown;
    createSdkMcpServer?: () => unknown;

    unstable_v2_createSession?: (...args: unknown[]) => unknown;
    unstable_v2_prompt?: (...args: unknown[]) => unknown;
    unstable_v2_resumeSession?: (...args: unknown[]) => unknown;
  };

  const inputSdk = sdk as TypedSdk;
  const wrappedSdk = { ...sdk } as TypedSdk;

  if ("query" in inputSdk && isTraceableFunction(inputSdk.query)) {
    throw new Error(
      "This instance of Claude Agent SDK has been already wrapped by `wrapClaudeAgentSDK`."
    );
  }

  // Wrap the query method if it exists
  if ("query" in inputSdk && typeof inputSdk.query === "function") {
    wrappedSdk.query = wrapClaudeAgentQuery(inputSdk.query, inputSdk, config);
  }

  // Wrap the tool method if it exists
  if ("tool" in inputSdk && typeof inputSdk.tool === "function") {
    wrappedSdk.tool = inputSdk.tool.bind(inputSdk);
  }

  // Keep createSdkMcpServer and other methods as-is (bound to original SDK)
  if (
    "createSdkMcpServer" in inputSdk &&
    typeof inputSdk.createSdkMcpServer === "function"
  ) {
    wrappedSdk.createSdkMcpServer = inputSdk.createSdkMcpServer.bind(inputSdk);
  }

  if (
    "unstable_v2_createSession" in inputSdk &&
    typeof inputSdk.unstable_v2_createSession === "function"
  ) {
    wrappedSdk.unstable_v2_createSession = (
      ...args: Parameters<typeof inputSdk.unstable_v2_createSession>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_createSession` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_createSession?.(...args);
    };
  }
  if (
    "unstable_v2_prompt" in inputSdk &&
    typeof inputSdk.unstable_v2_prompt === "function"
  ) {
    wrappedSdk.unstable_v2_prompt = (
      ...args: Parameters<typeof inputSdk.unstable_v2_prompt>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_prompt` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_prompt?.(...args);
    };
  }
  if (
    "unstable_v2_resumeSession" in inputSdk &&
    typeof inputSdk.unstable_v2_resumeSession === "function"
  ) {
    wrappedSdk.unstable_v2_resumeSession = (
      ...args: Parameters<typeof inputSdk.unstable_v2_resumeSession>
    ) => {
      console.warn(
        "Tracing of `unstable_v2_resumeSession` is not supported by LangSmith. Tracing will not be applied."
      );
      return inputSdk.unstable_v2_resumeSession?.(...args);
    };
  }

  return wrappedSdk as T;
}
