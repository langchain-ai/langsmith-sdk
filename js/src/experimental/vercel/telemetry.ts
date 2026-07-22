import type { ModelMessage, StepResult, Telemetry, TypedToolCall } from "ai";
import { isRunTree, RunTree, RunTreeConfig } from "../../run_trees.js";
import { getCurrentRunTree, withRunTree } from "../../traceable.js";
import { isEnvTracingEnabled } from "../../env.js";
import { convertMessageToTracedFormat } from "./utils.js";
import { setUsageMetadataOnRunTree } from "./utils.js";
import type { KVMap } from "../../schemas.js";
import { isPrimitive, isRecord } from "../../utils/types.js";

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

  /**
   * Whether to enable tracing.
   * @default true if LANGSMITH_TRACING is set to "true"
   */
  tracingEnabled?: boolean;
}

function _formatMessages(messages: ModelMessage[]): Record<string, unknown>[] {
  if (!Array.isArray(messages)) return messages;
  return messages.map((msg) => convertMessageToTracedFormat(msg));
}

// oxlint-disable-next-line typescript/no-explicit-any
function _formatToolCalls(toolCalls: TypedToolCall<any>[]) {
  return toolCalls.map((tc) => ({
    id: tc.toolCallId,
    type: "function",
    function: {
      name: tc.toolName,
      arguments: isPrimitive(tc.input)
        ? String(tc.input)
        : JSON.stringify(tc.input),
    },
  }));
}

