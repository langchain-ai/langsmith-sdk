import type { OpenAI } from "openai";
import type { Client } from "./index.js";
import {
  isRunnableConfigLike,
  isRunTree,
  type RunnableConfigLike,
} from "./run_trees.js";
import { traceable, type RunTreeLike } from "./traceable.js";

// Extra leniency around types in case multiple OpenAI SDK versions get installed
type OpenAIType = {
  chat: {
    completions: {
      create: (...args: any[]) => any;
    };
  };
  completions: {
    create: (...args: any[]) => any;
  };
};

type PatchedOpenAIClient<T extends OpenAIType> = {
  [P in keyof T]: T[P];
} & {
  chat: {
    completions: {
      create: {
        (
          arg: OpenAI.ChatCompletionCreateParamsStreaming,
          arg2?: OpenAI.RequestOptions & {
            langsmithExtra?: RunnableConfigLike | RunTreeLike;
          }
        ): Promise<AsyncGenerator<OpenAI.ChatCompletionChunk>>;
      } & {
        (
          arg: OpenAI.ChatCompletionCreateParamsNonStreaming,
          arg2?: OpenAI.RequestOptions & {
            langsmithExtra?: RunnableConfigLike | RunTreeLike;
          }
        ): Promise<OpenAI.ChatCompletionChunk>;
      };
    };
  };
  completions: {
    create: {
      (
        arg: OpenAI.CompletionCreateParamsStreaming,
        arg2?: OpenAI.RequestOptions & {
          langsmithExtra?: RunnableConfigLike | RunTreeLike;
        }
      ): Promise<AsyncGenerator<OpenAI.Completion>>;
    } & {
      (
        arg: OpenAI.CompletionCreateParamsNonStreaming,
        arg2?: OpenAI.RequestOptions & {
          langsmithExtra?: RunnableConfigLike | RunTreeLike;
        }
      ): Promise<OpenAI.Completion>;
    };
  };
};

/**
 * Wraps an OpenAI client's completion methods, enabling automatic LangSmith
 * tracing. Method signatures are unchanged, with the exception that you can pass
 * an additional and optional "langsmithExtra" field within the second parameter.
 * @param openai An OpenAI client instance.
 * @param options LangSmith options.
 * @example
 * ```ts
 * const patchedStream = await patchedClient.chat.completions.create(
 *   {
 *     messages: [{ role: "user", content: `Say 'foo'` }],
 *     model: "gpt-3.5-turbo",
 *     stream: true,
 *   },
 *   {
 *     langsmithExtra: {
 *       metadata: {
 *         additional_data: "bar",
 *       },
 *     },
 *   },
 * );
 * ```
 */
export const wrapOpenAI = <T extends OpenAIType>(
  openai: T,
  options?: { client?: Client }
): PatchedOpenAIClient<T> => {
  const originalChatCompletionsFn = openai.chat.completions.create.bind(
    openai.chat.completions
  );
  openai.chat.completions.create = async (...args) => {
    const defaultMetadata = Object.assign(
      { name: "ChatOpenAI", run_type: "llm" },
      options?.client
    );
    const wrappedMethod = traceable(originalChatCompletionsFn, defaultMetadata);
    if (
      isRunTree(args[1]?.langsmithExtra) ||
      isRunnableConfigLike(args[1]?.langsmithExtra)
    ) {
      const { langsmithExtra, ...openAIOptions } = args[1];
      return wrappedMethod(
        langsmithExtra,
        args[0],
        openAIOptions,
        args[1].slice(2)
      );
    }
    return wrappedMethod(...args);
  };

  const originalCompletionsFn = openai.completions.create.bind(
    openai.chat.completions
  );
  openai.completions.create = async (...args) => {
    const defaultMetadata = Object.assign(
      { name: "OpenAI", run_type: "llm" },
      options?.client
    );
    const wrappedMethod = traceable(originalCompletionsFn, defaultMetadata);
    if (
      isRunTree(args[1]?.langsmithExtra) ||
      isRunnableConfigLike(args[1]?.langsmithExtra)
    ) {
      const { langsmithExtra, ...openAIOptions } = args[1];
      return wrappedMethod(
        langsmithExtra,
        args[0],
        openAIOptions,
        args[1].slice(2)
      );
    }
    return wrappedMethod(...args);
  };

  return openai as PatchedOpenAIClient<T>;
};

const _wrapClient = <T extends object>(
  sdk: T,
  runName: string,
  options?: { client?: Client }
): T => {
  return new Proxy(sdk, {
    get(target, propKey, receiver) {
      const originalValue = target[propKey as keyof T];
      if (typeof originalValue === "function") {
        return traceable(
          originalValue.bind(target),
          Object.assign(
            { name: [runName, propKey.toString()].join("."), run_type: "llm" },
            options?.client
          )
        );
      } else if (
        originalValue != null &&
        !Array.isArray(originalValue) &&
        // eslint-disable-next-line no-instanceof/no-instanceof
        !(originalValue instanceof Date) &&
        typeof originalValue === "object"
      ) {
        return _wrapClient(
          originalValue,
          [runName, propKey.toString()].join("."),
          options
        );
      } else {
        return Reflect.get(target, propKey, receiver);
      }
    },
  });
};

/**
 * Wrap an arbitrary SDK, enabling automatic LangSmith tracing.
 * Method signatures are unchanged.
 *
 * Note that this will wrap and trace ALL SDK methods, not just
 * LLM completion methods. If the passed SDK contains other methods,
 * we recommend using the wrapped instance for LLM calls only.
 * @param sdk An arbitrary SDK instance.
 * @param options LangSmith options.
 * @returns
 */
export const wrapSDK = <T extends object>(
  sdk: T,
  options?: { client?: Client; runName?: string }
): T => {
  return _wrapClient(sdk, options?.runName ?? sdk.constructor?.name, {
    client: options?.client,
  });
};
