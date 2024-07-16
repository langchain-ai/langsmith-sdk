import { RunTree } from "../run_trees.js";
import { TraceableFunction } from "./types.js";

interface AsyncLocalStorageInterface {
  getStore: () => RunTree | undefined;

  run: (context: RunTree | undefined, fn: () => void) => void;
}

class MockAsyncLocalStorage implements AsyncLocalStorageInterface {
  getStore() {
    return undefined;
  }

  run(_: RunTree | undefined, callback: () => void): void {
    return callback();
  }
}

const TRACING_ALS_KEY = Symbol.for("ls:tracing_async_local_storage");

const mockAsyncLocalStorage = new MockAsyncLocalStorage();

class AsyncLocalStorageProvider {
  getInstance(): AsyncLocalStorageInterface {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (globalThis as any)[TRACING_ALS_KEY] ?? mockAsyncLocalStorage;
  }

  initializeGlobalInstance(instance: AsyncLocalStorageInterface) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((globalThis as any)[TRACING_ALS_KEY] === undefined) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any)[TRACING_ALS_KEY] = instance;
    }
  }
}

export const AsyncLocalStorageProviderSingleton =
  new AsyncLocalStorageProvider();

/**
 * Return the current run tree from within a traceable-wrapped function.
 * Will throw an error if called outside of a traceable function.
 *
 * @returns The run tree for the given context.
 */
export const getCurrentRunTree = () => {
  const runTree = AsyncLocalStorageProviderSingleton.getInstance().getStore();
  if (runTree === undefined) {
    throw new Error(
      [
        "Could not get the current run tree.",
        "",
        "Please make sure you are calling this method within a traceable function or the tracing is enabled.",
      ].join("\n")
    );
  }

  return runTree;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function withRunTree<Fn extends (...args: any[]) => any>(
  runTree: RunTree,
  fn: Fn
): Promise<Awaited<ReturnType<Fn>>> {
  const storage = AsyncLocalStorageProviderSingleton.getInstance();
  return new Promise<Awaited<ReturnType<Fn>>>((resolve, reject) => {
    storage.run(
      runTree,
      () => void Promise.resolve(fn()).then(resolve).catch(reject)
    );
  });
}

export const ROOT = Symbol.for("langsmith:traceable:root");

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any> {
  return typeof x === "function" && "langsmith:traceable" in x;
}

export type { TraceableFunction } from "./types.js";
