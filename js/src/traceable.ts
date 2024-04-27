import { AsyncLocalStorage } from "async_hooks";

import {
  RunTree,
  RunTreeConfig,
  RunnableConfigLike,
  isRunTree,
  isRunnableConfigLike,
} from "./run_trees.js";
import { KVMap } from "./schemas.js";
import { getEnvironmentVariable } from "./utils/env.js";

const asyncLocalStorage = new AsyncLocalStorage<RunTree | undefined>();

export type RunTreeLike = RunTree;

type WrapArgReturnPair<Pair> = Pair extends [
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  infer Args extends any[],
  infer Return
]
  ? {
      (...args: Args): Promise<Return>;
      (...args: [runTree: RunTreeLike, ...rest: Args]): Promise<Return>;
      (...args: [config: RunnableConfigLike, ...rest: Args]): Promise<Return>;
    }
  : never;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UnionToIntersection<U> = (U extends any ? (x: U) => void : never) extends (
  x: infer I
) => void
  ? I
  : never;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type TraceableFunction<Func extends (...args: any[]) => any> =
  // function overloads are represented as intersections rather than unions
  // matches the behavior introduced in https://github.com/microsoft/TypeScript/pull/54448
  Func extends {
    (...args: infer A1): infer R1;
    (...args: infer A2): infer R2;
    (...args: infer A3): infer R3;
    (...args: infer A4): infer R4;
    (...args: infer A5): infer R5;
  }
    ? UnionToIntersection<
        WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3] | [A4, R4] | [A5, R5]>
      >
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
        (...args: infer A3): infer R3;
        (...args: infer A4): infer R4;
      }
    ? UnionToIntersection<
        WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3] | [A4, R4]>
      >
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
        (...args: infer A3): infer R3;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3]>>
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1] | [A2, R2]>>
    : Func extends {
        (...args: infer A1): infer R1;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1]>>
    : never;

const isAsyncIterable = (x: unknown): x is AsyncIterable<unknown> =>
  x != null &&
  typeof x === "object" &&
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  typeof (x as any)[Symbol.asyncIterator] === "function";

const getTracingRunTree = (runTree: RunTree): RunTree | undefined => {
  const tracingEnabled =
    getEnvironmentVariable("LANGSMITH_TRACING_V2") === "true" ||
    getEnvironmentVariable("LANGCHAIN_TRACING_V2") === "true";
  if (!tracingEnabled) {
    return undefined;
  }
  return runTree;
};

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
  config?: Partial<RunTreeConfig> & {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    aggregator?: (args: any[]) => any;
  }
) {
  type Inputs = Parameters<Func>;
  type Output = ReturnType<Func>;
  const { aggregator, ...runTreeConfig } = config ?? {};

  const traceableFunc = async (
    ...args: Inputs | [RunTreeLike, ...Inputs] | [RunnableConfigLike, ...Inputs]
  ): Promise<Output> => {
    let currentRunTree: RunTree | undefined;
    let rawInputs: Inputs;

    const ensuredConfig: RunTreeConfig = {
      name: wrappedFunc.name || "<lambda>",
      ...runTreeConfig,
    };

    const previousRunTree = asyncLocalStorage.getStore();
    if (isRunTree(args[0])) {
      currentRunTree = args[0];
      rawInputs = args.slice(1) as Inputs;
    } else if (isRunnableConfigLike(args[0])) {
      currentRunTree = RunTree.fromRunnableConfig(args[0], ensuredConfig);
      rawInputs = args.slice(1) as Inputs;
    } else if (previousRunTree !== undefined) {
      currentRunTree = await previousRunTree.createChild(ensuredConfig);
      rawInputs = args as Inputs;
    } else {
      currentRunTree = new RunTree(ensuredConfig);
      rawInputs = args as Inputs;
    }

    currentRunTree = getTracingRunTree(currentRunTree);
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

    if (currentRunTree) {
      currentRunTree.inputs = inputs;
    }

    const initialOutputs = currentRunTree?.outputs;
    const initialError = currentRunTree?.error;
    await currentRunTree?.postRun();

    return new Promise((resolve, reject) => {
      void asyncLocalStorage.run(currentRunTree, async () => {
        try {
          const onEnd = config?.on_end;
          if (onEnd) {
            onEnd(currentRunTree);
          }
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
              let finalOutputs;
              if (aggregator !== undefined) {
                try {
                  finalOutputs = await aggregator(chunks);
                } catch (e) {
                  console.error(`[ERROR]: LangSmith aggregation failed: `, e);
                  finalOutputs = chunks;
                }
              } else {
                finalOutputs = chunks;
              }
              if (
                typeof finalOutputs === "object" &&
                !Array.isArray(finalOutputs)
              ) {
                await currentRunTree?.end(finalOutputs);
              } else {
                await currentRunTree?.end({ outputs: finalOutputs });
              }
              await currentRunTree?.patchRun();
            }
            return resolve(wrapOutputForTracing() as Output);
          } else {
            const outputs: KVMap = isKVMap(rawOutput)
              ? rawOutput
              : { outputs: rawOutput };

            if (initialOutputs === currentRunTree?.outputs) {
              await currentRunTree?.end(outputs);
            } else {
              if (currentRunTree !== undefined) {
                currentRunTree.end_time = Date.now();
              }
            }

            await currentRunTree?.patchRun();
            return resolve(rawOutput);
          }
        } catch (error) {
          if (initialError === currentRunTree?.error) {
            await currentRunTree?.end(initialOutputs, String(error));
          } else {
            if (currentRunTree !== undefined) {
              currentRunTree.end_time = Date.now();
            }
          }

          await currentRunTree?.patchRun();
          reject(error);
        }
      });
    });
  };

  Object.defineProperty(traceableFunc, "langsmith:traceable", {
    value: runTreeConfig,
  });

  return traceableFunc as TraceableFunction<Func>;
}

/**
 * Return the current run tree from within a traceable-wrapped function.
 * Will throw an error if called outside of a traceable function.
 *
 * @returns The run tree for the given context.
 */
export function getCurrentRunTree(): RunTree {
  const runTree = asyncLocalStorage.getStore();
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

export function wrapFunctionAndEnsureTraceable<
  Func extends (...args: any[]) => any
>(target: Func, options: Partial<RunTreeConfig>, name = "target") {
  if (typeof target === "function") {
    return traceable<Func>(target, {
      ...options,
      name,
    });
  }
  throw new Error("Target must be runnable function");
}
