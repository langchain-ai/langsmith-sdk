// Wrap the default fetch call due to issues with illegal invocations
// in some environments:
// https://stackoverflow.com/questions/69876859/why-does-bind-fix-failed-to-execute-fetch-on-window-illegal-invocation-err
// @ts-expect-error Broad typing to support a range of fetch implementations
const DEFAULT_FETCH_IMPLEMENTATION = (...args: any[]) => fetch(...args);

const LANGSMITH_FETCH_IMPLEMENTATION_KEY = Symbol.for(
  "ls:fetch_implementation"
);

export const setFetchImplementation = (fetch: (...args: any[]) => any) => {
  (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] = fetch;
};

export const getFetchImplementation = () => {
  return (
    (globalThis as any)[LANGSMITH_FETCH_IMPLEMENTATION_KEY] ??
    DEFAULT_FETCH_IMPLEMENTATION
  );
};
