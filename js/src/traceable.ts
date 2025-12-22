import { AsyncLocalStorage } from "node:async_hooks";

import {
  RunTree,
  RunTreeConfig,
  RunnableConfigLike,
  isRunTree,
  isRunnableConfigLike,
} from "./run_trees.js";
import {
  Attachments,
  InvocationParamsSchema,
  KVMap,
  ExtractedUsageMetadata,
} from "./schemas.js";
import { isTracingEnabled } from "./env.js";
import {
  ROOT,
  AsyncLocalStorageProviderSingleton,
  getCurrentRunTree,
} from "./singletons/traceable.js";
import {
  _LC_CHILD_RUN_END_PROMISES_KEY,
  _LC_CONTEXT_VARIABLES_KEY,
} from "./singletons/constants.js";
import type {
  TraceableFunction,
  ContextPlaceholder,
} from "./singletons/types.js";
import {
  isKVMap,
  isReadableStream,
  isAsyncIterable,
  isIteratorLike,
  isThenable,
  isGenerator,
  isPromiseMethod,
} from "./utils/asserts.js";
import { getOtelEnabled } from "./utils/env.js";
import { __version__ } from "./index.js";
import { getOTELTrace, getOTELContext } from "./singletons/otel.js";
import { getUuidFromOtelSpanId } from "./experimental/otel/utils.js";
import { OTELTracer } from "./experimental/otel/types.js";
import {
  LANGSMITH_REFERENCE_EXAMPLE_ID,
  LANGSMITH_SESSION_NAME,
  LANGSMITH_TRACEABLE,
} from "./experimental/otel/constants.js";

AsyncLocalStorageProviderSingleton.initializeGlobalInstance(
  new AsyncLocalStorage<RunTree | ContextPlaceholder | undefined>()
);

/**
 * Create OpenTelemetry context manager from RunTree if OTEL is enabled.
 */
function maybeCreateOtelContext<T>(
  runTree?: RunTree,
  projectName?: string,
  tracer?: OTELTracer
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): ((fn: (...args: any[]) => T) => T) | undefined {
  if (!runTree || !getOtelEnabled()) {
    return;
  }

  const otel_trace = getOTELTrace();

  try {
    const activeTraceId = otel_trace.getActiveSpan()?.spanContext()?.traceId;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (fn: (...args: any[]) => T) => {
      const resolvedTracer =
        tracer ?? otel_trace.getTracer("langsmith", __version__);
      const attributes: KVMap = {
        [LANGSMITH_TRACEABLE]: "true",
      };
      if (runTree.reference_example_id) {
        attributes[LANGSMITH_REFERENCE_EXAMPLE_ID] =
          runTree.reference_example_id;
      }
      if (projectName !== undefined) {
        attributes[LANGSMITH_SESSION_NAME] = projectName;
      }
      const forceOTELRoot = runTree.extra?.ls_otel_root === true;
      return resolvedTracer.startActiveSpan(
        runTree.name,
        {
          attributes,
          root: forceOTELRoot,
        },
        () => {
          if (activeTraceId === undefined || forceOTELRoot) {
            const otelSpanId = otel_trace
              .getActiveSpan()
              ?.spanContext()?.spanId;
            if (otelSpanId) {
              const langsmithTraceId = getUuidFromOtelSpanId(otelSpanId);
              // Must refetch from our primary async local storage
              const currentRunTree = getCurrentRunTree();
              if (currentRunTree) {
                // This is only for root runs to ensure that trace id
                // and the root run id are returned correctly.
                // This is important for things like leaving feedback on
                // target function runs during evaluation.
                currentRunTree.id = langsmithTraceId;
                currentRunTree.trace_id = langsmithTraceId;
              }
            }
          }
          return fn();
        }
      );
    };
  } catch {
    // Silent failure if OTEL setup is incomplete
    return;
  }
}

