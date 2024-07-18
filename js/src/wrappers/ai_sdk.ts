import type { Client } from "../index.js";
import { traceable } from "../traceable.js";
import { isAsyncIterable } from "../utils/asserts.js";

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
          async (...args: any[]) => {
            const originalRes = await originalValue.bind(target)(...args);
            if (originalRes?.stream !== undefined && isAsyncIterable(originalRes.stream)) {
              return originalRes;
            }
            return originalRes;
          },
          Object.assign(
            { name: [runName, propKey.toString()].join("."), run_type: "llm" },
            options
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
 * Wrap a model instance of the AI SDK, enabling automatic LangSmith tracing.
 * Method signatures are unchanged.
 *
 * Note that this will wrap and trace ALL SDK methods, not just
 * LLM completion methods. If the passed SDK contains other methods,
 * we recommend using the wrapped instance for LLM calls only.
 * @param sdk An arbitrary SDK instance.
 * @param options LangSmith options.
 * @returns
 */
export const wrapAISDKModel = <T extends object>(
  sdk: T,
  options?: { client?: Client; runName?: string }
): T => {
  if (!("doGenerate" in sdk) || typeof sdk.doGenerate !== "function") {
    console.warn([
      "It appears you are not passing an instance of an AI SDK model.",
      `Please double check your inputs to "wrapAISDKModel".`,
      "",
      "If you are passing an AI SDK model, disregard this message."
    ].join("\n"));
  }
  return _wrapClient(sdk, options?.runName ?? sdk.constructor?.name, {
    client: options?.client,
  });
};
