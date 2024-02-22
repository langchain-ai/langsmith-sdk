import * as uuid from "uuid";
import { BaseRun, KVMap, RunCreate, RunUpdate } from "./schemas.js";
import { getEnvironmentVariable, getRuntimeEnvironment } from "./utils/env.js";
import { Client } from "./client.js";

const warnedMessages: Record<string, boolean> = {};

function warnOnce(message: string): void {
  if (!warnedMessages[message]) {
    console.warn(message);
    warnedMessages[message] = true;
  }
}

function stripNonAlphanumeric(input: string) {
  return input.replace(/[-:.]/g, "");
}

export function convertToDottedOrderFormat(epoch: number, runId: string) {
  return (
    stripNonAlphanumeric(`${new Date(epoch).toISOString().slice(0, -1)}000Z`) +
    runId
  );
}

export interface RunTreeConfig {
  name: string;
  run_type?: string;
  id?: string;
  project_name?: string;
  parent_run?: RunTree;
  parent_run_id?: string;
  child_runs?: RunTree[];
  start_time?: number;
  end_time?: number;
  extra?: KVMap;
  tags?: string[];
  error?: string;
  serialized?: object;
  inputs?: KVMap;
  outputs?: KVMap;
  reference_example_id?: string;
  client?: Client;
}

export interface RunnableConfigLike {
  /**
   * Tags for this call and any sub-calls (eg. a Chain calling an LLM).
   * You can use these to filter calls.
   */
  tags?: string[];

  /**
   * Metadata for this call and any sub-calls (eg. a Chain calling an LLM).
   * Keys should be strings, values should be JSON-serializable.
   */
  metadata?: Record<string, unknown>;

