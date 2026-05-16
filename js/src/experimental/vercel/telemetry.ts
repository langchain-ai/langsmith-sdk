import type { Telemetry } from "ai";
import { RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, withRunTree } from "../../singletons/traceable.js";
import { isTracingEnabled } from "../../env.js";
import { convertMessageToTracedFormat } from "./utils.js";
import { setUsageMetadataOnRunTree } from "./middleware.js";
import type { KVMap } from "../../schemas.js";
import { isRecord } from "../../utils/types.js";

/**
 * Configuration options for creating a LangSmith telemetry integration
 * for the Vercel AI SDK.
 */
export interface LangSmithTelemetryConfig {
  /**
   * Custom name for the root span. If not provided, defaults to the
   * model display name or "generateText"/"streamText".
   */
  name?: string;

  /**
   * Run type for the root span. Defaults to "chain".
   */
  runType?: string;

  /**
   * Additional metadata to attach to all spans.
   */
  metadata?: KVMap;

  /**
   * Tags to attach to all spans.
   */
  tags?: string[];

  /**
   * Custom LangSmith client configuration.
   */
  client?: RunTreeConfig["client"];

  /**
   * Project name to log runs to.
   */
  projectName?: string;

  /**
   * Transform inputs before logging on the root span.
   */
  processInputs?: (inputs: KVMap) => KVMap;

  /**
   * Transform outputs before logging on the root span.
   */
  processOutputs?: (outputs: KVMap) => KVMap;

  /**
   * Transform inputs before logging on child LLM step spans.
   */
  processChildLLMRunInputs?: (inputs: KVMap) => KVMap;

  /**
   * Transform outputs before logging on child LLM step spans.
   */
  processChildLLMRunOutputs?: (outputs: KVMap) => KVMap;

  /**
   * Whether to include intermediate step details in the output.
   */
  traceResponseMetadata?: boolean;

  /**
   * Whether to include raw HTTP request/response bodies.
   */
  traceRawHttp?: boolean;

