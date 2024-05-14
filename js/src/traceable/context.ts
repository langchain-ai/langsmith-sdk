import { RunTree } from "../run_trees.js";

interface AsyncStorageLike {
  getStore: () => RunTree | undefined;

  run: (context: RunTree | undefined, fn: () => void) => void;
}

export const TraceableLocalStorageContext = (() => {
  let storage: AsyncStorageLike;

  return {
    register: (value: AsyncStorageLike) => {
      storage ??= value;
      return storage;
    },
    get storage() {
      return storage;
    },
  };
})();

/**
 * Return the current run tree from within a traceable-wrapped function.
 * Will throw an error if called outside of a traceable function.
 *
 * @returns The run tree for the given context.
 */
export const getCurrentRunTree = () => {
  if (!TraceableLocalStorageContext.storage) {
    throw new Error("Could not find the traceable storage context");
  }

  const runTree = TraceableLocalStorageContext.storage.getStore();
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
