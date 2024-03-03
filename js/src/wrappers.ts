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

export const wrapClient = <T extends object>(
  sdk: T,
  options?: { client?: Client; runName?: string }
): T => {
  return _wrapClient(sdk, options?.runName ?? sdk.constructor?.name, {
    client: options?.client,
  });
};
