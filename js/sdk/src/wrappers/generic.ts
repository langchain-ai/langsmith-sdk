import type { RunTreeConfig } from "../index.js";
import { traceable } from "../traceable.js";

export const _wrapClient = <T extends object>(
  sdk: T,
  runName: string,
  options?: Omit<RunTreeConfig, "name">
): T => {
  return new Proxy(sdk, {
    get(target, propKey, receiver) {
      const originalValue = target[propKey as keyof T];
      if (typeof originalValue === "function") {
        return traceable(originalValue.bind(target), {
          run_type: "llm",
          ...options,
          name: [runName, propKey.toString()].join("."),
        });
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

type WrapSDKOptions = Partial<
  RunTreeConfig & {
    /**
     * @deprecated Use `name` instead.
     */
    runName: string;
  }
>;

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
  options?: WrapSDKOptions
): T => {
  const traceableOptions = options ? { ...options } : undefined;
  if (traceableOptions != null) {
    delete traceableOptions.runName;
    delete traceableOptions.name;
  }

  return _wrapClient(
    sdk,
    options?.name ?? options?.runName ?? sdk.constructor?.name,
    traceableOptions
  );
};
