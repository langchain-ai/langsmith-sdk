import type { Telemetry } from "ai";
import { RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, withRunTree } from "../../singletons/traceable.js";
import { traceable } from "../../traceable.js";
import { isTracingEnabled } from "../../env.js";
import {
  convertMessageToTracedFormat,
  getModelDisplayName,
  getModelId,
} from "./utils.js";
import { setUsageMetadataOnRunTree } from "./middleware.js";
import type { KVMap } from "../../schemas.js";

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
 * isolated trace state.
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
 * The `executeToolCall` hook ensures that any `generateText`/`streamText`
 * calls made inside a tool's `execute` function are properly nested as
 * children of the tool span, enabling full sub-agent tracing.
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
    toolCallMetadata: Map<string, { toolName: string; args: unknown }>;
  }

  // Active invocations keyed by rootRunTree.id.
  // For sequential reuse, there is at most one entry at a time.
  // For concurrent reuse (parallel generateText calls sharing one integration),
  // each gets its own entry.
  const invocations = new Map<string, InvocationState>();

  // Points to the most recently started invocation. Used by hooks that
  // the AI SDK calls without an invocation identifier so we can route
  // them to the correct state. For sequential usage this is always correct.
  // For concurrent usage this is a best-effort heuristic — callers doing
  // truly concurrent generateText through a single integration should create
  // separate instances.
  let activeInvocationId: string | undefined;

  const onStart: Telemetry["onStart"] = (event) => {
    if (!isTracingEnabled()) return;

    const modelName = getModelDisplayName(event.model);
    const modelId = getModelId(event.model);

    // If called within an existing traceable context, nest under it
    const parentRunTree = getCurrentRunTree(true);

    let inputs: KVMap = {};
    if (event.messages != null) {
      inputs.messages = _formatMessages(event.messages);
    }
    if (event.prompt != null) {
      inputs.prompt = event.prompt;
    }
    if (event.system != null) {
      inputs.system = event.system;
    }
    if (event.tools != null) {
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
      name: customName ?? modelName,
      run_type: runType,
      inputs,
      extra: {
        ...customExtra,
        metadata: {
          ...customMetadata,
          ls_model_name: modelId,
          ls_provider: modelName,
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
    void rootRunTree.postRun();

    const invocationId = rootRunTree.id;
    invocations.set(invocationId, {
      rootRunTree,
      stepRunTrees: new Map(),
      toolCallMetadata: new Map(),
    });
    activeInvocationId = invocationId;
  };

  const onStepStart: Telemetry["onStepStart"] = (event) => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;
    if (!state) return;

    const stepNumber: number = event.stepNumber ?? 0;

    let inputs: KVMap = {};
    if (event.messages != null) {
      inputs.messages = _formatMessages(event.messages);
    }
    if (event.request != null && traceRawHttp) {
      inputs.request = event.request;
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
    void stepRunTree.postRun();
  };

  const onToolExecutionStart: Telemetry["onToolExecutionStart"] = (event) => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;
    if (!state) return;

    // Stash metadata so executeToolCall can use it for the traceable wrapper
    const toolCallId: string = event.toolCallId;
    state.toolCallMetadata.set(toolCallId, {
      toolName: event.toolName,
      args: event.args,
    });
  };

  const onChunk: Telemetry["onChunk"] = (_event) => {
    // For streaming: we could add new_token events, but the step's
    // onStepFinish will capture the full output. We add a streaming
    // event marker on the step run tree if it exists.
    // Currently a no-op; the step finish will capture aggregated output.
  };

  const onStepFinish: Telemetry["onStepFinish"] = async (event) => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;
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
    setUsageMetadataOnRunTree(event, stepRunTree);

    await stepRunTree.end(outputs);
    await stepRunTree.patchRun({ excludeInputs: true });
    state.stepRunTrees.delete(stepNumber);
  };

  const onEnd: Telemetry["onEnd"] = async (event) => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;
    if (!state) return;

    const { rootRunTree } = state;

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
    if (event.text != null) {
      outputs.content = event.text;
    } else if (event.content != null) {
      outputs.content = event.content;
    }

    if (event.object != null) {
      outputs.object = event.object;
    }

    if (Array.isArray(event.toolCalls) && event.toolCalls.length > 0) {
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

    if (event.finishReason != null) {
      outputs.finish_reason = event.finishReason;
    }

    if (traceResponseMetadata && Array.isArray(event.steps)) {
      outputs.steps = event.steps.map(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (step: any, idx: number) => ({
          step_number: idx,
          ..._formatStepOutput(step, traceRawHttp),
        }),
      );
    }

    // Set aggregated usage on root
    if (event.totalUsage != null) {
      setUsageMetadataOnRunTree(
        { usage: event.totalUsage, providerMetadata: event.providerMetadata },
        rootRunTree,
      );
    } else if (event.usage != null) {
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

    // Clean up this invocation's state
    invocations.delete(activeInvocationId!);
    activeInvocationId = undefined;
  };

  const onError: Telemetry["onError"] = async (error) => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;
    if (!state) return;

    const { rootRunTree } = state;

    // Close any open step runs with error
    const errorSteps = Array.from(state.stepRunTrees.entries());
    for (let i = 0; i < errorSteps.length; i++) {
      const [stepNumber, stepRt] = errorSteps[i];
      if (stepRt.end_time == null) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        await stepRt.end(undefined, errorMsg);
        await stepRt.patchRun({ excludeInputs: true });
      }
      state.stepRunTrees.delete(stepNumber);
    }

    const errorMsg = error instanceof Error ? error.message : String(error);
    await rootRunTree.end(undefined, errorMsg);
    await rootRunTree.patchRun({ excludeInputs: true });

    // Clean up this invocation's state
    invocations.delete(activeInvocationId!);
    activeInvocationId = undefined;
  };

  const executeTool: Telemetry["executeTool"] = async <T>(params: {
    callId: string;
    toolCallId: string;
    execute: () => PromiseLike<T>;
  }): Promise<T> => {
    const state = activeInvocationId
      ? invocations.get(activeInvocationId)
      : undefined;

    const metadata = state?.toolCallMetadata.get(params.toolCallId);
    state?.toolCallMetadata.delete(params.toolCallId);

    const toolName = metadata?.toolName ?? "tool";
    const toolArgs = metadata?.args;

    // Find the active step to use as the parent context.
    // withRunTree sets the ALS context so traceable creates
    // the tool span as a child of that step.
    let activeStep: RunTree | undefined;
    state?.stepRunTrees.forEach((stepRt) => {
      if (stepRt.end_time == null) {
        activeStep = stepRt;
      }
    });
    const parentRunTree = activeStep ?? state?.rootRunTree;

    // Wrap the tool execute with traceable so:
    // 1. A "tool" run is created in LangSmith
    // 2. The ALS context is set to the tool run, so any nested
    //    generateText/streamText calls become children of the tool
    const traceableExecute = traceable(
      async (_args: unknown) => {
        return params.execute();
      },
      {
        name: toolName,
        run_type: "tool",
        metadata: {
          tool_call_id: params.toolCallId,
        },
      },
    );

    if (parentRunTree) {
      return withRunTree(parentRunTree, () =>
        traceableExecute(toolArgs),
      ) as Promise<T>;
    }

    // Fallback: no parent context, still trace the tool
    return traceableExecute(toolArgs) as Promise<T>;
  };

  return {
    onStart,
    onStepStart,
    onToolExecutionStart,
    onChunk,
    onStepFinish,
    onEnd,
    onError,
    executeTool,
  };
}
