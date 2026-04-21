/**
 * LangSmith integration for OpenAI Agents SDK.
 *
 * This module provides tracing support for the OpenAI Agents SDK.
 */

import { AsyncLocalStorage } from "node:async_hooks";
import { RunTree } from "../run_trees.js";
import type { ExtractedUsageMetadata } from "../schemas.js";
import { Client } from "../client.js";
import {
  AsyncLocalStorageProviderSingleton,
  getCurrentRunTree,
} from "../singletons/traceable.js";
import type { ContextPlaceholder } from "../singletons/types.js";
import type {
  AgentSpanData,
  CustomSpanData,
  FunctionSpanData,
  GenerationSpanData,
  GenerationUsageData,
  GuardrailSpanData,
  HandoffSpanData,
  ResponseSpanData,
  Span as SDKSpan,
  SpanData,
  Trace as SDKTrace,
} from "@openai/agents";

AsyncLocalStorageProviderSingleton.initializeGlobalInstance(
  new AsyncLocalStorage<RunTree | ContextPlaceholder | undefined>()
);

/**
 * Set the current AsyncLocalStorage store to the given RunTree without a
 * callback. Uses `AsyncLocalStorage.enterWith` if available on the underlying
 * instance (it is on Node's built-in ALS). This is required because the
 * OpenAI Agents tracing processor receives `onSpanStart`/`onSpanEnd` callbacks
 * at different points with no single function to wrap via `withRunTree`.
 *
 * Returns the previous store so callers can restore it on exit.
 *
 * Caveats of `enterWith` (inherent, not avoidable with this API shape):
 *  - Replaces the ALS store for the current async task and all its
 *    descendants. Concurrent async tasks spawned from the caller's scope
 *    during the trace will see the installed store.
 *  - `onTraceEnd`/`onSpanEnd` restoration only works when it runs on the
 *    same async task as the matching start. This is guaranteed by the
 *    OpenAI Agents SDK's span lifecycle (span.start / fn / span.end are
 *    invoked on one task via `_withSpanFactory`).
 */
function enterRunTreeContext(
  runTree: RunTree | undefined
): RunTree | undefined {
  const storage = AsyncLocalStorageProviderSingleton.getInstance();
  const previous = storage.getStore() as RunTree | undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const maybeEnterWith = (storage as any).enterWith;
  if (typeof maybeEnterWith === "function") {
    maybeEnterWith.call(storage, runTree);
  }
  return previous;
}

// `Span` and `Trace` from the SDK are classes with `#private` fields, which
// TypeScript treats as nominally typed — plain mock objects cannot satisfy
// them. We narrow to the subset of public members actually read by the
// processor via `Pick`, which also strips the private brand and lets test
// mocks be plain objects.
type Span<TData extends SpanData = SpanData> = Pick<
  SDKSpan<TData>,
  | "traceId"
  | "spanData"
  | "spanId"
  | "parentId"
  | "error"
  | "startedAt"
  | "endedAt"
  | "toJSON"
>;
type Trace = Pick<
  SDKTrace,
  "traceId" | "name" | "groupId" | "metadata" | "toJSON"
>;

interface TracingProcessor {
  start?(): void;
  onTraceStart(trace: Trace): Promise<void>;
  onTraceEnd(trace: Trace): Promise<void>;
  onSpanStart(span: Span): Promise<void>;
  onSpanEnd(span: Span): Promise<void>;
  shutdown(timeout?: number): Promise<void>;
  forceFlush(): Promise<void>;
}

type RunTypeT =
  | "tool"
  | "chain"
  | "llm"
  | "retriever"
  | "embedding"
  | "prompt"
  | "parser";

/**
 * Parse inputs or outputs into a dictionary format.
 */
function isOpenAIAgentsItemArray(
  data: unknown
): data is Array<Record<string, unknown>> {
  return (
    Array.isArray(data) &&
    data.length > 0 &&
    data.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        "type" in item &&
        typeof (item as { type?: unknown }).type === "string"
    )
  );
}

