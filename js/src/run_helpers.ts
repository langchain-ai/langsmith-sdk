import { RunTree, RunTreeConfig, isRunTree } from "./run_trees.js";
import { KVMap } from "./schemas.js";

export type TraceableFunction<I, O> = (
  rawInput: I,
  parentRun: RunTree | { root: RunTree } | null
) => Promise<O>;

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
  let boundParentRunTree: RunTree | undefined;
  const traceableFunc = async (
    ...rawInputs: Inputs | [RunTree, ...Inputs]
  ): Promise<Output> => {
    let parentRunTree: RunTree | undefined = boundParentRunTree;
    let wrappedFunctionInputs: Inputs;

    if (isRunTree(rawInputs[0])) {
      [parentRunTree, ...wrappedFunctionInputs] = rawInputs as [
        RunTree,
        ...Inputs
      ];
    } else {
      wrappedFunctionInputs = rawInputs as Inputs;
    }
    if (parentRunTree == null) {
      return wrappedFunc(...wrappedFunctionInputs);
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

    const ensuredConfig = { name: "traced_function", config };

    const currentRunTree: RunTree =
      "root" in parentRunTree
        ? (parentRunTree.root as RunTree)
        : await parentRunTree.createChild({
            ...ensuredConfig,
            inputs,
          });

    if ("root" in parentRunTree) {
      Object.assign(currentRunTree, { ...ensuredConfig, inputs });
    }

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
  traceableFunc.setParentRunTree = (parent: RunTree) => {
    boundParentRunTree = parent;
  };
  Object.defineProperty(wrappedFunc, "langsmith:traceable", {
    value: config,
  });
  return traceableFunc;
}
