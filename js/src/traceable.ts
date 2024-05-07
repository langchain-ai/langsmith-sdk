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

function isPromiseMethod(
  x: string | symbol
): x is "then" | "catch" | "finally" {
  if (x === "then" || x === "catch" || x === "finally") {
    return true;
  }
  return false;
}

const asyncLocalStorage = new AsyncLocalStorage<RunTree | undefined>();

export const ROOT = Symbol("langsmith:traceable:root");

export type RunTreeLike = RunTree;

type SmartPromise<T> = T extends AsyncGenerator
  ? T
  : T extends Promise<unknown>
  ? T
  : Promise<T>;

type WrapArgReturnPair<Pair> = Pair extends [
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  infer Args extends any[],
  infer Return
]
  ? Args extends [RunTreeLike, ...infer RestArgs]
    ? {
        (
          runTree: RunTreeLike | typeof ROOT,
          ...args: RestArgs
        ): SmartPromise<Return>;
        (config: RunnableConfigLike, ...args: RestArgs): SmartPromise<Return>;
      }
    : {
        (...args: Args): SmartPromise<Return>;
        (runTree: RunTreeLike, ...rest: Args): SmartPromise<Return>;
        (config: RunnableConfigLike, ...args: Args): SmartPromise<Return>;
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

const GeneratorFunction = function* () {}.constructor;

const isIteratorLike = (x: unknown): x is Iterator<unknown> =>
  x != null &&
  typeof x === "object" &&
  "next" in x &&
  typeof x.next === "function";

const isGenerator = (x: unknown): x is Generator =>
  // eslint-disable-next-line no-instanceof/no-instanceof
  x != null && typeof x === "function" && x instanceof GeneratorFunction;

const isThenable = (x: unknown): x is Promise<unknown> =>
  x != null &&
  typeof x === "object" &&
  "then" in x &&
  typeof x.then === "function";

const isReadableStream = (x: unknown): x is ReadableStream =>
  x != null &&
  typeof x === "object" &&
  "getReader" in x &&
  typeof x.getReader === "function";

const tracingIsEnabled = (tracingEnabled?: boolean): boolean => {
  if (tracingEnabled !== undefined) {
    return tracingEnabled;
  }
  const envVars = [
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING",
  ];
  return Boolean(
    envVars.find((envVar) => getEnvironmentVariable(envVar) === "true")
  );
};

const handleRunInputs = (rawInputs: unknown[]): KVMap => {
  const firstInput = rawInputs[0];

  if (firstInput == null) {
    return {};
  }

  if (rawInputs.length > 1) {
    return { args: rawInputs };
  }
  if (isKVMap(firstInput)) {
    return firstInput;
  }

  return { input: firstInput };
};

const handleRunOutputs = (rawOutputs: unknown): KVMap => {
  if (isKVMap(rawOutputs)) {
    return rawOutputs;
  }
  return { outputs: rawOutputs };
};

const getTracingRunTree = (
  runTree: RunTree,
  inputs: unknown[]
): RunTree | undefined => {
  const tracingEnabled_ = tracingIsEnabled(runTree.tracingEnabled);
  if (!tracingEnabled_) {
    return undefined;
  }

  runTree.inputs = handleRunInputs(inputs);
  return runTree;
};

// idea: store the state of the promise outside
// but only when the promise is "consumed"
const getSerializablePromise = <T = unknown>(arg: Promise<T>) => {
  const proxyState: {
    current: ["resolve", unknown] | ["reject", unknown] | undefined;
  } = { current: undefined };

  const promiseProxy = new Proxy(arg, {
    get(target, prop, receiver) {
      if (prop === "then") {
        const boundThen = arg[prop].bind(arg);
        return (
          resolve: (value: unknown) => unknown,
          reject: (error: unknown) => unknown = (x) => {
            throw x;
          }
        ) => {
          return boundThen(
            (value) => {
              proxyState.current = ["resolve", value];
              return resolve(value);
            },
            (error) => {
              proxyState.current = ["reject", error];
              return reject(error);
            }
          );
        };
      }

      if (prop === "catch") {
        const boundCatch = arg[prop].bind(arg);
        return (reject: (error: unknown) => unknown) => {
          return boundCatch((error) => {
            proxyState.current = ["reject", error];
            return reject(error);
          });
        };
      }

      if (prop === "toJSON") {
        return () => {
          if (!proxyState.current) return undefined;
          const [type, value] = proxyState.current ?? [];
          if (type === "resolve") return value;
          return { error: value };
        };
      }

      return Reflect.get(target, prop, receiver);
    },
  });

  return promiseProxy as Promise<T> & { toJSON: () => unknown };
};

const convertSerializableArg = (arg: unknown): unknown => {
  if (isReadableStream(arg)) {
    const proxyState: unknown[] = [];
    const transform = new TransformStream({
      start: () => void 0,
      transform: (chunk, controller) => {
        proxyState.push(chunk);
        controller.enqueue(chunk);
      },
      flush: () => void 0,
    });

    const pipeThrough = arg.pipeThrough(transform);
    Object.assign(pipeThrough, { toJSON: () => proxyState });
    return pipeThrough;
  }

  if (isAsyncIterable(arg)) {
    const proxyState: {
      current: (Promise<IteratorResult<unknown>> & {
        toJSON: () => unknown;
      })[];
    } = { current: [] };

    return new Proxy(arg, {
      get(target, prop, receiver) {
        if (prop === Symbol.asyncIterator) {
          return () => {
            const boundIterator = arg[Symbol.asyncIterator].bind(arg);
            const iterator = boundIterator();

            return new Proxy(iterator, {
              get(target, prop, receiver) {
                if (prop === "next" || prop === "return" || prop === "throw") {
                  const bound = iterator.next.bind(iterator);

                  return (
                    ...args: Parameters<
                      Exclude<
                        AsyncIterator<unknown>["next" | "return" | "throw"],
                        undefined
                      >
                    >
                  ) => {
                    // @ts-expect-error TS cannot infer the argument types for the bound function
                    const wrapped = getSerializablePromise(bound(...args));
                    proxyState.current.push(wrapped);
                    return wrapped;
                  };
                }

                if (prop === "return" || prop === "throw") {
                  return iterator.next.bind(iterator);
                }

                return Reflect.get(target, prop, receiver);
              },
            });
          };
        }

        if (prop === "toJSON") {
          return () => {
            const onlyNexts = proxyState.current;
            const serialized = onlyNexts.map(
              (next) => next.toJSON() as IteratorResult<unknown> | undefined
            );

            const chunks = serialized.reduce<unknown[]>((memo, next) => {
              if (next?.value) memo.push(next.value);
              return memo;
            }, []);

            return chunks;
          };
        }

        return Reflect.get(target, prop, receiver);
      },
    });
  }

  if (!Array.isArray(arg) && isIteratorLike(arg)) {
    const proxyState: Array<IteratorResult<unknown>> = [];

    return new Proxy(arg, {
      get(target, prop, receiver) {
        if (prop === "next" || prop === "return" || prop === "throw") {
          const bound = arg[prop]?.bind(arg);
          return (
            ...args: Parameters<
              Exclude<Iterator<unknown>["next" | "return" | "throw"], undefined>
            >
          ) => {
            // @ts-expect-error TS cannot infer the argument types for the bound function
            const next = bound?.(...args);
            if (next != null) proxyState.push(next);
            return next;
          };
        }

        if (prop === "toJSON") {
          return () => {
            const chunks = proxyState.reduce<unknown[]>((memo, next) => {
              if (next.value) memo.push(next.value);
              return memo;
            }, []);

            return chunks;
          };
        }

        return Reflect.get(target, prop, receiver);
      },
    });
  }

  if (isThenable(arg)) {
    return getSerializablePromise(arg);
  }

  return arg;
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
    argsConfigPath?: [number] | [number, string];
  }
) {
  type Inputs = Parameters<Func>;
  const { aggregator, argsConfigPath, ...runTreeConfig } = config ?? {};

  const traceableFunc = (
    ...args: Inputs | [RunTreeLike, ...Inputs] | [RunnableConfigLike, ...Inputs]
  ) => {
    let ensuredConfig: RunTreeConfig;
    try {
      let runtimeConfig: Partial<RunTreeConfig> | undefined;
      if (argsConfigPath) {
        const [index, path] = argsConfigPath;
        if (index === args.length - 1 && !path) {
          runtimeConfig = args.pop() as Partial<RunTreeConfig>;
        } else if (
          index <= args.length &&
          typeof args[index] === "object" &&
          args[index] !== null
        ) {
          if (path) {
            const { [path]: extracted, ...rest } = args[index];
            runtimeConfig = extracted as Partial<RunTreeConfig>;
            args[index] = rest;
          } else {
            runtimeConfig = args[index] as Partial<RunTreeConfig>;
            args.splice(index, 1);
          }
        }
      }

      ensuredConfig = {
        name: wrappedFunc.name || "<lambda>",
        ...runTreeConfig,
        ...runtimeConfig,
        tags: [
          ...new Set([
            ...(runTreeConfig?.tags ?? []),
            ...(runtimeConfig?.tags ?? []),
          ]),
        ],
        metadata: {
          ...runTreeConfig?.metadata,
          ...runtimeConfig?.metadata,
        },
      };
    } catch (err) {
      console.warn(
        `Failed to extract runtime config from args for ${
          runTreeConfig?.name ?? wrappedFunc.name
        }`,
        err
      );
      ensuredConfig = {
        name: wrappedFunc.name || "<lambda>",
        ...runTreeConfig,
      };
    }

    // TODO: deal with possible nested promises and async iterables
    const processedArgs = args as unknown as Inputs;
    for (let i = 0; i < processedArgs.length; i++) {
      processedArgs[i] = convertSerializableArg(processedArgs[i]);
    }

    const [currentRunTree, rawInputs] = ((): [RunTree | undefined, Inputs] => {
      const [firstArg, ...restArgs] = processedArgs;

      // used for handoff between LangChain.JS and traceable functions
      if (isRunnableConfigLike(firstArg)) {
        return [
          getTracingRunTree(
            RunTree.fromRunnableConfig(firstArg, ensuredConfig),
            restArgs
          ),
          restArgs as Inputs,
        ];
      }

      // legacy CallbackManagerRunTree used in runOnDataset
      // override ALS and do not pass-through the run tree
      if (
        isRunTree(firstArg) &&
        "callbackManager" in firstArg &&
        firstArg.callbackManager != null
      ) {
        return [firstArg, restArgs as Inputs];
      }

      // when ALS is unreliable, users can manually
      // pass in the run tree
      if (firstArg === ROOT || isRunTree(firstArg)) {
        const currentRunTree = getTracingRunTree(
          firstArg === ROOT
            ? new RunTree(ensuredConfig)
            : firstArg.createChild(ensuredConfig),
          restArgs
        );

        return [currentRunTree, [currentRunTree, ...restArgs] as Inputs];
      }

      // Node.JS uses AsyncLocalStorage (ALS) and AsyncResource
      // to allow storing context
      const prevRunFromStore = asyncLocalStorage.getStore();
      if (prevRunFromStore) {
        return [
          getTracingRunTree(
            prevRunFromStore.createChild(ensuredConfig),
            processedArgs
          ),
          processedArgs as Inputs,
        ];
      }

      const currentRunTree = getTracingRunTree(
        new RunTree(ensuredConfig),
        processedArgs
      );
      return [currentRunTree, processedArgs as Inputs];
    })();

    return asyncLocalStorage.run(currentRunTree, () => {
      const postRunPromise = currentRunTree?.postRun();

      async function handleChunks(chunks: unknown[]) {
        if (aggregator !== undefined) {
          try {
            return await aggregator(chunks);
          } catch (e) {
            console.error(`[ERROR]: LangSmith aggregation failed: `, e);
          }
        }

        return chunks;
      }

      async function* wrapAsyncGeneratorForTracing(
        iterable: AsyncIterable<unknown>,
        snapshot: ReturnType<typeof AsyncLocalStorage.snapshot> | undefined
      ) {
        let finished = false;
        const chunks: unknown[] = [];
        try {
          const iterator = iterable[Symbol.asyncIterator]();
          while (true) {
            const { value, done } = await (snapshot
              ? snapshot(() => iterator.next())
              : iterator.next());
            if (done) {
              finished = true;
              break;
            }
            chunks.push(value);
            yield value;
          }
        } catch (e) {
          await currentRunTree?.end(undefined, String(e));
          throw e;
        } finally {
          if (!finished) await currentRunTree?.end(undefined, "Cancelled");
          await currentRunTree?.end(
            handleRunOutputs(await handleChunks(chunks))
          );
          await handleEnd();
        }
      }

      async function handleEnd() {
        const onEnd = config?.on_end;
        if (onEnd) {
          if (!currentRunTree) {
            console.warn(
              "Can not call 'on_end' if currentRunTree is undefined"
            );
          } else {
            onEnd(currentRunTree);
          }
        }
        await postRunPromise;
        await currentRunTree?.patchRun();
      }

      function gatherAll(iterator: Iterator<unknown>) {
        const chunks: IteratorResult<unknown>[] = [];
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const next = iterator.next();
          chunks.push(next);
          if (next.done) break;
        }

        return chunks;
      }

      let returnValue: unknown;
      try {
        returnValue = wrappedFunc(...rawInputs);
      } catch (err: unknown) {
        returnValue = Promise.reject(err);
      }

      if (isAsyncIterable(returnValue)) {
        const snapshot = AsyncLocalStorage.snapshot();
        return wrapAsyncGeneratorForTracing(returnValue, snapshot);
      }

      const tracedPromise = new Promise<unknown>((resolve, reject) => {
        Promise.resolve(returnValue)
          .then(
            async (rawOutput) => {
              if (isAsyncIterable(rawOutput)) {
                const snapshot = AsyncLocalStorage.snapshot();
                return resolve(
                  wrapAsyncGeneratorForTracing(rawOutput, snapshot)
                );
              }

              if (isGenerator(wrappedFunc) && isIteratorLike(rawOutput)) {
                const chunks = gatherAll(rawOutput);

                await currentRunTree?.end(
                  handleRunOutputs(
                    await handleChunks(
                      chunks.reduce<unknown[]>((memo, { value, done }) => {
                        if (!done || typeof value !== "undefined") {
                          memo.push(value);
                        }

                        return memo;
                      }, [])
                    )
                  )
                );
                await handleEnd();

                return (function* () {
                  for (const ret of chunks) {
                    if (ret.done) return ret.value;
                    yield ret.value;
                  }
                })();
              }

              try {
                await currentRunTree?.end(handleRunOutputs(rawOutput));
                await handleEnd();
              } finally {
                // eslint-disable-next-line no-unsafe-finally
                return rawOutput;
              }
            },
            async (error: unknown) => {
              await currentRunTree?.end(undefined, String(error));
              await handleEnd();
              throw error;
            }
          )
          .then(resolve, reject);
      });

      if (typeof returnValue !== "object" || returnValue === null) {
        return tracedPromise;
      }

      return new Proxy(returnValue, {
        get(target, prop, receiver) {
          if (isPromiseMethod(prop)) {
            return tracedPromise[prop].bind(tracedPromise);
          }
          return Reflect.get(target, prop, receiver);
        },
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
  if (typeof x !== "object" || x == null) {
    return false;
  }

  const prototype = Object.getPrototypeOf(x);
  return (
    (prototype === null ||
      prototype === Object.prototype ||
      Object.getPrototypeOf(prototype) === null) &&
    !(Symbol.toStringTag in x) &&
    !(Symbol.iterator in x)
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