function normalizeResponseInputItemsForReplay(
  items: Array<Record<string, unknown>>
): Array<Record<string, unknown>> {
  return items.map((item) => {
    const type = item.type;

    if (type === "message") {
      return {
        type: "message",
        role: item.role,
        content: item.content,
      };
    }

    if (type === "reasoning") {
      return {
        type: "reasoning",
        ...(item.id ? { id: item.id } : {}),
        content: Array.isArray(item.content) ? item.content : [],
      };
    }

    if (type === "function_call") {
      return {
        type: "function_call",
        ...(item.id ? { id: item.id } : {}),
        call_id: item.callId,
        name: item.name,
        arguments: item.arguments,
      };
    }

    if (type === "function_call_result") {
      const output = item.output;
      return {
        type: "function_call_output",
        call_id: item.callId,
        output:
          typeof output === "object" && output !== null && "text" in output
            ? output.text
            : output,
      };
    }

    return item;
  });
}

function parseIO(
  data: unknown,
  defaultKey = "output"
): Record<string, unknown> {
  if (data === null || data === undefined) {
    return {};
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return {};
    }
    // Check if this is a list of output blocks (reasoning, message, etc.)
    if (data.length > 0 && typeof data[0] === "object" && data[0] !== null) {
      if ("type" in data[0]) {
        return { [defaultKey]: data };
      } else if (data.length === 1) {
        return data[0] as Record<string, unknown>;
      }
    }
    return { [defaultKey]: data };
  }

  if (typeof data === "object") {
    return data as Record<string, unknown>;
  }

  if (typeof data === "string") {
    try {
      const parsed = JSON.parse(data);
      if (typeof parsed === "object" && parsed !== null) {
        return parsed as Record<string, unknown>;
      }
      return { [defaultKey]: data };
    } catch {
      return { [defaultKey]: data };
    }
  }

  return { [defaultKey]: data };
}

/**
 * Get the LangSmith run type for a span.
 */
function getRunType(span: Span): RunTypeT {
  const spanType = span.spanData?.type;
  if (spanType === "agent" || spanType === "handoff" || spanType === "custom") {
    return "chain";
  } else if (spanType === "function" || spanType === "guardrail") {
    return "tool";
  } else if (spanType === "generation" || spanType === "response") {
    return "llm";
  }
  return "chain";
}

/**
 * Get the run name for a span.
 */
function getRunName(span: Span): string {
  const spanData = span.spanData;
  if ("name" in spanData && spanData.name) {
    return spanData.name;
  }
  const spanType = spanData?.type;
  if (spanType === "generation") {
    return "Generation";
  } else if (spanType === "response") {
    return "Response";
  } else if (spanType === "handoff") {
    return "Handoff";
  }
  return "Span";
}

function deriveAgentInputsOutputs(run: RunTree): {
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
} {
  const children = [...run.child_runs];
  const firstChildWithInputs = children.find(
    (child) => child.inputs && Object.keys(child.inputs).length > 0
  );
  const lastChildWithOutputs = [...children]
    .reverse()
    .find((child) => child.outputs && Object.keys(child.outputs).length > 0);

  return {
    ...(firstChildWithInputs ? { inputs: firstChildWithInputs.inputs } : {}),
    ...(lastChildWithOutputs ? { outputs: lastChildWithOutputs.outputs } : {}),
  };
}

/**
 * Extract span data into a format suitable for LangSmith runs.
 */
