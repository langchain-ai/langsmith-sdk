import { RunTree, RunTreeConfig, isRunTree } from "./run_trees.js";
import { KVMap } from "./schemas.js";

/**
 * Higher-order function for creating or adding a run to a run tree.
 *
 * @param wrappedFunc Targeted function to be traced
 * @param config Useful for adding additional metadata such as name, tags or providing custom LangSmith client instance
 */
export function traceable<Inputs extends unknown[], Output>(
  wrappedFunc: (runTree: RunTree, ...inputs: Inputs) => Output,
  config?: RunTreeConfig
) {
  const traceableFunc: TraceableFunction<Inputs, Output> = async (
    inputRunTree: RunTree | RunTreeConfig,
    ...rawInputs: Inputs
  ): Promise<Output> => {
    let currentRunTree: RunTree;
    const ensuredConfig: RunTreeConfig = {
      name: wrappedFunc.name || "<lambda>",
      ...config,
    };

    if (isRunTree(inputRunTree)) {
      currentRunTree = await inputRunTree.createChild(ensuredConfig);
    } else {
      currentRunTree = new RunTree({ ...ensuredConfig, ...inputRunTree });
    }

    let inputs: KVMap;
    const firstInput = rawInputs[0];
    if (firstInput == null) {
      inputs = {};
    } else if (rawInputs.length > 1) {
      inputs = { args: rawInputs };
    } else if (isKVMap(firstInput)) {
      inputs = firstInput;
    } else {
      inputs = { input: firstInput };
    }

    currentRunTree.inputs = inputs;

    const initialOutputs = currentRunTree.outputs;
    const initialError = currentRunTree.error;

    try {
      const rawOutput = await wrappedFunc(currentRunTree, ...rawInputs);
      const outputs: KVMap = isKVMap(rawOutput)
        ? rawOutput
        : { outputs: rawOutput };

      if (initialOutputs === currentRunTree.outputs) {
        await currentRunTree.end(outputs);
      } else {
        currentRunTree.end_time = Date.now();
      }

      return rawOutput;
    } catch (error) {
      if (initialError === currentRunTree.error) {
        await currentRunTree.end(initialOutputs, String(error));
      } else {
        currentRunTree.end_time = Date.now();
      }

      throw error;
    } finally {
      await currentRunTree.postRun();
    }
  };
  Object.defineProperty(wrappedFunc, "langsmith:traceable", {
    value: config,
  });
  return traceableFunc;
}

export type TraceableFunction<Inputs extends unknown[], Output> = (
  runTree: RunTree,
  ...rawInputs: Inputs
) => Promise<Output>;

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any, any> {
  return typeof x === "function" && "langsmith:traceable" in x;
}

function isKVMap(x: unknown): x is Record<string, unknown> {
  return (
    typeof x === "object" &&
    x != null &&
    !Array.isArray(x) &&
    // eslint-disable-next-line no-instanceof/no-instanceof
    !(x instanceof Date)
  );
}