  /**
   * Additional RunTree configuration to pass through.
   */
  extra?: KVMap;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function _formatMessages(messages: any[]): any[] {
  if (!Array.isArray(messages)) return messages;
  return messages.map((msg) => convertMessageToTracedFormat(msg));
}

function _formatStepOutput(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  event: Record<string, any>,
  traceRawHttp?: boolean,
): KVMap {
  // Build an assistant-style message from the step result
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const output: Record<string, any> = {
    role: "assistant",
  };

  // Text content
  if (event.text != null) {
    output.content = event.text;
  } else if (event.content != null) {
    output.content = event.content;
  }

  // Tool calls
  if (Array.isArray(event.toolCalls) && event.toolCalls.length > 0) {
    output.tool_calls = event.toolCalls.map(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (tc: any) => ({
        id: tc.toolCallId,
        type: "function",
        function: {
          name: tc.toolName,
          arguments:
            typeof tc.args === "string" ? tc.args : JSON.stringify(tc.args),
        },
      }),
    );
  }

  if (event.finishReason != null) {
    output.finish_reason = event.finishReason;
  }

  if (traceRawHttp) {
    if (event.request != null) output.request = event.request;
    if (event.response != null) output.response = event.response;
  }

  return convertMessageToTracedFormat(output) as KVMap;
}

/**
 * Creates a LangSmith `TelemetryIntegration` for the Vercel AI SDK.
 *
 * This adapter implements the Vercel AI SDK's `TelemetryIntegration` interface
 * and maps lifecycle events to LangSmith traces. It creates a root span for
 * the entire generation, child LLM spans for each step, and tool spans for
 * tool calls.
 *
 * The integration object is **reusable** — create it once and pass it to
 * multiple `generateText`/`streamText` calls. Each call gets its own
 * isolated trace state. State is keyed by the AI SDK `callId`, so nested
 * `generateText` / `streamText` calls can safely share one integration instance.
 *
 * ```ts
 * import { generateText } from "ai";
 * import { createLangSmithTelemetry } from "langsmith/experimental/vercel";
 *
 * const telemetry = createLangSmithTelemetry();
 *
 * // Reuse across multiple calls
 * const result1 = await generateText({
 *   model: openai("gpt-4o"),
 *   prompt: "Hello!",
 *   experimental_telemetry: { integrations: [telemetry] },
 * });
 *
 * const result2 = await generateText({
 *   model: openai("gpt-4o"),
 *   prompt: "Goodbye!",
 *   experimental_telemetry: { integrations: [telemetry] },
 * });
 * ```
 *
 * Tool spans are created in `onToolExecutionStart`, execution runs under
 * `withRunTree` via `executeTool` for nesting, and `onToolExecutionEnd`
 * records outputs or errors (including tool results not visible to `executeTool`
 * alone).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createLangSmithTelemetry(
  config?: LangSmithTelemetryConfig,
): Telemetry {
  const {
    name: customName,
    runType = "chain",
    metadata: customMetadata,
    tags: customTags,
    client,
    projectName,
    processInputs,
    processOutputs,
    processChildLLMRunInputs,
    processChildLLMRunOutputs,
    traceResponseMetadata,
    traceRawHttp,
    extra: customExtra,
  } = config ?? {};

  // Per-invocation state. Each generateText/streamText call gets its own
  // context so the same integration object can be reused across calls.
  interface InvocationState {
    rootRunTree: RunTree;
    stepRunTrees: Map<number, RunTree>;
    toolRunTrees: Map<string, RunTree>;
  }

  function getOpenStepOrRoot(state: InvocationState): RunTree {
    let openStep: RunTree | undefined;
    state.stepRunTrees.forEach((stepRt) => {
      if (stepRt.end_time == null) {
        openStep = stepRt;
      }
    });
    return openStep ?? state.rootRunTree;
  }

  async function finalizeOpenToolRuns(
    state: InvocationState,
    opts?: { note?: string; error?: string },
  ) {
    const entries = Array.from(state.toolRunTrees.entries());
    for (let i = 0; i < entries.length; i++) {
      const [, toolRt] = entries[i];
      if (toolRt.end_time == null) {
        if (opts?.error != null) {
          await toolRt.end(undefined, opts.error);
        } else {
          await toolRt.end(
            opts?.note != null ? { note: opts.note } : undefined,
          );
        }
        await toolRt.patchRun({ excludeInputs: true });
      }
    }
    state.toolRunTrees.clear();
  }

  /** Per-generation state keyed by AI SDK `callId` (stable across nested calls). */
  const invocationsByCallId = new Map<string, InvocationState>();

  const onStart: Telemetry["onStart"] = async (event) => {
    if (!isTracingEnabled()) return;
    if (!("callId" in event) || typeof event.callId !== "string") return;

    // If called within an existing traceable context, nest under it
    const parentRunTree = getCurrentRunTree(true);

    let inputs: KVMap = {};
    if ("messages" in event && event.messages != null) {
      inputs.messages = _formatMessages(event.messages);
    }

    if ("prompt" in event && event.prompt != null) {
      inputs.prompt = event.prompt;
    }

    if ("instructions" in event && event.instructions != null) {
      inputs.instructions = event.instructions;
    }

    if ("system" in event && event.system != null) {
      inputs.system = event.system;
    }

    if ("tools" in event && event.tools != null) {
      inputs.tools = Object.keys(event.tools);
    }

    // Apply user-provided input processing
    if (processInputs) {
      try {
        inputs = processInputs(inputs);
      } catch (e) {
        console.error("Error in processInputs, using raw inputs:", e);
      }
    }

    const runTreeConfig: RunTreeConfig = {
      name: customName ?? event.provider,
      run_type: runType,
      inputs,
      extra: {
        ...customExtra,
        metadata: {
          ...customMetadata,
          ls_model_name: event.modelId,
          ls_provider: event.provider,
          ls_integration: "vercel-ai-sdk-telemetry",
        },
      },
      tags: customTags,
      ...(client ? { client } : {}),
      ...(projectName ? { project_name: projectName } : {}),
    };

    let rootRunTree: RunTree;
    if (parentRunTree != null) {
      rootRunTree = parentRunTree.createChild(runTreeConfig);
    } else {
      rootRunTree = new RunTree(runTreeConfig);
    }
    await rootRunTree.postRun();
    invocationsByCallId.set(event.callId, {
      rootRunTree,
      stepRunTrees: new Map(),
      toolRunTrees: new Map(),
    });
  };