function extractSpanData(span: Span): Record<string, unknown> {
  const spanData = span.spanData;
  const data: Record<string, unknown> = {};

  if (spanData.type === "function") {
    const functionData = spanData as FunctionSpanData;
    data.inputs = parseIO(functionData.input, "input");
    data.outputs = parseIO(functionData.output, "output");
  } else if (spanData.type === "generation") {
    const generationData = spanData as GenerationSpanData;
    data.inputs = parseIO(generationData.input, "input");
    data.outputs = parseIO(generationData.output, "output");
    data.invocation_params = {
      model: generationData.model,
      model_config: generationData.model_config,
    };
    if (generationData.usage) {
      data.metadata = {
        usage_metadata: createUsageMetadata(generationData.usage),
      };
    }
  } else if (spanData.type === "response") {
    const responseData = spanData as ResponseSpanData;
    if (responseData._input !== undefined) {
      data.inputs = {
        input: isOpenAIAgentsItemArray(responseData._input)
          ? normalizeResponseInputItemsForReplay(responseData._input)
          : responseData._input,
        instructions:
          typeof responseData._response?.instructions === "string"
            ? responseData._response.instructions
            : "",
      };
    }
    if (responseData._response) {
      const response = responseData._response;
      const outputData = (response.output as unknown[]) ?? [];
      data.outputs = parseIO(outputData, "output");
      // Extract invocation params
      const invocationParams: Record<string, unknown> = {};
      const invocationKeys = [
        "max_output_tokens",
        "model",
        "parallel_tool_calls",
        "reasoning",
        "temperature",
        "text",
        "tool_choice",
        "tools",
        "top_p",
        "truncation",
      ];
      for (const key of invocationKeys) {
        if (key in response) {
          invocationParams[key] = response[key as keyof typeof response];
        }
      }
      data.invocation_params = invocationParams;

      // Extract metadata
      const metadata: Record<string, unknown> = {};
      const metadataKeys = Object.keys(response).filter(
        (k) =>
          k !== "output" &&
          k !== "usage" &&
          k !== "instructions" &&
          !invocationKeys.includes(k)
      );
      for (const key of metadataKeys) {
        metadata[key] = response[key as keyof typeof response];
      }
      metadata.ls_model_name = invocationParams.model;
      metadata.ls_max_tokens = invocationParams.max_output_tokens;
      metadata.ls_temperature = invocationParams.temperature;
      metadata.ls_model_type = "chat";
      metadata.ls_provider = "openai";

      if (response.usage) {
        metadata.usage_metadata = createResponsesUsageMetadata(
          response.usage as Record<string, unknown>
        );
      }
      data.metadata = metadata;
    }
  } else if (spanData.type === "agent") {
    const agentData = spanData as AgentSpanData;
    data.invocation_params = {
      tools: agentData.tools,
      handoffs: agentData.handoffs,
    };
    data.metadata = {
      output_type: agentData.output_type,
    };
  } else if (spanData.type === "handoff") {
    const handoffData = spanData as HandoffSpanData;
    data.inputs = {
      from_agent: handoffData.from_agent,
    };
    data.outputs = {
      to_agent: handoffData.to_agent,
    };
  } else if (spanData.type === "guardrail") {
    const guardrailData = spanData as GuardrailSpanData;
    data.metadata = {
      triggered: guardrailData.triggered,
    };
  } else if (spanData.type === "custom") {
    const customData = spanData as CustomSpanData;
    data.metadata = customData.data;
  }

  return data;
}

/**
 * Create usage metadata from a `generation` span's `GenerationUsageData`.
 *
 * The Agents SDK's generation-span usage shape is intentionally flexible and
 * puts token breakdowns under `usage.details` (e.g. `cached_tokens`,
 * `reasoning_tokens`, `audio_tokens`). This is distinct from the OpenAI
 * Responses API shape used by `response` spans (see
 * {@link createResponsesUsageMetadata}).
 */
function createUsageMetadata(
  usage: GenerationUsageData
): ExtractedUsageMetadata {
  const inputTokens = (usage.input_tokens as number) ?? 0;
  const outputTokens = (usage.output_tokens as number) ?? 0;

  const result: ExtractedUsageMetadata = {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: inputTokens + outputTokens,
  };

  // Handle details if present
  if (usage.details) {
    const details = usage.details as Record<string, unknown>;
    const inputTokenDetails: Record<string, number> = {};
    const outputTokenDetails: Record<string, number> = {};

    // Map common detail fields
    if (typeof details.cached_tokens === "number") {
      inputTokenDetails.cache_read = details.cached_tokens;
    }
    if (typeof details.reasoning_tokens === "number") {
      outputTokenDetails.reasoning = details.reasoning_tokens;
    }
    if (typeof details.audio_tokens === "number") {
      inputTokenDetails.audio = details.audio_tokens;
    }

    if (Object.keys(inputTokenDetails).length > 0) {
      result.input_token_details = inputTokenDetails;
    }
    if (Object.keys(outputTokenDetails).length > 0) {
      result.output_token_details = outputTokenDetails;
    }
  }

  return result;
}