function _formatStepOutput(
  // oxlint-disable-next-line typescript/no-explicit-any
  event: StepResult<any, any>,
  traceRawHttp?: boolean,
): KVMap {
  // Build an assistant-style message from the step result
  const output: Record<string, unknown> = { role: "assistant" };

  // Text content
  if (event.content != null) {
    output.content = event.content;
  } else if (event.text != null) {
    output.content = event.text;
  }

  // Tool calls
  if (Array.isArray(event.toolCalls) && event.toolCalls.length > 0) {
    output.tool_calls = _formatToolCalls(event.toolCalls);
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

function _getLsAgentType(parentRunTree: unknown): "subagent" | "root" {
  if (isRunTree(parentRunTree) && parentRunTree.run_type === "tool") {
    return "subagent";
  }
  return "root";
}

function _hasNonzeroUsageMetadata(runTree: RunTree): boolean {
  const usageMetadata = runTree.extra?.metadata?.usage_metadata;
  if (!isRecord(usageMetadata)) return false;

  return ["input_tokens", "output_tokens", "total_tokens"].some(
    (key) => typeof usageMetadata[key] === "number" && usageMetadata[key] > 0,
  );
}

/**
 * Creates a LangSmith `Telemetry` for the Vercel AI SDK.
 *
 * This adapter implements the Vercel AI SDK's `Telemetry` interface
 * and maps lifecycle events to LangSmith traces. It creates a root span for
 * the entire generation, child LLM spans for each step, and tool spans for
 * tool calls.
 *
 * ```ts
 * import { generateText, registerTelemetry } from "ai";
 * import { LangSmithTelemetry } from "langsmith/experimental/vercel";
 *
 * registerTelemetry(LangSmithTelemetry());
 *
 * const result = await generateText({
 *   model: openai("gpt-4o"),
 *   prompt: "Hello!",
 * });
 * ```
 *
 * @experimental Only available in Vercel AI SDK 7.
 */
export function LangSmithTelemetry(
  config?: LangSmithTelemetryConfig,
  // Ignore until Telemetry is released
  // oxlint-disable-next-line typescript/no-explicit-any
): any {
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
    tracingEnabled,
    extra: customExtra,
  } = config ?? {};

  // Per-invocation state. Each generateText/streamText call gets its own
  // context so the same integration object can be reused across calls.
  interface InvocationState {
    rootRunTree: RunTree;
    stepRunTrees: Map<number, RunTree>;
    deferredStepRunTrees: Map<number, RunTree>;
    patchedStepRunIds: Set<string>;
    toolRunTrees: Map<string, RunTree>;
    toolRunPostPromises: Map<string, Promise<void>>;
    lastStepContent: unknown[];
    reconstructStepMessages: boolean;
    completedStepMessages: Record<string, unknown>[];
    toolResults: Map<string, { toolName: string; output: unknown }>;
    pendingToolCalls: Map<string, string>;
    /** Most recently started model step, retained for delayed tool telemetry. */
    latestStepRunTree?: RunTree;
  }

  function formatToolResultMessage(
    toolCallId: string,
    toolName: string,
    toolOutput: unknown,
  ): Record<string, unknown> {
    const rawOutput = isRecord(toolOutput)
      ? toolOutput.type === "tool-result"
        ? toolOutput.output
        : "error" in toolOutput
          ? toolOutput.error
          : toolOutput
      : toolOutput;
    const artifact = rawOutput instanceof Error ? rawOutput.message : rawOutput;
    const content =
      typeof artifact === "string"
        ? artifact
        : (JSON.stringify(artifact) ?? String(artifact));
    return {
      role: "tool",
      content,
      tool_call_id: toolCallId,
      name: toolName,
      artifact,
    };
  }

  function appendToolResultMessage(
    state: InvocationState,
    toolCallId: string,
    toolName: string,
    toolOutput: unknown,
  ): Record<string, unknown> {
    const message = formatToolResultMessage(toolCallId, toolName, toolOutput);
    state.completedStepMessages.push(message);
    return message;
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

  async function patchStepRun(
    state: InvocationState,
    stepRunTree: RunTree,
    options?: { excludeInputs?: boolean },
  ) {
    if (state.patchedStepRunIds.has(stepRunTree.id)) return;
    // Harness dispatches telemetry callbacks without awaiting them, so reserve
    // the one allowed PATCH synchronously before performing network I/O.
    state.patchedStepRunIds.add(stepRunTree.id);
    await stepRunTree.patchRun(options);
  }

  async function flushDeferredStepRuns(state: InvocationState) {
    const entries = Array.from(state.deferredStepRunTrees.entries());
    for (const [stepNumber] of entries) {
      state.deferredStepRunTrees.delete(stepNumber);
    }
    await Promise.all(
      entries.map(([, stepRunTree]) =>
        patchStepRun(state, stepRunTree, { excludeInputs: true }),
      ),
    );
  }

  async function finalizeOpenToolRuns(
    state: InvocationState,
    opts?: { note?: string; error?: string },
  ) {
    const entries = Array.from(state.toolRunTrees.entries());
    for (let i = 0; i < entries.length; i++) {
      const [toolCallId, toolRt] = entries[i];
      await state.toolRunPostPromises.get(toolCallId);
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
    state.toolRunPostPromises.clear();
  }

  /** Per-generation state keyed by AI SDK `callId` (stable across nested calls). */
  const invocationsByCallId = new Map<string, InvocationState>();

  const onStart: Telemetry["onStart"] = async (event) => {
    if (!isEnvTracingEnabled(tracingEnabled)) return;
    if (!("callId" in event) || typeof event.callId !== "string") return;

    // If called within an existing traceable context, nest under it
    const parentRunTree = getCurrentRunTree(true);

    let inputs: KVMap = {};
    if (event.recordInputs !== false) {
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

      if ("runtimeContext" in event && event.runtimeContext != null) {
        inputs.runtimeContext = event.runtimeContext;
      }

      if ("toolsContext" in event && event.toolsContext != null) {
        inputs.toolsContext = event.toolsContext;
      }

      // Apply user-provided input processing
      if (processInputs) {
        try {
          inputs = processInputs(inputs);
        } catch (e) {
          console.error("Error in processInputs, using raw inputs:", e);
        }
      }
    }

    const runTreeConfig: RunTreeConfig = {
      name: customName ?? event.functionId ?? event.provider,
      run_type: runType,
      inputs,
      tracingEnabled: true,
      extra: {
        ...customExtra,
        metadata: {
          ...customMetadata,
          ai_sdk_method: event.operationId,
          ls_agent_type: _getLsAgentType(parentRunTree),
          ls_model_name: event.modelId,
          ls_integration: "vercel-ai-sdk-telemetry",
        },
      },
      tags: customTags,
      ...(client ? { client } : {}),
      ...(projectName ? { project_name: projectName } : {}),
    };

    let rootRunTree: RunTree;
    if (isRunTree(parentRunTree)) {
      rootRunTree = parentRunTree.createChild(runTreeConfig);
    } else {
      rootRunTree = new RunTree(runTreeConfig);
    }
    await rootRunTree.postRun();
    invocationsByCallId.set(event.callId, {
      rootRunTree,
      stepRunTrees: new Map(),
      deferredStepRunTrees: new Map(),
      patchedStepRunIds: new Set(),
      toolRunTrees: new Map(),
      toolRunPostPromises: new Map(),
      lastStepContent: [],
      reconstructStepMessages: event.operationId === "ai.harness",
      completedStepMessages: [],
      toolResults: new Map(),
      pendingToolCalls: new Map(),
    });
  };

  const onStepStart: Telemetry["onStepStart"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    await flushDeferredStepRuns(state);
    const stepNumber: number = event.stepNumber ?? 0;

    let inputs: KVMap = {};
    if (event.recordInputs !== false) {
      if ("messages" in event && event.messages != null) {
        inputs.messages = [
          ..._formatMessages(event.messages),
          ...(state.reconstructStepMessages ? state.completedStepMessages : []),
        ];
      }

      if ("runtimeContext" in event && event.runtimeContext != null) {
        inputs.runtimeContext = event.runtimeContext;
      }

      if ("toolsContext" in event && event.toolsContext != null) {
        inputs.toolsContext = event.toolsContext;
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
    }

    const stepRunTree = state.rootRunTree.createChild({
      name: event.provider,
      run_type: "llm",
      inputs,
      extra: {
        metadata: {
          step_number: stepNumber,
          ls_model_name: event.modelId,
        },
      },
    });

    state.stepRunTrees.set(stepNumber, stepRunTree);
    state.latestStepRunTree = stepRunTree;
    await stepRunTree.postRun();
  };

  const onLanguageModelCallStart: Telemetry["onLanguageModelCallStart"] =
    async (event) => {
      const state = invocationsByCallId.get(event.callId);
      if (!state) return;

      const stepRunTree = getOpenStepOrRoot(state);
      if (stepRunTree.run_type !== "llm") return;

      const prevParams = isRecord(stepRunTree.extra?.invocation_params)
        ? stepRunTree.extra.invocation_params
        : {};

      type AsPlain<T> = { -readonly [K in keyof T]?: T[K] };
      const nextParams: AsPlain<typeof event> = { ...event };

      // Remove properties that are already in the step run tree
      delete nextParams.messages;
      delete nextParams.provider;
      delete nextParams.modelId;

      // Remove telemetry options (except functionId)
      delete nextParams.recordInputs;
      delete nextParams.recordOutputs;
      delete nextParams.includeToolsContext;

      // Massage tools for LangSmith to render schema nicely
      nextParams.tools = nextParams.tools?.map((tool) => {
        const newTool = { ...tool };
        if ("inputSchema" in newTool) {
          newTool.input_schema = newTool.inputSchema;
          delete newTool.inputSchema;
        }
        return newTool;
      });

      stepRunTree.extra = {
        ...stepRunTree.extra,
        invocation_params: { ...prevParams, ...nextParams },
      };
    };

  const onToolExecutionStart: Telemetry["onToolExecutionStart"] = async (
    event,
  ) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const parentRunTree = state.rootRunTree;

    let inputs: KVMap = {};
    if (event.recordInputs !== false) {
      let toolCallInput = event.toolCall.input;
      if (typeof toolCallInput === "string") {
        try {
          toolCallInput = JSON.parse(toolCallInput);
        } catch {
          // The tool argument itself may be a plain string rather than JSON.
        }
      }
      if (isRecord(toolCallInput)) {
        inputs = { ...toolCallInput };
      } else if (toolCallInput !== undefined) {
        inputs = { input: toolCallInput };
      }
    }

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
    // Register before posting because HarnessAgent does not await telemetry
    // callbacks and may emit tool-end while this POST is still in flight.
    state.toolRunTrees.set(event.toolCall.toolCallId, toolRunTree);
    const postPromise = toolRunTree.postRun();
    state.toolRunPostPromises.set(event.toolCall.toolCallId, postPromise);
    await postPromise;
  };

  const onToolExecutionEnd: Telemetry["onToolExecutionEnd"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const toolRunTree = state.toolRunTrees.get(event.toolCall.toolCallId);
    if (!toolRunTree) return;
    await state.toolRunPostPromises.get(event.toolCall.toolCallId);

    if (state.reconstructStepMessages) {
      const pendingToolName = state.pendingToolCalls.get(
        event.toolCall.toolCallId,
      );
      if (pendingToolName != null) {
        const toolMessage = appendToolResultMessage(
          state,
          event.toolCall.toolCallId,
          pendingToolName,
          event.toolOutput,
        );
        state.pendingToolCalls.delete(event.toolCall.toolCallId);

        // HarnessAgent may finish the next model step before its asynchronous
        // tool-end telemetry callback completes. Retain and update the latest
        // step if it was invoked with the corresponding assistant tool call.
        const latestStep = state.latestStepRunTree;
        const messages = latestStep?.inputs.messages;
        if (
          latestStep?.run_type === "llm" &&
          Array.isArray(messages) &&
          messages.some(
            (message) =>
              isRecord(message) &&
              message.role === "assistant" &&
              JSON.stringify(message).includes(event.toolCall.toolCallId),
          ) &&
          !messages.some(
            (message) =>
              isRecord(message) &&
              message.role === "tool" &&
              JSON.stringify(message).includes(event.toolCall.toolCallId),
          )
        ) {
          latestStep.inputs = {
            ...latestStep.inputs,
            messages: [...messages, toolMessage],
          };
        }
      } else {
        state.toolResults.set(event.toolCall.toolCallId, {
          toolName: event.toolCall.toolName,
          output: event.toolOutput,
        });
      }
    }

    let outputs: KVMap | undefined;
    let error: string | undefined;

    if (event.recordOutputs !== false) {
      if (event.toolOutput.type === "tool-result") {
        outputs = { output: event.toolOutput.output };
      } else if (isRecord(event.toolOutput) && "error" in event.toolOutput) {
        const err = event.toolOutput.error;
        error = err instanceof Error ? err.message : String(err);
      }
    } else {
      outputs = {};
    }

    await toolRunTree.end(
      outputs,
      error,
      Math.floor(toolRunTree.start_time + event.toolExecutionMs),
    );
    await toolRunTree.patchRun({ excludeInputs: true });
    state.toolRunTrees.delete(event.toolCall.toolCallId);
    state.toolRunPostPromises.delete(event.toolCall.toolCallId);
  };

  const onStepFinish: Telemetry["onStepFinish"] = async (event) => {
    const state = invocationsByCallId.get(event.callId);
    if (!state) return;

    const stepNumber: number = event.stepNumber ?? 0;
    const stepRunTree = state.stepRunTrees.get(stepNumber);
    if (!stepRunTree) return;

    let outputs = {};
    if (event.recordOutputs !== false) {
      if (Array.isArray(event.content)) {
        state.lastStepContent = [...event.content];
      }
      outputs = _formatStepOutput(event, traceRawHttp);

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
    }

    if (state.reconstructStepMessages && Array.isArray(event.content)) {
      state.completedStepMessages.push(
        convertMessageToTracedFormat({
          role: "assistant",
          content: event.content,
        }),
      );

      for (const part of event.content) {
        if (
          !isRecord(part) ||
          part.type !== "tool-call" ||
          typeof part.toolCallId !== "string"
        ) {
          continue;
        }
        const toolResult = state.toolResults.get(part.toolCallId);
        if (toolResult) {
          appendToolResultMessage(
            state,
            part.toolCallId,
            toolResult.toolName,
            toolResult.output,
          );
          state.toolResults.delete(part.toolCallId);
        } else {
          state.pendingToolCalls.set(
            part.toolCallId,
            typeof part.toolName === "string" ? part.toolName : "tool",
          );
        }
      }
    }

    // Set usage metadata
    // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
    setUsageMetadataOnRunTree(event, stepRunTree);

    await stepRunTree.end(outputs);
    if (
      state.reconstructStepMessages &&
      !_hasNonzeroUsageMetadata(stepRunTree)
    ) {
      // Pi reports zero usage for inferred step boundaries and sends the real
      // aggregate at turn end. Defer the final PATCH so that aggregate can be
      // attached to the last LLM run without issuing a duplicate update.
      state.deferredStepRunTrees.set(stepNumber, stepRunTree);
    } else {
      await patchStepRun(state, stepRunTree, { excludeInputs: true });
    }
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
        if (
          state.reconstructStepMessages &&
          !_hasNonzeroUsageMetadata(stepRt)
        ) {
          state.deferredStepRunTrees.set(stepNumber, stepRt);
        } else {
          await patchStepRun(state, stepRt, { excludeInputs: true });
        }
      }
      state.stepRunTrees.delete(stepNumber);
    }

    let outputs: KVMap = {};

    if (event.recordOutputs !== false) {
      // Final result output
      if ("text" in event && event.text != null) {
        outputs.content = event.text;
      } else if (
        "content" in event &&
        event.content != null &&
        (!Array.isArray(event.content) || event.content.length > 0)
      ) {
        outputs.content = event.content;
      } else if (
        state.reconstructStepMessages &&
        state.lastStepContent.length > 0
      ) {
        // HarnessAgent currently reports an empty root `content` array even
        // though each completed step contains assistant output. Only the final
        // step belongs on the root; prior steps have their own child runs.
        outputs.content = state.lastStepContent;
      }

      if (outputs.content != null) {
        outputs.role = "assistant";
      }

      if ("object" in event && event.object != null) {
        outputs.object = event.object;
      }

      if (
        "toolCalls" in event &&
        Array.isArray(event.toolCalls) &&
        event.toolCalls.length > 0
      ) {
        outputs.tool_calls = _formatToolCalls(event.toolCalls);
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

      if (processOutputs) {
        try {
          outputs = processOutputs(outputs);
        } catch (e) {
          console.error("Error in processOutputs, using raw outputs:", e);
        }
      }
    }

    // Harness integrations such as Pi may report zero usage on inferred step
    // boundaries and provide the actual aggregate only when the turn ends. Keep
    // that usage on an LLM run rather than incorrectly elevating it to the
    // parent chain. The latest step is the only accurate place available for
    // this aggregate when the harness does not report per-step usage.
    const latestStep = state.latestStepRunTree;
    if (
      state.reconstructStepMessages &&
      latestStep?.run_type === "llm" &&
      !_hasNonzeroUsageMetadata(latestStep)
    ) {
      if ("totalUsage" in event && event.totalUsage != null) {
        setUsageMetadataOnRunTree(
          // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
          { usage: event.totalUsage, providerMetadata: event.providerMetadata },
          latestStep,
        );
      } else if ("usage" in event && event.usage != null) {
        // @ts-expect-error SharedV4ProviderMetadata is not assignable to SharedV2ProviderMetadata
        setUsageMetadataOnRunTree(event, latestStep);
      }
    }

    await rootRunTree.end(outputs);
    await Promise.all([
      flushDeferredStepRuns(state),
      rootRunTree.patchRun({ excludeInputs: true }),
    ]);

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
        await patchStepRun(state, stepRt, { excludeInputs: true });
      }
      state.stepRunTrees.delete(stepNumber);
    }
    await flushDeferredStepRuns(state);

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
    onLanguageModelCallStart,
    onToolExecutionStart,
    onToolExecutionEnd,
    onStepFinish,
    onEnd,
    onError,
    executeTool,
  } satisfies Telemetry;
}
