import type { Client } from "./index.js";
import { traceable } from "./traceable.js";

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

/**
 * Wraps an OpenAI client's completion methods, enabling automatic LangSmith
 * tracing. Method signatures are unchanged.
 * @param openai An OpenAI client instance.
 * @param options LangSmith options.
 * @returns
 */
export const wrapOpenAI = <T extends OpenAIType>(
  openai: T,
  options?: { client?: Client }
): T => {
  openai.chat.completions.create = traceable(
    openai.chat.completions.create.bind(openai.chat.completions),
    Object.assign({ name: "ChatOpenAI", run_type: "llm" }, options?.client)
  );

  openai.completions.create = traceable(
    openai.completions.create.bind(openai.completions),
    Object.assign({ name: "OpenAI", run_type: "llm" }, options?.client)
  );

  return openai;
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