/**
 * Create usage metadata from a `response` span's embedded OpenAI Responses API
 * usage object.
 *
 * Shape:
 * ```
 * {
 *   input_tokens, output_tokens, total_tokens,
 *   input_tokens_details: { cached_tokens },
 *   output_tokens_details: { reasoning_tokens },
 * }
 * ```
 *
 * This is distinct from {@link createUsageMetadata}, which handles the
 * Agents SDK `GenerationUsageData` shape (with breakdowns under `details`).
 */
function createResponsesUsageMetadata(
  usage: Record<string, unknown>
): ExtractedUsageMetadata {
  const inputTokens = (usage.input_tokens as number) ?? 0;
  const outputTokens = (usage.output_tokens as number) ?? 0;
  const totalTokens =
    (usage.total_tokens as number) ?? inputTokens + outputTokens;

  const result: ExtractedUsageMetadata = {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: totalTokens,
  };

  const inputTokenDetails: Record<string, number> = {};
  const outputTokenDetails: Record<string, number> = {};

  const inputDetails = usage.input_tokens_details as
    | Record<string, unknown>
    | undefined;
  if (inputDetails && typeof inputDetails.cached_tokens === "number") {
    inputTokenDetails.cache_read = inputDetails.cached_tokens;
  }

  const outputDetails = usage.output_tokens_details as
    | Record<string, unknown>
    | undefined;
  if (outputDetails && typeof outputDetails.reasoning_tokens === "number") {
    outputTokenDetails.reasoning = outputDetails.reasoning_tokens;
  }

  if (Object.keys(inputTokenDetails).length > 0) {
    result.input_token_details = inputTokenDetails;
  }
  if (Object.keys(outputTokenDetails).length > 0) {
    result.output_token_details = outputTokenDetails;
  }

  return result;
}

/**
 * Tracing processor for the [OpenAI Agents SDK](https://openai.github.io/openai-agents-js/).
 *
 * Traces all intermediate steps of your OpenAI Agent to LangSmith.
 *
 * Requirements: Make sure to install `npm install @openai/agents`.
 *
 * @param client - An instance of `langsmith.Client`. If not provided, a default client is created.
 * @param metadata - Metadata to associate with all traces.
 * @param tags - Tags to associate with all traces.
 * @param projectName - LangSmith project to trace to.
 * @param name - Name of the root trace.
 *
 * @example
 * ```typescript
 * import { Agent, Runner, function_tool, setTraceProcessors } from "@openai/agents";
 * import { OpenAIAgentsTracingProcessor } from "langsmith/wrappers/openai_agents";
 *
 * setTraceProcessors([new OpenAIAgentsTracingProcessor()]);
 *
 * const getWeather = function_tool({
 *   name: "get_weather",
 *   description: "Get the weather for a city",
 *   parameters: { type: "object", properties: { city: { type: "string" } } },
 *   run: async ({ city }: { city: string }) => `The weather in ${city} is sunny`,
 * });
 *
 * const agent = new Agent({
 *   name: "Assistant",
 *   instructions: "You are a helpful assistant",
 *   model: "gpt-4.1-mini",
 *   tools: [getWeather],
 * });
 *
 * const result = await Runner.run(agent, "What's the weather in New York?");
 * console.log(result.finalOutput);
 * ```
 */
export class OpenAIAgentsTracingProcessor implements TracingProcessor {
  private client: Client;
  private _metadata?: Record<string, unknown>;
  private _tags?: string[];
  private _projectName?: string;
  private _name?: string;

  private _firstResponseInputs: Record<string, Record<string, unknown>> = {};
  private _lastResponseOutputs: Record<string, Record<string, unknown>> = {};

