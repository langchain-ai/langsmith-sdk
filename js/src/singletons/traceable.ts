import type { RunTree } from "../run_trees.js";
import type { ContextPlaceholder, TraceableFunction } from "./types.js";

interface AsyncLocalStorageInterface {
  getStore: () => RunTree | ContextPlaceholder | undefined;

  run: (
    context: RunTree | ContextPlaceholder | undefined,
    fn: () => void
  ) => void;
}

class MockAsyncLocalStorage implements AsyncLocalStorageInterface {
  getStore() {
    return undefined;
  }

  run(_: RunTree | ContextPlaceholder | undefined, callback: () => void): void {
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
export function getCurrentRunTree(): RunTree;

export function getCurrentRunTree(permitAbsentRunTree: false): RunTree;

export function getCurrentRunTree(
  permitAbsentRunTree: boolean
): RunTree | undefined;

export function getCurrentRunTree(permitAbsentRunTree = false) {
  const runTree = AsyncLocalStorageProviderSingleton.getInstance().getStore();
  if (!permitAbsentRunTree && runTree === undefined) {
    throw new Error(
      "Could not get the current run tree.\n\nPlease make sure you are calling this method within a traceable function and that tracing is enabled."
    );
  }

  return runTree;
}

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
