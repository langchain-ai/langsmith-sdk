import { CallbackManager } from "@langchain/core/callbacks/manager";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { Runnable, RunnableConfig } from "@langchain/core/runnables";

import { RunTree } from "./run_trees.js";
import { Run } from "./schemas.js";
import {
  TraceableFunction,
  getCurrentRunTree,
  isTraceableFunction,
} from "./traceable.js";

/**
 * Converts the current run tree active within a traceable-wrapped function
 * into a LangChain compatible callback manager. This is useful to handoff tracing
 * from LangSmith to LangChain Runnables and LLMs.
 *
 * @param {RunTree | undefined} currentRunTree Current RunTree from within a traceable-wrapped function. If not provided, the current run tree will be inferred from AsyncLocalStorage.
 * @returns {CallbackManager | undefined} Callback manager used by LangChain Runnable objects.
 */
export async function getLangchainCallbacks(
  currentRunTree?: RunTree | undefined
) {
  const runTree: RunTree | undefined = currentRunTree ?? getCurrentRunTree();
  if (!runTree) return undefined;

  // TODO: CallbackManager.configure() is only async due to LangChainTracer
  // factory being unnecessarily async.
  let callbacks = await CallbackManager.configure();
  if (!callbacks && runTree.tracingEnabled) {
    callbacks = new CallbackManager();
  }

  let langChainTracer = callbacks?.handlers.find(
    (handler): handler is LangChainTracer =>
      handler?.name === "langchain_tracer"
  );

  if (!langChainTracer && runTree.tracingEnabled) {
    langChainTracer = new LangChainTracer();
    callbacks?.addHandler(langChainTracer);
  }

  const runMap = new Map<string, Run>();

  // find upward root run
  let rootRun = runTree;
  const rootVisited = new Set<string>();
  while (rootRun.parent_run) {
    if (rootVisited.has(rootRun.id)) break;
    rootVisited.add(rootRun.id);
    rootRun = rootRun.parent_run;
  }

  const queue = [rootRun];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current.id)) continue;
    visited.add(current.id);

    runMap.set(current.id, current);
    if (current.child_runs) {
      queue.push(...current.child_runs);
    }
  }

  if (callbacks != null) {
    Object.assign(callbacks, { _parentRunId: runTree.id });
  }

  if (langChainTracer != null) {
    Object.assign(langChainTracer, {
      runMap,
      client: runTree.client,
      projectName: runTree.project_name || langChainTracer.projectName,
      exampleId: runTree.reference_example_id || langChainTracer.exampleId,
    });
  }

  return callbacks;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyTraceableFunction = TraceableFunction<(...any: any[]) => any>;

/**
 * RunnableTraceable is a Runnable that wraps a traceable function.
 * This allows adding Langsmith traced functions into LangChain sequences.
 */
export class RunnableTraceable<RunInput, RunOutput> extends Runnable<
  RunInput,
  RunOutput
> {
  lc_serializable = false;

  lc_namespace = ["langchain_core", "runnables"];

  protected func: AnyTraceableFunction;

  constructor(fields: { func: AnyTraceableFunction }) {
    super(fields);

    if (!isTraceableFunction(fields.func)) {
      throw new Error(
        "RunnableTraceable requires a function that is wrapped in traceable higher-order function"
      );
    }

    this.func = fields.func;
  }

  async invoke(input: RunInput, options?: Partial<RunnableConfig>) {
    const [config] = this._getOptionsList(options ?? {}, 1);
    return (await this.func(config, input)) as RunOutput;
  }

  static from(func: AnyTraceableFunction) {
    return new RunnableTraceable({ func });
  }
}
