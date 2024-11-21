import { AsyncLocalStorage } from "node:async_hooks";

import {
  RunTree,
  RunTreeConfig,
  RunnableConfigLike,
  isRunTree,
  isRunnableConfigLike,
} from "./run_trees.js";
import { Attachments, InvocationParamsSchema, KVMap } from "./schemas.js";
import { isTracingEnabled } from "./env.js";
import {
  ROOT,
  AsyncLocalStorageProviderSingleton,
} from "./singletons/traceable.js";
import { _LC_CONTEXT_VARIABLES_KEY } from "./singletons/constants.js";
import { TraceableFunction } from "./singletons/types.js";
import {
  isKVMap,
  isReadableStream,
  isAsyncIterable,
  isIteratorLike,
  isThenable,
  isGenerator,
  isPromiseMethod,
} from "./utils/asserts.js";

AsyncLocalStorageProviderSingleton.initializeGlobalInstance(
  new AsyncLocalStorage<RunTree | undefined>()
);

const runInputsToMap = (rawInputs: unknown[]) => {
  const firstInput = rawInputs[0];
  let inputs: KVMap;

  if (firstInput == null) {
    inputs = {};
  } else if (rawInputs.length > 1) {
    inputs = { args: rawInputs };
  } else if (isKVMap(firstInput)) {
    inputs = firstInput;
  } else {
    inputs = { input: firstInput };
  }
  return inputs;
};

const handleRunInputs = (
  inputs: KVMap,
  processInputs: (inputs: Readonly<KVMap>) => KVMap
): KVMap => {
  try {
    return processInputs(inputs);
  } catch (e) {
    console.error(
      "Error occurred during processInputs. Sending raw inputs:",
      e
    );
    return inputs;
  }
};

const handleRunOutputs = (
  rawOutputs: unknown,
  processOutputs: (outputs: Readonly<KVMap>) => KVMap
): KVMap => {
  let outputs: KVMap;

  if (isKVMap(rawOutputs)) {
    outputs = rawOutputs;
  } else {
    outputs = { outputs: rawOutputs };
  }

  try {
    return processOutputs(outputs);
  } catch (e) {
    console.error(
      "Error occurred during processOutputs. Sending raw outputs:",
      e
    );
    return outputs;
  }
};
const handleRunAttachments = (
  rawInputs: unknown[],
  extractAttachments?: (
    ...args: unknown[]
  ) => [Attachments | undefined, unknown[]]
): [Attachments | undefined, unknown[]] => {
  if (!extractAttachments) {
    return [undefined, rawInputs];
  }

  try {
    const [attachments, remainingArgs] = extractAttachments(...rawInputs);
    return [attachments, remainingArgs];
  } catch (e) {
    console.error("Error occurred during extractAttachments:", e);
    return [undefined, rawInputs];
  }
};