  const onStepStart: Telemetry["onStepStart"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const stepNumber: number = event.stepNumber ?? 0;

    let inputs: KVMap = {};
    if ("messages" in event && event.messages != null) {
      inputs.messages = _formatMessages(event.messages);
    }

    if (processChildLLMRunInputs) {
      try {
        inputs = processChildLLMRunInputs(inputs);
      } catch (e) {
        console.error(
          "Error in processChildLLMRunInputs, using raw inputs:",
          e,
        );
      }
    }

    const stepRunTree = state.rootRunTree.createChild({
      name: `step ${stepNumber}`,
      run_type: "llm",
      inputs,
      extra: {
        metadata: {
          ai_sdk_method: "ai.step",
          step_number: stepNumber,
        },
      },
    });

    state.stepRunTrees.set(stepNumber, stepRunTree);
    await stepRunTree.postRun();
  };

  const onToolExecutionStart: Telemetry["onToolExecutionStart"] = async (
    event,
  ) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const parentRunTree = getOpenStepOrRoot(state);

    const inputs = isRecord(event.toolCall.input)
      ? { ...event.toolCall.input }
      : typeof event.toolCall.input !== "undefined"
        ? { input: event.toolCall.input }
        : {};

    const toolRunTree = parentRunTree.createChild({
      name: event.toolCall.toolName,
      run_type: "tool",
      inputs,
      extra: {
        metadata: {
          tool_call_id: event.toolCall.toolCallId,
          ai_sdk_call_id: event.callId,
        },
      },
    });
    await toolRunTree.postRun();
    state.toolRunTrees.set(event.toolCall.toolCallId, toolRunTree);
  };

  const onToolExecutionEnd: Telemetry["onToolExecutionEnd"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const toolRunTree = state.toolRunTrees.get(event.toolCall.toolCallId);
    if (!toolRunTree) return;
    state.toolRunTrees.delete(event.toolCall.toolCallId);

    let outputs: KVMap | undefined;
    let error: string | undefined;

    if (event.toolOutput.type === "tool-result") {
      outputs = { output: event.toolOutput.output };
    } else if (event.toolOutput.type === "tool-error") {
      const err = event.toolOutput.error;
      error = err instanceof Error ? err.message : String(err);
    }

    await toolRunTree.end(
      outputs,
      error,
      Math.floor(toolRunTree.start_time + event.toolExecutionMs),
    );
    await toolRunTree.patchRun({ excludeInputs: true });
  };

  const onChunk: Telemetry["onChunk"] = (_event) => {
    // For streaming: we could add new_token events, but the step's
    // onStepFinish will capture the full output. We add a streaming
    // event marker on the step run tree if it exists.
    // Currently a no-op; the step finish will capture aggregated output.
  };

  const onStepFinish: Telemetry["onStepFinish"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const stepNumber: number = event.stepNumber ?? 0;
    const stepRunTree = state.stepRunTrees.get(stepNumber);
    if (!stepRunTree) return;

    let outputs = _formatStepOutput(event, traceRawHttp);

    if (processChildLLMRunOutputs) {
      try {
        outputs = processChildLLMRunOutputs(outputs);
      } catch (e) {
        console.error(
          "Error in processChildLLMRunOutputs, using raw outputs:",
          e,
        );
      }
    }

    // Set usage metadata
    // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
    setUsageMetadataOnRunTree(event, stepRunTree);

    await stepRunTree.end(outputs);
    await stepRunTree.patchRun({ excludeInputs: true });
    state.stepRunTrees.delete(stepNumber);
  };

  const onEnd: Telemetry["onEnd"] = async (event) => {
    if (!("callId" in event) || typeof event.callId !== "string") return;
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const { rootRunTree } = state;
    await finalizeOpenToolRuns(state, { note: "closed on finish" });

    // Ensure any remaining step runs are closed
    const remainingSteps = Array.from(state.stepRunTrees.entries());
    for (let i = 0; i < remainingSteps.length; i++) {
      const [stepNumber, stepRt] = remainingSteps[i];
      if (stepRt.end_time == null) {
        await stepRt.end({ note: "closed on finish" });
        await stepRt.patchRun({ excludeInputs: true });
      }
      state.stepRunTrees.delete(stepNumber);
    }

    let outputs: KVMap = {};

    // Final result output
    if ("text" in event && event.text != null) {
      outputs.content = event.text;
    } else if ("content" in event && event.content != null) {
      outputs.content = event.content;
    }

    if ("object" in event && event.object != null) {
      outputs.object = event.object;
    }

    if (
      "toolCalls" in event &&
      Array.isArray(event.toolCalls) &&
      event.toolCalls.length > 0
    ) {
      outputs.tool_calls = event.toolCalls.map(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (tc: any) => ({
          id: tc.toolCallId,
          type: "function",
          function: {
            name: tc.toolName,
            arguments:
              typeof tc.args === "string" ? tc.args : JSON.stringify(tc.args),
          },
        }),
      );
    }

    if ("finishReason" in event && event.finishReason != null) {
      outputs.finish_reason = event.finishReason;
    }

    if (
      traceResponseMetadata &&
      "steps" in event &&
      Array.isArray(event.steps)
    ) {
      outputs.steps = event.steps.map((step, idx) => ({
        step_number: idx,
        ..._formatStepOutput(step, traceRawHttp),
      }));
    }

    // Set aggregated usage on root
    if ("totalUsage" in event && event.totalUsage != null) {
      setUsageMetadataOnRunTree(
        // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
        { usage: event.totalUsage, providerMetadata: event.providerMetadata },
        rootRunTree,
      );
    } else if ("usage" in event && event.usage != null) {
      // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
      setUsageMetadataOnRunTree(event, rootRunTree);
    }

    if (processOutputs) {
      try {
        outputs = processOutputs(outputs);
      } catch (e) {
        console.error("Error in processOutputs, using raw outputs:", e);
      }
    }

    await rootRunTree.end(outputs);
    await rootRunTree.patchRun({ excludeInputs: true });

    invocationsByCallId.delete(event.callId);
  };

  const onError: Telemetry["onError"] = async (payload) => {
    const callId =
      typeof payload === "object" &&
      payload !== null &&
      "callId" in payload &&
      typeof (payload as { callId: unknown }).callId === "string"
        ? (payload as { callId: string }).callId
        : undefined;
    const error =
      typeof payload === "object" && payload !== null && "error" in payload
        ? (payload as { error: unknown }).error
        : payload;

    if (callId === undefined) return;
    const state = invocationsByCallId.get(callId);
    if (!state) return;

    const { rootRunTree } = state;

    const errorMsg = error instanceof Error ? error.message : String(error);
    await finalizeOpenToolRuns(state, { error: errorMsg });

    // Close any open step runs with error
    const errorSteps = Array.from(state.stepRunTrees.entries());
    for (let i = 0; i < errorSteps.length; i++) {
      const [stepNumber, stepRt] = errorSteps[i];
      if (stepRt.end_time == null) {
        await stepRt.end(undefined, errorMsg);
        await stepRt.patchRun({ excludeInputs: true });
      }
      state.stepRunTrees.delete(stepNumber);
    }

    await rootRunTree.end(undefined, errorMsg);
    await rootRunTree.patchRun({ excludeInputs: true });

    invocationsByCallId.delete(callId);
  };

  const executeTool: Telemetry["executeTool"] = async <T>(params: {
    callId: string;
    toolCallId: string;
    execute: () => PromiseLike<T>;
  }): Promise<T> => {
    const state = invocationsByCallId.get(params.callId);

    const toolRunTree = state?.toolRunTrees.get(params.toolCallId);
    if (toolRunTree != null) {
      return withRunTree(toolRunTree, () => params.execute()) as Promise<T>;
    }

    return params.execute() as Promise<T>;
  };

  return {
    onStart,
    onStepStart,
    onToolExecutionStart,
    onToolExecutionEnd,
    onChunk,
    onStepFinish,
    onEnd,
    onError,
    executeTool,
  };
}
