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

class AsyncLocalStorageProvider {
  private asyncLocalStorage: AsyncLocalStorageInterface =
    new MockAsyncLocalStorage();

  private hasBeenInitialized = false;

  getInstance(): AsyncLocalStorageInterface {
    return this.asyncLocalStorage;
  }

  initializeGlobalInstance(instance: AsyncLocalStorageInterface) {
    if (!this.hasBeenInitialized) {
      this.hasBeenInitialized = true;
      this.asyncLocalStorage = instance;
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
        "Please make sure you are calling this method within a traceable function.",
      ].join("\n")
    );
  }

  return runTree;
};

export const ROOT = Symbol.for("langsmith:traceable:root");

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any> {
  return typeof x === "function" && "langsmith:traceable" in x;
}
