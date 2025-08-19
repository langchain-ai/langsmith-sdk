import { getLangSmithEnvironmentVariable } from "../utils/env.js";

// Wrap the default fetch call due to issues with illegal invocations
// in some environments:
// https://stackoverflow.com/questions/69876859/why-does-bind-fix-failed-to-execute-fetch-on-window-illegal-invocation-err
// @ts-expect-error Broad typing to support a range of fetch implementations
const DEFAULT_FETCH_IMPLEMENTATION = (...args: any[]) => fetch(...args);

const LANGSMITH_FETCH_IMPLEMENTATION_KEY = Symbol.for(
  "ls:fetch_implementation"
);

/**
 * Overrides the fetch implementation used for LangSmith calls.
 * You should use this if you need to use an implementation of fetch
 * other than the default global (e.g. for dealing with proxies).
 * @param fetch The new fetch function to use.
 */
export const overrideFetchImplementation = (fetch: (...args: any[]) => any) => {
  (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] = fetch;
};

export const _globalFetchImplementationIsNodeFetch = () => {
  const fetchImpl = (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY];
  if (!fetchImpl) return false;

  // Check if the implementation has node-fetch specific properties
  return (
    typeof fetchImpl === "function" &&
    "Headers" in fetchImpl &&
    "Request" in fetchImpl &&
    "Response" in fetchImpl
  );
};

/**
 * @internal
 */
export const _getFetchImplementation: (
  debug?: boolean
) => (...args: any[]) => any = (debug?: boolean) => {
  return async (...args: any[]) => {
    const [url, options, ...rest] = args;
    if (debug || getLangSmithEnvironmentVariable("DEBUG") === "true") {
      console.log(`→ ${options?.method || "GET"} ${url}`);
    }
    if (options.timeout_ms) {
      if (!options.signal) {
        options.signal = AbortSignal.timeout(options.timeout_ms);
      } else {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          options.timeout_ms
        );
        options.signal.addEventListener("abort", () => {
          clearTimeout(timeoutId);
          controller.abort();
        });
        options.signal = controller.signal;
      }
      delete options.timeout_ms;
    }
    const res = await (
      (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] ??
      DEFAULT_FETCH_IMPLEMENTATION
    )(url, options, ...rest);
    if (debug || getLangSmithEnvironmentVariable("DEBUG") === "true") {
      console.log(`← ${res.status} ${res.statusText} ${res.url}`);
    }
    return res;
  };
};
