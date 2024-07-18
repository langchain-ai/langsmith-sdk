import type { Client } from "../index.js";
import { traceable } from "../traceable.js";

const _wrapClient = <T extends object>(
  sdk: T,
  runName: string,
  options?: { client?: Client }
): T => {
  return new Proxy(sdk, {
    apply(target, thisArg, argumentsList) {
      return traceable(
        (target as (...args: any[]) => any).bind(thisArg),
        Object.assign({ name: runName, run_type: "llm" }, options)
      )(...argumentsList);
    },
    get(target, propKey, receiver) {
      const originalValue = target[propKey as keyof T];
      if (typeof originalValue === "function") {
        return traceable(
          originalValue.bind(target),
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
