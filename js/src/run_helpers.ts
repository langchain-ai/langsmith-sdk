import { v4 as uuidv4 } from "uuid";
import { RunTree, RunTreeConfig, isRunTree } from "./run_trees.js";
import { KVMap } from "./schemas.js";

export type TraceableFunction<Inputs extends any[], Output> = (
  ...rawInputs: Inputs | [RunTree, ...Inputs]
) => Promise<[Output, RunTree]>;

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any, any> {
  return typeof x === "function" && "langsmith:traceable" in x;
}

export function traceable<Inputs extends any[], Output>(
  wrappedFunc: (...inputs: Inputs) => Output,
  config?: RunTreeConfig
) {
  const traceableFunc: TraceableFunction<Inputs, Output> = async (
    ...rawInputs: Inputs | [RunTree, ...Inputs]
  ): Promise<[Output, RunTree]> => {
    let inputRunTree: RunTree | undefined;
    let currentRunTree: RunTree;
    let wrappedFunctionInputs: Inputs;
    const ensuredConfig = { name: "traced_function", ...config };

    if (isRunTree(rawInputs[0])) {
      [inputRunTree, ...wrappedFunctionInputs] = rawInputs as [
        RunTree,
        ...Inputs
      ];
      if ("root" in inputRunTree) {
        currentRunTree = inputRunTree.root as RunTree;
      } else {
        currentRunTree = await inputRunTree.createChild(ensuredConfig); 
      }
    } else {
      wrappedFunctionInputs = rawInputs as Inputs;
      currentRunTree = new RunTree({
        id: uuidv4(),
        run_type: "chain",
        ...ensuredConfig,
      });
    }
    let inputs: KVMap;
    const firstWrappedFunctionInput = wrappedFunctionInputs[0];
    if (firstWrappedFunctionInput == null) {
      inputs = {};
    } else if (wrappedFunctionInputs.length > 1) {
      inputs = { args: wrappedFunctionInputs };
    } else if (
      typeof firstWrappedFunctionInput === "object" &&
      !Array.isArray(firstWrappedFunctionInput) &&
      // eslint-disable-next-line no-instanceof/no-instanceof
      !(firstWrappedFunctionInput instanceof Date)
    ) {
      inputs = firstWrappedFunctionInput;
    } else {
      inputs = { input: firstWrappedFunctionInput };
    }

    if ("root" in currentRunTree) {
      Object.assign(currentRunTree, { ...ensuredConfig });
    }

    currentRunTree.inputs = inputs;

    const initialOutputs = currentRunTree.outputs;
    const initialError = currentRunTree.error;

    try {
      const rawOutput = await wrappedFunc(...wrappedFunctionInputs);
      const outputs: KVMap =
        typeof rawOutput === "object" &&
        rawOutput != null &&
        !Array.isArray(rawOutput) &&
        // eslint-disable-next-line no-instanceof/no-instanceof
        !(rawOutput instanceof Date)
          ? rawOutput
          : { outputs: rawOutput };

      if (initialOutputs === currentRunTree.outputs) {
        await currentRunTree.end(outputs);
      } else {
        currentRunTree.end_time = Date.now();
      }
      return [rawOutput, currentRunTree];
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