  private _runs: Map<string, RunTree> = new Map();
  private _spanDataTypes: Map<string, string> = new Map();
  private _unpostedTraces: Set<string> = new Set();
  private _unpostedSpans: Set<string> = new Set();
  // Previous AsyncLocalStorage store for each trace/span, so nested
  // traceable() calls inside Agents tools correctly nest under the
  // enclosing span and context can be restored when the span/trace ends.
  private _previousStoreByTrace: Map<string, RunTree | undefined> = new Map();
  private _previousStoreBySpan: Map<string, RunTree | undefined> = new Map();

  constructor(options?: {
    client?: Client;
    metadata?: Record<string, unknown>;
    tags?: string[];
    projectName?: string;
    name?: string;
  }) {
    this.client = options?.client ?? new Client();
    this._metadata = options?.metadata;
    this._tags = options?.tags;
    this._projectName = options?.projectName;
    this._name = options?.name;
  }

  async onTraceStart(trace: Trace): Promise<void> {
    let currentRunTree: RunTree | undefined;
    try {
      currentRunTree = getCurrentRunTree();
    } catch {
      // Not in a traceable context
      currentRunTree = undefined;
    }

    // Determine run name
    let runName: string;
    if (this._name) {
      runName = this._name;
    } else if (trace.name) {
      runName = trace.name;
    } else {
      runName = "Agent workflow";
    }

    // Build metadata
    const runExtra: Record<string, unknown> = {
      metadata: {
        ...this._metadata,
        ls_integration: "openai-agents-sdk",
        ls_agent_type: "root",
      },
    };

    const traceDict = (trace.toJSON() as Record<string, unknown>) ?? {};
    const groupId =
      trace.groupId ??
      (traceDict.groupId as string | null | undefined) ??
      (traceDict.group_id as string | null | undefined);
    if (groupId !== undefined && groupId !== null) {
      (runExtra.metadata as Record<string, unknown>).thread_id = groupId;
    }

    try {
      let newRun: RunTree;
      if (currentRunTree !== undefined) {
        // Nest under existing trace
        newRun = currentRunTree.createChild({
          name: runName,
          run_type: "chain",
          inputs: {},
          extra: runExtra,
          tags: this._tags,
        });
      } else {
        // Create new root trace
        const runTreeConfig: ConstructorParameters<typeof RunTree>[0] = {
          name: runName,
          run_type: "chain",
          inputs: {},
          extra: runExtra,
          tags: this._tags,
          client: this.client,
        };

        if (this._projectName !== undefined) {
          runTreeConfig.project_name = this._projectName;
        }

        newRun = new RunTree(runTreeConfig);
      }

      // Delay posting until first response/generation span ends
      // so inputs can be included in the POST.
      this._unpostedTraces.add(trace.traceId);
      this._runs.set(trace.traceId, newRun);

      // Set this run as the current context so nested traceable() calls
      // invoked from inside Agents tools nest under it. Remember the previous
      // store so we can restore it in onTraceEnd.
      const previousStore = enterRunTreeContext(newRun);
      this._previousStoreByTrace.set(trace.traceId, previousStore);
    } catch (e) {
      console.error("Error creating trace run:", e);
    }
  }

