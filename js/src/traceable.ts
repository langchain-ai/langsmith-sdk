import { AsyncLocalStorage } from "async_hooks";

import { RunTree, RunTreeConfig, isRunTree } from "./run_trees.js";
import { KVMap } from "./schemas.js";

const asyncLocalStorage = new AsyncLocalStorage<RunTree>();

export type RunTreeLike = RunTree;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type TraceableFunction<Func extends (...args: any[]) => any> = (
  ...rawInputs: Parameters<Func>
) => Promise<ReturnType<Func>>;

const isAsyncIterable = (x: unknown): x is AsyncIterable<unknown> =>
  x != null &&
  typeof x === "object" &&
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  typeof (x as any)[Symbol.asyncIterator] === "function";

/**
 * Higher-order function that takes function as input and returns a
 * "TraceableFunction" - a wrapped version of the input that
 * automatically handles tracing. If the returned traceable function calls any
 * traceable functions, those are automatically traced as well.
 *
 * The returned TraceableFunction can accept a run tree or run tree config as
 * its first argument. If omitted, it will default to the caller's run tree,
 * or will be treated as a root run.
 *
 * @param wrappedFunc Targeted function to be traced
 * @param config Additional metadata such as name, tags or providing
 *     a custom LangSmith client instance
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function traceable<Func extends (...args: any[]) => any>(
  wrappedFunc: Func,
  config?: Partial<RunTreeConfig>
) {
  type Inputs = Parameters<Func>;
  type Output = ReturnType<Func>;

  const traceableFunc: TraceableFunction<Func> = async (
    ...args: Inputs | [RunTreeLike, ...Inputs]
  ): Promise<Output> => {
    let currentRunTree: RunTree;
    let rawInputs: Inputs;

    const ensuredConfig: RunTreeConfig = {
      name: wrappedFunc.name || "<lambda>",
      ...config,
    };

    const previousRunTree = asyncLocalStorage.getStore();
    if (isRunTree(args[0])) {
      currentRunTree = args[0];
      rawInputs = args.slice(1) as Inputs;
    } else if (previousRunTree !== undefined) {
      currentRunTree = await previousRunTree.createChild(ensuredConfig);
      rawInputs = args as Inputs;
    } else {
      currentRunTree = new RunTree(ensuredConfig);
      rawInputs = args as Inputs;
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
    await currentRunTree.postRun();

    return new Promise((resolve, reject) => {
      void asyncLocalStorage.run(currentRunTree, async () => {
        try {
          const rawOutput = await wrappedFunc(...rawInputs);
          if (isAsyncIterable(rawOutput)) {
            // eslint-disable-next-line no-inner-declarations
            async function* wrapOutputForTracing() {
              const chunks: unknown[] = [];
              // TypeScript thinks this is unsafe
              for await (const chunk of rawOutput as AsyncIterable<unknown>) {
                chunks.push(chunk);
                yield chunk;
              }
              await currentRunTree.end({ outputs: chunks });
              await currentRunTree.patchRun();
            }
            return resolve(wrapOutputForTracing() as Output);
          } else {
            const outputs: KVMap = isKVMap(rawOutput)
              ? rawOutput
              : { outputs: rawOutput };

            if (initialOutputs === currentRunTree.outputs) {
              await currentRunTree.end(outputs);
            } else {
              currentRunTree.end_time = Date.now();
            }

            await currentRunTree.patchRun();
            return resolve(rawOutput);
          }
        } catch (error) {
          if (initialError === currentRunTree.error) {
            await currentRunTree.end(initialOutputs, String(error));
          } else {
            currentRunTree.end_time = Date.now();
          }

          await currentRunTree.patchRun();
          reject(error);
        }
      });
    });
  };

  Object.defineProperty(wrappedFunc, "langsmith:traceable", {
    value: config,
  });
  return traceableFunc;
}

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any> {
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
