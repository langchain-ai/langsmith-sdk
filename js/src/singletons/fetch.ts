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
 * @param fetch The new fetch functino to use.
 */
export const overrideFetchImplementation = (fetch: (...args: any[]) => any) => {
  (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] = fetch;
};

/**
 * @internal
 */
export const _getFetchImplementation: (
  debug?: boolean
) => (...args: any[]) => any = (debug?: boolean) => {
  return async (...args: any[]) => {
    if (debug || getLangSmithEnvironmentVariable("DEBUG") === "true") {
      const [url, options] = args;
      console.log(`→ ${options?.method || "GET"} ${url}`);
    }
    const res = await (
      (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] ??
      DEFAULT_FETCH_IMPLEMENTATION
    )(...args);
    if (debug || getLangSmithEnvironmentVariable("DEBUG") === "true") {
      console.log(`← ${res.status} ${res.statusText} ${res.url}`);
    }
    return res;
  };
};