  async onTraceEnd(trace: Trace): Promise<void> {
    const run = this._runs.get(trace.traceId);
    if (!run) {
      return;
    }

    this._runs.delete(trace.traceId);

    const traceDict = (trace.toJSON() as Record<string, unknown>) ?? {};
    const metadata = {
      ...(traceDict.metadata as Record<string, unknown>),
      ...this._metadata,
    };

    try {
      // Update run with final inputs/outputs
      run.outputs = this._lastResponseOutputs[trace.traceId] ?? {};

      // Update metadata
      if (!run.extra) {
        run.extra = {};
      }
      if (!run.extra.metadata) {
        run.extra.metadata = {};
      }
      run.extra.metadata = {
        ...run.extra.metadata,
        ...metadata,
      };

      // End and patch
      await run.end();

      if (this._unpostedTraces.has(trace.traceId)) {
        // No response/generation spans ended, post now
        run.inputs = this._firstResponseInputs[trace.traceId] ?? {};
        this._unpostedTraces.delete(trace.traceId);
        await run.postRun();
      } else {
        await run.patchRun({ excludeInputs: true });
      }

      delete this._firstResponseInputs[trace.traceId];
      delete this._lastResponseOutputs[trace.traceId];
    } catch (e) {
      console.error("Error updating trace run:", e);
    } finally {
      // Restore the previous AsyncLocalStorage store so contexts outside
      // this trace are not polluted.
      if (this._previousStoreByTrace.has(trace.traceId)) {
        const previousStore = this._previousStoreByTrace.get(trace.traceId);
        this._previousStoreByTrace.delete(trace.traceId);
        enterRunTreeContext(previousStore);
      }
    }
  }

  async onSpanStart(span: Span): Promise<void> {
    // Find parent run
    const parentId = span.parentId;
    const parentRun = parentId
      ? this._runs.get(parentId)
      : this._runs.get(span.traceId);

    if (!parentRun) {
      console.warn(`No trace info found for span, skipping: ${span.spanId}`);
      return;
    }

    // Extract span data
    let runName = getRunName(span);
    const spanData = span.spanData;

    if (spanData.type === "response") {
      const parentName = parentRun.name;
      const rawSpanName = runName;
      if (parentName) {
        runName = `${parentName} ${rawSpanName}`.trim();
      } else {
        runName = rawSpanName;
      }
    }

    const runType = getRunType(span);
    const extracted = extractSpanData(span);

    // Create child run and install it into AsyncLocalStorage SYNCHRONOUSLY,
    // before any `await`. The OpenAI Agents runtime invokes `span.start()`
    // (which calls this method without awaiting) right before it executes
    // the tool/agent body in the same async task. Setting ALS via
    // `enterWith` here ensures nested `traceable()` calls inside tool
    // `execute` functions see this span's RunTree as their parent.
    let childRun: RunTree;
    try {
      childRun = parentRun.createChild({
        name: runName,
        run_type: runType,
        inputs: (extracted.inputs as Record<string, unknown>) ?? {},
        extra: extracted,
        start_time: span.startedAt
          ? new Date(span.startedAt).getTime()
          : undefined,
      });
    } catch (e) {
      console.error("Error creating span run:", e);
      return;
    }

    // Add ls_agent_type metadata for agent spans that are children of
    // function spans (i.e., agents used as tools).
    // Handoff agents are not considered subagents.
    if (spanData.type === "agent") {
      const parentSpanType = parentId
        ? this._spanDataTypes.get(parentId)
        : undefined;
      if (parentSpanType === "function") {
        if (!childRun.extra) {
          childRun.extra = {};
        }
        if (!childRun.extra.metadata) {
          childRun.extra.metadata = {};
        }
        childRun.extra.metadata = {
          ...childRun.extra.metadata,
          ls_agent_type: "subagent",
        };
      }
    }

    // Track span data type for parent lookups
    this._spanDataTypes.set(span.spanId, spanData.type);
    this._runs.set(span.spanId, childRun);

    // Enter AsyncLocalStorage context synchronously so nested traceable()
    // calls inside the span's body nest under this run. Remember the
    // previous store so we can restore it in onSpanEnd.
    const previousStore = enterRunTreeContext(childRun);
    this._previousStoreBySpan.set(span.spanId, previousStore);

    try {
      // Delay posting for spans whose complete inputs/outputs aren't
      // available at start.
      if (
        spanData.type === "generation" ||
        spanData.type === "response" ||
        spanData.type === "function" ||
        spanData.type === "handoff"
      ) {
        this._unpostedSpans.add(span.spanId);
      } else {
        await childRun.postRun();
      }
    } catch (e) {
      console.error("Error posting span run:", e);
    }
  }

