/* eslint-disable import/no-extraneous-dependencies */
import {
  CallbackManager,
  CallbackManagerForChainRun,
} from "@langchain/core/callbacks/manager";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { RunTree, RunTreeConfig } from "./run_trees.js";
import { Run } from "./schemas.js";
import {
  Runnable,
  RunnableConfig,
  getCallbackManagerForConfig,
} from "@langchain/core/runnables";
import { TraceableFunction, isTraceableFunction } from "./traceable.js";

// TODO: move this to langchain/smith
export async function getLangchainCallbacks(runTree: RunTree) {
  // TODO: CallbackManager.configure() is only async due to LangChainTracer
  // creationg being async, which is unnecessary.

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

  const queue = [runTree];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current.id)) continue;
    visited.add(current.id);

    runMap.set(current.id, current);
    if (current.child_runs) {
      queue.push(...current.child_runs);
    }

    if (current.parent_run) {
      queue.push(current.parent_run);
    }
  }

  if (callbacks != null) {
    Object.assign(callbacks, { _parentRunId: runTree.id });
  }

  if (langChainTracer != null) {
    Object.assign(langChainTracer, { runMap, client: runTree.client });
  }

  return callbacks;
}

type AnyTraceableFunction = TraceableFunction<(...any: any[]) => any>;

class CallbackManagerRunTree extends RunTree {
  callbackManager: CallbackManager;

  activeCallbackManager: CallbackManagerForChainRun | undefined = undefined;

  constructor(config: RunTreeConfig, callbackManager: CallbackManager) {
    super(config);

    this.callbackManager = callbackManager;
  }

  public createChild(config: RunTreeConfig): RunTree {
    const child = new CallbackManagerRunTree(
      {
        ...config,
        parent_run: this,
        project_name: this.project_name,
        client: this.client,
      },
      this.activeCallbackManager?.getChild() ?? this.callbackManager
    );
    this.child_runs.push(child);
    return child as RunTree;
  }

  async postRun(): Promise<void> {
    // how it is translated in comparison to basic RunTree?
    this.activeCallbackManager = await this.callbackManager.handleChainStart(
      typeof this.serialized !== "object" &&
        this.serialized != null &&
        "lc" in this.serialized
        ? this.serialized
        : {
            id: ["langchain", "smith", "CallbackManagerRunTree"],
            lc: 1,
            type: "not_implemented",
          },
      this.inputs,
      this.id,
      this.run_type,
      undefined,
      undefined,
      this.name
    );
  }

  async patchRun(): Promise<void> {
    if (this.error) {
      await this.activeCallbackManager?.handleChainError(
        this.error,
        this.id,
        this.parent_run?.id,
        undefined,
        undefined
      );
    } else {
      await this.activeCallbackManager?.handleChainEnd(
        this.outputs ?? {},
        this.id,
        this.parent_run?.id,
        undefined,
        undefined
      );
    }
  }
}

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
    const callbackManager = await getCallbackManagerForConfig(config);

    const partialConfig =
      "langsmith:traceable" in this.func
        ? (this.func["langsmith:traceable"] as RunTreeConfig)
        : { name: "<lambda>" };

    if (!callbackManager) throw new Error("CallbackManager not found");

    const tracer = callbackManager?.handlers.find(
      (handler): handler is LangChainTracer =>
        handler?.name === "langchain_tracer"
    );

    const runTree = new CallbackManagerRunTree(
      {
        tracingEnabled: !!tracer,
        ...partialConfig,
        parent_run: callbackManager?._parentRunId
          ? new RunTree({
              name: "<parent>",
              id: callbackManager?._parentRunId,
              tracingEnabled: !!tracer,
            })
          : undefined,
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore mismatched client version
        client: tracer?.client,
      },
      callbackManager
    );

    if (
      typeof input === "object" &&
      input != null &&
      Object.keys(input).length === 1
    ) {
      if ("args" in input && Array.isArray(input)) {
        return (await this.func(runTree, ...input)) as RunOutput;
      }

      if (
        "input" in input &&
        !(
          typeof input === "object" &&
          input != null &&
          !Array.isArray(input) &&
          // eslint-disable-next-line no-instanceof/no-instanceof
          !(input instanceof Date)
        )
      ) {
        try {
          return (await this.func(runTree, input.input)) as RunOutput;
        } catch (err) {
          return (await this.func(runTree, input)) as RunOutput;
        }
      }
    }

    return (await this.func(runTree, input)) as RunOutput;
  }
}