const getTracingRunTree = <Args extends unknown[]>(
  runTree: RunTree,
  inputs: Args,
  getInvocationParams:
    | ((...args: Args) => InvocationParamsSchema | undefined)
    | undefined,
  processInputs: (inputs: Readonly<KVMap>) => KVMap,
  extractAttachments:
    | ((...args: Args) => [Attachments | undefined, KVMap])
    | undefined
): RunTree | undefined => {
  if (!isTracingEnabled(runTree.tracingEnabled)) {
    return undefined;
  }

  const [attached, args] = handleRunAttachments(
    inputs,
    extractAttachments as
      | ((...args: unknown[]) => [Attachments | undefined, unknown[]])
      | undefined
  );
  runTree.attachments = attached;
  runTree.inputs = handleRunInputs(args, processInputs);

  const invocationParams = getInvocationParams?.(...inputs);
  if (invocationParams != null) {
    runTree.extra ??= {};
    runTree.extra.metadata = {
      ...invocationParams,
      ...runTree.extra.metadata,
    };
  }

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
    __finalTracedIteratorKey?: string;

    /**
     * Extract attachments from args and return remaining args.
     * @param args Arguments of the traced function
     * @returns Tuple of [Attachments, remaining args]
     */
    extractAttachments?: (
      ...args: Parameters<Func>
    ) => [Attachments | undefined, KVMap];

    /**
     * Extract invocation parameters from the arguments of the traced function.
     * This is useful for LangSmith to properly track common metadata like
     * provider, model name and temperature.
     *
     * @param args Arguments of the traced function
     * @returns Key-value map of the invocation parameters, which will be merged with the existing metadata
     */
    getInvocationParams?: (
      ...args: Parameters<Func>
    ) => InvocationParamsSchema | undefined;

    /**
     * Apply transformations to the inputs before logging.
     * This function should NOT mutate the inputs.
     * `processInputs` is not inherited by nested traceable functions.
     *
     * @param inputs Key-value map of the function inputs.
     * @returns Transformed key-value map
     */
    processInputs?: (inputs: Readonly<KVMap>) => KVMap;

    /**
     * Apply transformations to the outputs before logging.
     * This function should NOT mutate the outputs.
     * `processOutputs` is not inherited by nested traceable functions.
     *
     * @param outputs Key-value map of the function outputs
     * @returns Transformed key-value map
     */
    processOutputs?: (outputs: Readonly<KVMap>) => KVMap;
  }
) {
  type Inputs = Parameters<Func>;
  const {
    aggregator,
    argsConfigPath,
    __finalTracedIteratorKey,
    processInputs,
    processOutputs,
    extractAttachments,
    ...runTreeConfig
  } = config ?? {};

  const processInputsFn = processInputs ?? ((x) => x);
  const processOutputsFn = processOutputs ?? ((x) => x);
  const extractAttachmentsFn =
    extractAttachments ?? ((...x) => [undefined, runInputsToMap(x)]);

  const traceableFunc = (
    ...args: Inputs | [RunTree, ...Inputs] | [RunnableConfigLike, ...Inputs]
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

    const asyncLocalStorage = AsyncLocalStorageProviderSingleton.getInstance();

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
            restArgs as Inputs,
            config?.getInvocationParams,
            processInputsFn,
            extractAttachmentsFn
          ),
          restArgs as Inputs,
        ];
      }

      // deprecated: legacy CallbackManagerRunTree used in runOnDataset
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
          restArgs as Inputs,
          config?.getInvocationParams,
          processInputsFn,
          extractAttachmentsFn
        );

        return [currentRunTree, [currentRunTree, ...restArgs] as Inputs];
      }

      // Node.JS uses AsyncLocalStorage (ALS) and AsyncResource
      // to allow storing context
      const prevRunFromStore = asyncLocalStorage.getStore();
      if (isRunTree(prevRunFromStore)) {
        return [
          getTracingRunTree(
            prevRunFromStore.createChild(ensuredConfig),
            processedArgs,
            config?.getInvocationParams,
            processInputsFn,
            extractAttachmentsFn
          ),
          processedArgs as Inputs,
        ];
      }

      const currentRunTree = getTracingRunTree(
        new RunTree(ensuredConfig),
        processedArgs,
        config?.getInvocationParams,
        processInputsFn,
        extractAttachmentsFn
      );
      // If a context var is set by LangChain outside of a traceable,
      // it will be an object with a single property and we should copy
      // context vars over into the new run tree.
      if (
        prevRunFromStore !== undefined &&
        _LC_CONTEXT_VARIABLES_KEY in prevRunFromStore
      ) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (currentRunTree as any)[_LC_CONTEXT_VARIABLES_KEY] =
          prevRunFromStore[_LC_CONTEXT_VARIABLES_KEY];
      }
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

      function tapReadableStreamForTracing(
        stream: ReadableStream<unknown>,
        snapshot: ReturnType<typeof AsyncLocalStorage.snapshot> | undefined
      ) {
        const reader = stream.getReader();
        let finished = false;
        const chunks: unknown[] = [];

        const tappedStream = new ReadableStream({
          async start(controller) {
            // eslint-disable-next-line no-constant-condition
            while (true) {
              const result = await (snapshot
                ? snapshot(() => reader.read())
                : reader.read());
              if (result.done) {
                finished = true;
                await currentRunTree?.end(
                  handleRunOutputs(await handleChunks(chunks), processOutputsFn)
                );
                await handleEnd();
                controller.close();
                break;
              }
              chunks.push(result.value);
              controller.enqueue(result.value);
            }
          },
          async cancel(reason) {
            if (!finished) await currentRunTree?.end(undefined, "Cancelled");
            await currentRunTree?.end(
              handleRunOutputs(await handleChunks(chunks), processOutputsFn)
            );
            await handleEnd();
            return reader.cancel(reason);
          },
        });

        return tappedStream;
      }

      async function* wrapAsyncIteratorForTracing(
        iterator: AsyncIterator<unknown, unknown, undefined>,
        snapshot: ReturnType<typeof AsyncLocalStorage.snapshot> | undefined
      ) {
        let finished = false;
        const chunks: unknown[] = [];
        try {
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
            handleRunOutputs(await handleChunks(chunks), processOutputsFn)
          );
          await handleEnd();
        }
      }

      function wrapAsyncGeneratorForTracing(
        iterable: AsyncIterable<unknown>,
        snapshot: ReturnType<typeof AsyncLocalStorage.snapshot> | undefined
      ) {
        if (isReadableStream(iterable)) {
          return tapReadableStreamForTracing(iterable, snapshot);
        }
        const iterator = iterable[Symbol.asyncIterator]();
        const wrappedIterator = wrapAsyncIteratorForTracing(iterator, snapshot);
        iterable[Symbol.asyncIterator] = () => wrappedIterator;
        return iterable;
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

      if (
        !Array.isArray(returnValue) &&
        typeof returnValue === "object" &&
        returnValue != null &&
        __finalTracedIteratorKey !== undefined &&
        isAsyncIterable(
          (returnValue as Record<string, any>)[__finalTracedIteratorKey]
        )
      ) {
        const snapshot = AsyncLocalStorage.snapshot();
        return {
          ...returnValue,
          [__finalTracedIteratorKey]: wrapAsyncGeneratorForTracing(
            (returnValue as Record<string, any>)[__finalTracedIteratorKey],
            snapshot
          ),
        };
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

              if (
                !Array.isArray(rawOutput) &&
                typeof rawOutput === "object" &&
                rawOutput != null &&
                __finalTracedIteratorKey !== undefined &&
                isAsyncIterable(
                  (rawOutput as Record<string, any>)[__finalTracedIteratorKey]
                )
              ) {
                const snapshot = AsyncLocalStorage.snapshot();
                return {
                  ...rawOutput,
                  [__finalTracedIteratorKey]: wrapAsyncGeneratorForTracing(
                    (rawOutput as Record<string, any>)[
                      __finalTracedIteratorKey
                    ],
                    snapshot
                  ),
                };
              }

              if (isGenerator(wrappedFunc) && isIteratorLike(rawOutput)) {
                const chunks = gatherAll(rawOutput);

                try {
                  await currentRunTree?.end(
                    handleRunOutputs(
                      await handleChunks(
                        chunks.reduce<unknown[]>((memo, { value, done }) => {
                          if (!done || typeof value !== "undefined") {
                            memo.push(value);
                          }

                          return memo;
                        }, [])
                      ),
                      processOutputsFn
                    )
                  );
                  await handleEnd();
                } catch (e) {
                  console.error("Error occurred during handleEnd:", e);
                }

                return (function* () {
                  for (const ret of chunks) {
                    if (ret.done) return ret.value;
                    yield ret.value;
                  }
                })();
              }

              try {
                await currentRunTree?.end(
                  handleRunOutputs(rawOutput, processOutputsFn)
                );
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

export {
  getCurrentRunTree,
  isTraceableFunction,
  withRunTree,
  ROOT,
} from "./singletons/traceable.js";

export type { RunTreeLike, TraceableFunction } from "./singletons/types.js";