  async onSpanEnd(span: Span): Promise<void> {
    // Restore the previous AsyncLocalStorage store synchronously so any
    // further async work in the enclosing scope doesn't see this span's
    // run as its parent. Done before any await to match span.end()
    // which fires onSpanEnd without awaiting.
    if (this._previousStoreBySpan.has(span.spanId)) {
      const previousStore = this._previousStoreBySpan.get(span.spanId);
      this._previousStoreBySpan.delete(span.spanId);
      enterRunTreeContext(previousStore);
    }

    const run = this._runs.get(span.spanId);
    this._spanDataTypes.delete(span.spanId);

    if (!run) {
      return;
    }

    this._runs.delete(span.spanId);

    try {
      // Extract outputs and metadata
      const extracted = extractSpanData(span);
      const outputs = (extracted.outputs as Record<string, unknown>) ?? {};
      const inputs = (extracted.inputs as Record<string, unknown>) ?? {};

      // Update run
      run.outputs = outputs;
      if (Object.keys(inputs).length > 0) {
        run.inputs = inputs;
      }
      if (span.error) {
        run.error = span.error.message;
      }

      if (span.spanData.type === "agent") {
        const derived = deriveAgentInputsOutputs(run);
        if (
          Object.keys(run.inputs ?? {}).length === 0 &&
          derived.inputs &&
          Object.keys(derived.inputs).length > 0
        ) {
          run.inputs = derived.inputs;
        }
        if (
          Object.keys(run.outputs ?? {}).length === 0 &&
          derived.outputs &&
          Object.keys(derived.outputs).length > 0
        ) {
          run.outputs = derived.outputs;
        }
      }

      // Add OpenAI metadata
      if (!run.extra) {
        run.extra = {};
      }
      if (!run.extra.metadata) {
        run.extra.metadata = {};
      }
      run.extra.metadata = {
        ...run.extra.metadata,
        openai_parent_id: span.parentId ?? undefined,
        openai_trace_id: span.traceId,
        openai_span_id: span.spanId,
      };

      if (extracted.metadata) {
        run.extra.metadata = {
          ...run.extra.metadata,
          ...(extracted.metadata as Record<string, unknown>),
        };
      }
      if (extracted.invocation_params) {
        run.extra.invocation_params = extracted.invocation_params;
      }

      const spanData = span.spanData;
      if (spanData.type === "response") {
        this._firstResponseInputs[span.traceId] =
          this._firstResponseInputs[span.traceId] ?? inputs;
        this._lastResponseOutputs[span.traceId] = outputs;
        await this._maybePostTrace(span.traceId, inputs);
      } else if (spanData.type === "generation") {
        this._firstResponseInputs[span.traceId] =
          this._firstResponseInputs[span.traceId] ?? inputs;
        this._lastResponseOutputs[span.traceId] = outputs;
        await this._maybePostTrace(span.traceId, inputs);
      }

      // End the run
      if (span.endedAt) {
        await run.end(undefined, undefined, new Date(span.endedAt).getTime());
      } else {
        await run.end();
      }

      if (this._unpostedSpans.has(span.spanId)) {
        this._unpostedSpans.delete(span.spanId);
        await run.postRun();
      } else {
        await run.patchRun(
          span.spanData.type === "agent" ? undefined : { excludeInputs: true }
        );
      }
    } catch (e) {
      console.error("Error updating span run:", e);
    }
  }

  private async _maybePostTrace(
    traceId: string,
    inputs: Record<string, unknown>
  ): Promise<void> {
    if (this._unpostedTraces.has(traceId)) {
      const traceRun = this._runs.get(traceId);
      if (traceRun) {
        traceRun.inputs = inputs;
        try {
          await traceRun.postRun();
        } catch (e) {
          console.error("Error posting trace:", e);
        }
        this._unpostedTraces.delete(traceId);
      }
    }
  }

  async shutdown(): Promise<void> {
    await this.client.flush();
    await this.client.awaitPendingTraceBatches();
  }

  async forceFlush(): Promise<void> {
    await this.client.flush();
    await this.client.awaitPendingTraceBatches();
  }
}
