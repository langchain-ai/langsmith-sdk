import { RunTree, RunTreeConfig } from "./run_trees.js";
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

export const traceable = (params: RunTreeConfig) => {
  return <I, O>(func: (rawInput: I, parentRun: RunTree | null) => O) => {
    async function wrappedFunc(
      rawInput: I,
      parentRun: RunTree | { root: RunTree } | null
    ) {
      if (parentRun == null) {
        return await func(rawInput, parentRun);
      }

      const inputs: KVMap =
        typeof rawInput === "object" && rawInput != null
          ? rawInput
          : { input: rawInput };

      const currentRun: RunTree =
        "root" in parentRun
          ? parentRun.root
          : await parentRun.createChild({
              ...params,
              inputs,
            });

      if ("root" in parentRun) {
        Object.assign(currentRun, { ...params, inputs });
      }

      const initialOutputs = currentRun.outputs;
      const initialError = currentRun.error;

      try {
        const rawOutput = await func(rawInput, currentRun);
        const outputs: KVMap =
          typeof rawOutput === "object" &&
          rawOutput != null &&
          !Array.isArray(rawOutput)
            ? rawOutput
            : { outputs: rawOutput };

        if (initialOutputs === currentRun.outputs) {
          await currentRun.end(outputs);
        } else {
          currentRun.end_time = Date.now();
        }

        return rawOutput;
      } catch (error) {
        if (initialError === currentRun.error) {
          await currentRun.end(initialOutputs, String(error));
        } else {
          currentRun.end_time = Date.now();
        }

        throw error;
      } finally {
        await currentRun.postRun();
      }
    }

    Object.defineProperty(wrappedFunc, "langsmith:traceable", {
      value: params,
    });

    return wrappedFunc;
  };
};