const runInputsToMap = (rawInputs: unknown[]) => {
  const firstInput = rawInputs[0];
  let inputs: KVMap;

  if (firstInput === null) {
    inputs = { inputs: null };
  } else if (firstInput === undefined) {
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

const handleRunInputs = <Args extends unknown[]>(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  inputs: any,
  processInputs: (inputs: Readonly<ProcessInputs<Args>>) => KVMap
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

const _extractUsage = (runData: {
  runTree: RunTree;
  outputs?: KVMap;
}): ExtractedUsageMetadata | undefined => {
  const usageMetadataFromMetadata = (runData.runTree.extra.metadata ?? {})
    .usage_metadata;
  return runData.outputs?.usage_metadata ?? usageMetadataFromMetadata;
};

async function handleEnd(params: {
  runTree?: RunTree;
  on_end: (runTree?: RunTree) => void;
  postRunPromise?: Promise<void>;
  deferredInputs?: boolean;
}) {
  const { runTree, on_end, postRunPromise, deferredInputs } = params;
  const onEnd = on_end;
  if (onEnd) {
    onEnd(runTree);
  }
  await postRunPromise;
  if (deferredInputs) {
    await runTree?.postRun();
  } else {
    await runTree?.patchRun({
      excludeInputs: true,
    });
  }
}

const _populateUsageMetadata = (processedOutputs: KVMap, runTree?: RunTree) => {
  if (runTree !== undefined) {
    let usageMetadata: ExtractedUsageMetadata | undefined;
    try {
      usageMetadata = _extractUsage({ runTree, outputs: processedOutputs });
    } catch (e) {
      console.error("Error occurred while extracting usage metadata:", e);
    }
    if (usageMetadata !== undefined) {
      runTree.extra.metadata = {
        ...runTree.extra.metadata,
        usage_metadata: usageMetadata,
      };
      processedOutputs.usage_metadata = usageMetadata;
    }
  }
};

function isAsyncFn(
  fn: unknown
): fn is (...args: unknown[]) => Promise<unknown> {
  return (
    fn != null &&
    typeof fn === "function" &&
    fn.constructor.name === "AsyncFunction"
  );
}

// Note: This mutates the run tree
async function handleRunOutputs<Return>(params: {
  runTree?: RunTree;
  rawOutputs: unknown;
  processOutputsFn: (
    outputs: Readonly<ProcessOutputs<Return>>
  ) => KVMap | Promise<KVMap>;
  on_end: (runTree?: RunTree) => void;
  postRunPromise?: Promise<void>;
  deferredInputs?: boolean;
  skipChildPromiseDelay?: boolean;
}): Promise<void> {
  const {
    runTree,
    rawOutputs,
    processOutputsFn,
    on_end,
    postRunPromise,
    deferredInputs,
    skipChildPromiseDelay,
  } = params;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let outputs: any;

  if (isKVMap(rawOutputs)) {
    outputs = { ...rawOutputs };
  } else {
    outputs = { outputs: rawOutputs };
  }

  const childRunEndPromises =
    !skipChildPromiseDelay &&
    isRunTree(runTree) &&
    _LC_CHILD_RUN_END_PROMISES_KEY in runTree &&
    Array.isArray(runTree[_LC_CHILD_RUN_END_PROMISES_KEY])
      ? Promise.all(runTree[_LC_CHILD_RUN_END_PROMISES_KEY] ?? [])
      : Promise.resolve();

  try {
    outputs = processOutputsFn(outputs);
    // TODO: Investigate making this behavior for all returned promises
    // on next minor bump.
    if (isAsyncFn(processOutputsFn)) {
      void outputs
        .then(async (processedOutputs: KVMap) => {
          _populateUsageMetadata(processedOutputs, runTree);
          await childRunEndPromises;
          await runTree?.end(processedOutputs);
        })
        .catch(async (e: unknown) => {
          console.error(
            "Error occurred during processOutputs. Sending unprocessed outputs:",
            e
          );
          try {
            await childRunEndPromises;
            await runTree?.end(outputs);
          } catch (e) {
            console.error("Error occurred during runTree?.end.", e);
          }
        })
        .finally(async () => {
          try {
            await handleEnd({
              runTree,
              postRunPromise,
              on_end,
              deferredInputs,
            });
          } catch (e) {
            console.error("Error occurred during handleEnd.", e);
          }
        });
      return;
    }
  } catch (e) {
    console.error(
      "Error occurred during processOutputs. Sending unprocessed outputs:",
      e
    );
  }
  _populateUsageMetadata(outputs, runTree);
  void childRunEndPromises
    .then(async () => {
      try {
        await runTree?.end(outputs);
        await handleEnd({ runTree, postRunPromise, on_end, deferredInputs });
      } catch (e) {
        console.error(e);
      }
    })
    .catch((e) => {
      console.error(
        "Error occurred during childRunEndPromises.then. This should never happen.",
        e
      );
    });
  return;
}

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
  processInputs: (inputs: Readonly<ProcessInputs<Args>>) => KVMap,
  extractAttachments:
    | ((...args: Args) => [Attachments | undefined, KVMap])
    | undefined
): RunTree | ContextPlaceholder => {
  if (!isTracingEnabled(runTree.tracingEnabled)) {
    return {};
  }

  const [attached, args] = handleRunAttachments(
    inputs,
    extractAttachments as
      | ((...args: unknown[]) => [Attachments | undefined, unknown[]])
      | undefined
  );
  runTree.attachments = attached;
  runTree.inputs = handleRunInputs<Args>(args, processInputs);

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
            (value: unknown) => {
              proxyState.current = ["resolve", value];
              return resolve(value);
            },
            (error: unknown) => {
              proxyState.current = ["reject", error];
              return reject(error);
            }
          );
        };
      }

      if (prop === "catch") {
        const boundCatch = arg[prop].bind(arg);
        return (reject: (error: unknown) => unknown) => {
          return boundCatch((error: unknown) => {
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

const convertSerializableArg = (
  arg: unknown
): { converted: unknown; deferredInputs: boolean } => {
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
    return { converted: pipeThrough, deferredInputs: true };
  }

  if (isAsyncIterable(arg)) {
    const proxyState: {
      current: (Promise<IteratorResult<unknown>> & {
        toJSON: () => unknown;
      })[];
    } = { current: [] };

    const converted = new Proxy(arg, {
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
                    const wrapped = getSerializablePromise(
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      bound(...(args as any))
                    );
                    proxyState.current.push(
                      wrapped as Promise<IteratorResult<unknown>> & {
                        toJSON: () => IteratorResult<unknown>;
                      }
                    );
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
    return { converted, deferredInputs: true };
  }

  if (!Array.isArray(arg) && isIteratorLike(arg)) {
    const proxyState: Array<IteratorResult<unknown>> = [];

    const converted = new Proxy(arg, {
      get(target, prop, receiver) {
        if (prop === "next" || prop === "return" || prop === "throw") {
          const bound = arg[prop]?.bind(arg);
          return (
            ...args: Parameters<
              Exclude<Iterator<unknown>["next" | "return" | "throw"], undefined>
            >
          ) => {
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
    return { converted, deferredInputs: true };
  }

  if (isThenable(arg)) {
    return { converted: getSerializablePromise(arg), deferredInputs: true };
  }

  return { converted: arg, deferredInputs: false };
};

export type ProcessInputs<Args extends unknown[]> = Args extends []
  ? Record<string, never>
  : Args extends [infer Input]
  ? Input extends KVMap
    ? Input extends Iterable<infer Item> | AsyncIterable<infer Item>
      ? { input: Array<Item> }
      : Input
    : { input: Input }
  : { args: Args };

export type ProcessOutputs<ReturnValue> = ReturnValue extends KVMap
  ? ReturnValue extends Iterable<infer Item> | AsyncIterable<infer Item>
    ? { outputs: Array<Item> }
    : ReturnValue
  : { outputs: ReturnValue };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type TraceableConfig<Func extends (...args: any[]) => any> = Partial<
  Omit<RunTreeConfig, "inputs" | "outputs">
> & {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  aggregator?: (args: any[]) => any;
  argsConfigPath?: [number] | [number, string];
  tracer?: OTELTracer;
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
   * The input to this function is determined as follows based on the
   * arguments passed to the wrapped function:
   * - If called with one argument that is an object, it will be the unchanged argument
   * - If called with one argument that is not an object, it will be `{ input: arg }`
   * - If called with multiple arguments, it will be `{ args: [...arguments] }`
   * - If called with no arguments, it will be an empty object `{}`
   *
   * @param inputs Key-value map of the function inputs.
   * @returns Transformed key-value map
   */
  processInputs?: (inputs: Readonly<ProcessInputs<Parameters<Func>>>) => KVMap;

  /**
   * Apply transformations to the outputs before logging.
   * This function should NOT mutate the outputs.
   * `processOutputs` is not inherited by nested traceable functions.
   *
   * The input to this function is determined as follows based on the
   * return value of the wrapped function:
   * - If the return value is an object, it will be the unchanged return value
   * - If the return value is not an object, it will wrapped as `{ outputs: returnValue }`
   *
   * @param outputs Key-value map of the function outputs
   * @returns Transformed key-value map
   */
  processOutputs?: (
    outputs: Readonly<ProcessOutputs<Awaited<ReturnType<Func>>>>
  ) => KVMap | Promise<KVMap>;
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
  config?: TraceableConfig<Func>
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

    let runEndedPromiseResolver: () => void;
    const runEndedPromise = new Promise<void>((resolve) => {
      runEndedPromiseResolver = resolve;
    });
    const on_end = (runTree?: RunTree) => {
      if (config?.on_end) {
        if (!runTree) {
          console.warn("Can not call 'on_end' if currentRunTree is undefined");
        } else {
          config.on_end(runTree);
        }
      }
      runEndedPromiseResolver();
    };
    const asyncLocalStorage = AsyncLocalStorageProviderSingleton.getInstance();

    // TODO: deal with possible nested promises and async iterables
    const processedArgs = args as Inputs;
    let deferredInputs = false;
    for (let i = 0; i < processedArgs.length; i++) {
      const { converted, deferredInputs: argDefersInput } =
        convertSerializableArg(processedArgs[i]);
      processedArgs[i] = converted;
      deferredInputs = deferredInputs || argDefersInput;
    }

    const [currentContext, rawInputs] = ((): [
      RunTree | ContextPlaceholder,
      Inputs
    ] => {
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
      let lc_contextVars: unknown;
      // If a context var is set by LangChain outside of a traceable,
      // it will be an object with a single property and we should copy
      // context vars over into the new run tree.
      if (
        prevRunFromStore !== undefined &&
        _LC_CONTEXT_VARIABLES_KEY in prevRunFromStore
      ) {
        lc_contextVars = prevRunFromStore[_LC_CONTEXT_VARIABLES_KEY];
      }
      if (isRunTree(prevRunFromStore)) {
        if (
          _LC_CHILD_RUN_END_PROMISES_KEY in prevRunFromStore &&
          Array.isArray(prevRunFromStore[_LC_CHILD_RUN_END_PROMISES_KEY])
        ) {
          prevRunFromStore[_LC_CHILD_RUN_END_PROMISES_KEY].push(
            runEndedPromise
          );
        } else {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (prevRunFromStore as any)[_LC_CHILD_RUN_END_PROMISES_KEY] = [
            runEndedPromise,
          ];
        }
        const currentRunTree = getTracingRunTree(
          prevRunFromStore.createChild(ensuredConfig),
          processedArgs,
          config?.getInvocationParams,
          processInputsFn,
          extractAttachmentsFn
        );
        if (lc_contextVars) {
          ((currentRunTree ?? {}) as Record<string | symbol, unknown>)[
            _LC_CONTEXT_VARIABLES_KEY
          ] = lc_contextVars;
        }
        return [currentRunTree, processedArgs as Inputs];
      }

      const currentRunTree = getTracingRunTree(
        new RunTree(ensuredConfig),
        processedArgs,
        config?.getInvocationParams,
        processInputsFn,
        extractAttachmentsFn
      );
      if (lc_contextVars) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ((currentRunTree ?? {}) as any)[_LC_CONTEXT_VARIABLES_KEY] =
          lc_contextVars;
      }
      return [currentRunTree, processedArgs as Inputs];
    })();

    const currentRunTree = isRunTree(currentContext)
      ? currentContext
      : undefined;

    const otelContextManager = maybeCreateOtelContext(
      currentRunTree,
      config?.project_name,
      config?.tracer
    );
    const otel_context = getOTELContext();

    const runWithContext = () => {
      const postRunPromise = !deferredInputs
        ? currentRunTree?.postRun()
        : Promise.resolve();

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
        const capturedOtelContext = otel_context.active();

        const tappedStream = new ReadableStream({
          async start(controller) {
            // eslint-disable-next-line no-constant-condition
            while (true) {
              const result = await (snapshot
                ? snapshot(() =>
                    otel_context.with(capturedOtelContext, () => reader.read())
                  )
                : otel_context.with(capturedOtelContext, () => reader.read()));
              if (result.done) {
                finished = true;
                await handleRunOutputs({
                  runTree: currentRunTree,
                  rawOutputs: await handleChunks(chunks),
                  processOutputsFn,
                  on_end,
                  postRunPromise,
                  deferredInputs,
                });
                controller.close();
                break;
              }
              chunks.push(result.value);
              // Add new_token event for streaming LLM runs
              if (currentRunTree && currentRunTree.run_type === "llm") {
                currentRunTree.addEvent({
                  name: "new_token",
                  kwargs: { token: result.value },
                });
              }
              controller.enqueue(result.value);
            }
          },
          async cancel(reason) {
            if (!finished) await currentRunTree?.end(undefined, "Cancelled");
            await handleRunOutputs({
              runTree: currentRunTree,
              rawOutputs: await handleChunks(chunks),
              processOutputsFn,
              on_end,
              postRunPromise,
              deferredInputs,
            });
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
        let hasError = false;
        const chunks: unknown[] = [];
        const capturedOtelContext = otel_context.active();
        try {
          while (true) {
            const { value, done } = await (snapshot
              ? snapshot(() =>
                  otel_context.with(capturedOtelContext, () => iterator.next())
                )
              : otel_context.with(capturedOtelContext, () => iterator.next()));
            if (done) {
              finished = true;
              break;
            }
            chunks.push(value);
            // Add new_token event for streaming LLM runs
            if (currentRunTree && currentRunTree.run_type === "llm") {
              currentRunTree.addEvent({
                name: "new_token",
                kwargs: { token: value },
              });
            }
            yield value;
          }
        } catch (e) {
          hasError = true;
          await currentRunTree?.end(undefined, String(e));
          throw e;
        } finally {
          if (!finished) {
            // Call return() on the original iterator to trigger cleanup
            if (iterator.return) {
              await iterator.return(undefined);
            }
            await currentRunTree?.end(undefined, "Cancelled");
          }
          await handleRunOutputs({
            runTree: currentRunTree,
            rawOutputs: await handleChunks(chunks),
            processOutputsFn,
            on_end,
            postRunPromise,
            deferredInputs,
            skipChildPromiseDelay: hasError || !finished,
          });
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
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (returnValue as Record<string, any>)[__finalTracedIteratorKey]
        )
      ) {
        const snapshot = AsyncLocalStorage.snapshot();
        return {
          ...returnValue,
          [__finalTracedIteratorKey]: wrapAsyncGeneratorForTracing(
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  (rawOutput as Record<string, any>)[__finalTracedIteratorKey]
                )
              ) {
                const snapshot = AsyncLocalStorage.snapshot();
                return {
                  ...rawOutput,
                  [__finalTracedIteratorKey]: wrapAsyncGeneratorForTracing(
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
                  await handleRunOutputs({
                    runTree: currentRunTree,
                    rawOutputs: await handleChunks(
                      chunks.reduce<unknown[]>((memo, { value, done }) => {
                        if (!done || typeof value !== "undefined") {
                          memo.push(value);
                        }

                        return memo;
                      }, [])
                    ),
                    processOutputsFn,
                    on_end,
                    postRunPromise,
                    deferredInputs,
                  });
                } catch (e) {
                  console.error(
                    "[LANGSMITH]: Error occurred while handling run outputs:",
                    e
                  );
                }

                return (function* () {
                  for (const ret of chunks) {
                    if (ret.done) return ret.value;
                    yield ret.value;
                  }
                })();
              }

              try {
                await handleRunOutputs({
                  runTree: currentRunTree,
                  rawOutputs: rawOutput,
                  processOutputsFn,
                  on_end,
                  postRunPromise,
                  deferredInputs,
                });
              } finally {
                // eslint-disable-next-line no-unsafe-finally
                return rawOutput;
              }
            },
            async (error: unknown) => {
              // Don't wait for child runs on error - fail fast
              await currentRunTree?.end(undefined, String(error));
              await handleEnd({
                runTree: currentRunTree,
                postRunPromise,
                on_end,
                deferredInputs,
              });
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
    };

    // Wrap with OTEL context if available, similar to Python's implementation
    if (otelContextManager) {
      return asyncLocalStorage.run(currentContext, () =>
        otelContextManager(runWithContext)
      );
    } else {
      return asyncLocalStorage.run(currentContext, runWithContext);
    }
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