  /**
   * Callbacks for this call and any sub-calls (eg. a Chain calling an LLM).
   * Tags are passed to all callbacks, metadata is passed to handle*Start callbacks.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  callbacks?: any;
}

interface CallbackManagerLike {
  handlers: TracerLike[];
  getParentRunId?: () => string | undefined;
}

interface TracerLike {
  name: string;
}
interface LangChainTracerLike extends TracerLike {
  name: "langchain_tracer";
  projectName: string;
  getRun?: (id: string) => RunTree | undefined;
}

export class RunTree implements BaseRun {
  id: string;
  name: RunTreeConfig["name"];
  run_type: string;
  project_name: string;
  parent_run?: BaseRun;
  child_runs: RunTree[];
  start_time: number;
  end_time?: number;
  extra: KVMap;
  tags?: string[];
  error?: string;
  serialized: object;
  inputs: KVMap;
  outputs?: KVMap;
  reference_example_id?: string;
  client: Client;
  events?: KVMap[] | undefined;
  trace_id: string;
  dotted_order: string;

  constructor(config: RunTreeConfig) {
    const defaultConfig = RunTree.getDefaultConfig();
    const client = config.client ?? new Client();
    Object.assign(this, { ...defaultConfig, ...config, client });
    if (!this.trace_id) {
      if (this.parent_run) {
        this.trace_id = this.parent_run.trace_id ?? this.id;
      } else {
        this.trace_id = this.id;
      }
    }
    if (!this.dotted_order) {
      const currentDottedOrder = convertToDottedOrderFormat(
        this.start_time,
        this.id
      );
      if (this.parent_run) {
        this.dotted_order =
          this.parent_run.dotted_order + "." + currentDottedOrder;
      } else {
        this.dotted_order = currentDottedOrder;
      }
    }
  }

  static fromRunnableConfig(
    config: RunnableConfigLike,
    props: {
      name: string;
      tags?: string[];
      metadata?: KVMap;
    }
  ): RunTree {
    // We only handle the callback manager case for now
    const callbackManager = config?.callbacks as
      | CallbackManagerLike
      | undefined;
    let parentRun: RunTree | undefined;
    let projectName: string | undefined;
    if (callbackManager) {
      const parentRunId = callbackManager?.getParentRunId?.() ?? "";
      const langChainTracer = callbackManager?.handlers?.find(
        (handler: TracerLike) => handler?.name == "langchain_tracer"
      ) as LangChainTracerLike | undefined;
      parentRun = langChainTracer?.getRun?.(parentRunId);
      projectName = langChainTracer?.projectName;
    }
    const deduppedTags = [
      ...new Set((parentRun?.tags ?? []).concat(config?.tags ?? [])),
    ];
    const dedupedMetadata = {
      ...parentRun?.extra?.metadata,
      ...config?.metadata,
    };
    const rt = new RunTree({
      name: props?.name ?? "<lambda>",
      parent_run: parentRun,
      tags: deduppedTags,
      extra: {
        metadata: dedupedMetadata,
      },
      project_name: projectName,
    });
    return rt;
  }

  private static getDefaultConfig(): object {
    return {
      id: uuid.v4(),
      run_type: "chain",
      project_name:
        getEnvironmentVariable("LANGCHAIN_PROJECT") ??
        getEnvironmentVariable("LANGCHAIN_SESSION") ?? // TODO: Deprecate
        "default",
      child_runs: [],
      api_url:
        getEnvironmentVariable("LANGCHAIN_ENDPOINT") ?? "http://localhost:1984",
      api_key: getEnvironmentVariable("LANGCHAIN_API_KEY"),
      caller_options: {},
      start_time: Date.now(),
      serialized: {},
      inputs: {},
      extra: {},
    };
  }

  public async createChild(config: RunTreeConfig): Promise<RunTree> {
    const child = new RunTree({
      ...config,
      parent_run: this,
      project_name: this.project_name,
      client: this.client,
    });

    this.child_runs.push(child);
    return child;
  }

  async end(
    outputs?: KVMap,
    error?: string,
    endTime = Date.now()
  ): Promise<void> {
    this.outputs = outputs;
    this.error = error;
    this.end_time = endTime;
  }

  private async _convertToCreate(
    run: RunTree,
    excludeChildRuns = true
  ): Promise<RunCreate> {
    const runExtra = run.extra ?? {};
    if (!runExtra.runtime) {
      runExtra.runtime = {};
    }
    const runtimeEnv = await getRuntimeEnvironment();
    for (const [k, v] of Object.entries(runtimeEnv)) {
      if (!runExtra.runtime[k]) {
        runExtra.runtime[k] = v;
      }
    }
    let child_runs: RunCreate[];
    let parent_run_id: string | undefined;
    if (!excludeChildRuns) {
      child_runs = await Promise.all(
        run.child_runs.map((child_run) =>
          this._convertToCreate(child_run, excludeChildRuns)
        )
      );
      parent_run_id = undefined;
    } else {
      parent_run_id = run.parent_run?.id;
      child_runs = [];
    }
    const persistedRun: RunCreate = {
      id: run.id,
      name: run.name,
      start_time: run.start_time,
      end_time: run.end_time,
      run_type: run.run_type,
      reference_example_id: run.reference_example_id,
      extra: runExtra,
      serialized: run.serialized,
      error: run.error,
      inputs: run.inputs,
      outputs: run.outputs,
      session_name: run.project_name,
      child_runs: child_runs,
      parent_run_id: parent_run_id,
      trace_id: run.trace_id,
      dotted_order: run.dotted_order,
      tags: run.tags,
    };
    return persistedRun;
  }

  async postRun(excludeChildRuns = true): Promise<void> {
    const runCreate = await this._convertToCreate(this, true);
    await this.client.createRun(runCreate);

    if (!excludeChildRuns) {
      warnOnce(
        "Posting with excludeChildRuns=false is deprecated and will be removed in a future version."
      );
      for (const childRun of this.child_runs) {
        await childRun.postRun(false);
      }
    }
  }

  async patchRun(): Promise<void> {
    const runUpdate: RunUpdate = {
      end_time: this.end_time,
      error: this.error,
      outputs: this.outputs,
      parent_run_id: this.parent_run?.id,
      reference_example_id: this.reference_example_id,
      extra: this.extra,
      events: this.events,
      dotted_order: this.dotted_order,
      trace_id: this.trace_id,
      tags: this.tags,
    };

    await this.client.updateRun(this.id, runUpdate);
  }
}

export function isRunTree(x?: unknown): x is RunTree {
  return (
    x !== undefined &&
    typeof (x as RunTree).createChild === "function" &&
    typeof (x as RunTree).postRun === "function"
  );
}

function containsLangChainTracerLike(x?: unknown): x is LangChainTracerLike[] {
  return (
    Array.isArray(x) &&
    x.some((callback: unknown) => {
      return (
        typeof (callback as LangChainTracerLike).name === "string" &&
        (callback as LangChainTracerLike).name === "langchain_tracer"
      );
    })
  );
}

export function isRunnableConfigLike(x?: unknown): x is RunnableConfigLike {
  // Check that it's an object with a callbacks arg
  // that has either a CallbackManagerLike object with a langchain tracer within it
  // or an array with a LangChainTracerLike object within it

  return (
    x !== undefined &&
    typeof (x as RunnableConfigLike).callbacks === "object" &&
    // Callback manager with a langchain tracer
    (containsLangChainTracerLike(
      (x as RunnableConfigLike).callbacks?.handlers
    ) ||
      // Or it's an array with a LangChainTracerLike object within it
      containsLangChainTracerLike((x as RunnableConfigLike).callbacks))
  );
}
