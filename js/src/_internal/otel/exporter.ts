import { getEnvironmentVariable } from "../../utils/env.js";
import type { KVMap, Run, RunCreate, RunUpdate } from "../../schemas.js";

let HAS_OTEL = false;

try {
  if (getEnvironmentVariable("OTEL_ENABLED") === "true") {
    HAS_OTEL = true;
  }
} catch {
  // Ignore import errors
}

// OpenTelemetry GenAI semantic convention attribute names
export const GEN_AI_OPERATION_NAME = "gen_ai.operation.name";
export const GEN_AI_SYSTEM = "gen_ai.system";
export const GEN_AI_REQUEST_MODEL = "gen_ai.request.model";
export const GEN_AI_RESPONSE_MODEL = "gen_ai.response.model";
export const GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens";
export const GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens";
export const GEN_AI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens";
export const GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens";
export const GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature";
export const GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p";
export const GEN_AI_REQUEST_FREQUENCY_PENALTY =
  "gen_ai.request.frequency_penalty";
export const GEN_AI_REQUEST_PRESENCE_PENALTY =
  "gen_ai.request.presence_penalty";
export const GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons";
export const GENAI_PROMPT = "gen_ai.prompt";
export const GENAI_COMPLETION = "gen_ai.completion";

export const GEN_AI_REQUEST_EXTRA_QUERY = "gen_ai.request.extra_query";
export const GEN_AI_REQUEST_EXTRA_BODY = "gen_ai.request.extra_body";
export const GEN_AI_SERIALIZED_NAME = "gen_ai.serialized.name";
export const GEN_AI_SERIALIZED_SIGNATURE = "gen_ai.serialized.signature";
export const GEN_AI_SERIALIZED_DOC = "gen_ai.serialized.doc";
export const GEN_AI_RESPONSE_ID = "gen_ai.response.id";
export const GEN_AI_RESPONSE_SERVICE_TIER = "gen_ai.response.service_tier";
export const GEN_AI_RESPONSE_SYSTEM_FINGERPRINT =
  "gen_ai.response.system_fingerprint";
export const GEN_AI_USAGE_INPUT_TOKEN_DETAILS =
  "gen_ai.usage.input_token_details";
export const GEN_AI_USAGE_OUTPUT_TOKEN_DETAILS =
  "gen_ai.usage.output_token_details";

// LangSmith custom attributes
export const LANGSMITH_RUN_ID = "langsmith.span.id";
export const LANGSMITH_TRACE_ID = "langsmith.trace.id";
export const LANGSMITH_DOTTED_ORDER = "langsmith.span.dotted_order";
export const LANGSMITH_PARENT_RUN_ID = "langsmith.span.parent_id";
export const LANGSMITH_SESSION_ID = "langsmith.trace.session_id";
export const LANGSMITH_SESSION_NAME = "langsmith.trace.session_name";
export const LANGSMITH_RUN_TYPE = "langsmith.span.kind";
export const LANGSMITH_NAME = "langsmith.trace.name";
export const LANGSMITH_METADATA = "langsmith.metadata";
export const LANGSMITH_TAGS = "langsmith.span.tags";
export const LANGSMITH_RUNTIME = "langsmith.span.runtime";
export const LANGSMITH_REQUEST_STREAMING = "langsmith.request.streaming";
export const LANGSMITH_REQUEST_HEADERS = "langsmith.request.headers";

// GenAI event names
export const GEN_AI_SYSTEM_MESSAGE = "gen_ai.system.message";
export const GEN_AI_USER_MESSAGE = "gen_ai.user.message";
export const GEN_AI_ASSISTANT_MESSAGE = "gen_ai.assistant.message";
export const GEN_AI_CHOICE = "gen_ai.choice";

const WELL_KNOWN_OPERATION_NAMES: Record<string, string> = {
  llm: "chat",
  tool: "execute_tool",
  retriever: "embeddings",
  embedding: "embeddings",
  prompt: "chat",
};

function getOperationName(runType: string): string {
  return WELL_KNOWN_OPERATION_NAMES[runType] || runType;
}

export interface SerializedRunOperation {
  operation: "post" | "patch";
  id: string;
  trace_id: string;
  _none: string; // JSON string in JS
  inputs?: string;
  outputs?: string;
  events?: string;
}

export interface OTELSpan {
  setAttribute(key: string, value: string | number | boolean): void;
  setStatus(status: any): void;
  recordException(exception: Error): void;
  end(endTime?: number): void;
}

export interface OTELTracer {
  startSpan(name: string, options?: any): OTELSpan;
}

export interface OTELContext {
  // Context interface placeholder
}

export class OTELExporter {
  private tracer: OTELTracer | null = null;
  private spans: Map<string, OTELSpan> = new Map();

  constructor(tracerProvider?: any) {
    if (!HAS_OTEL) {
      console.warn(
        "OTEL_ENABLED is set but OpenTelemetry packages are not installed. " +
          "Install the required OpenTelemetry packages."
      );
      return;
    }

    // Note: Actual implementation would require OpenTelemetry imports
    // This is a placeholder structure
    this.tracer = tracerProvider?.getTracer?.("langsmith") || null;
  }

  exportBatch(
    operations: SerializedRunOperation[],
    otelContextMap: Map<string, OTELContext | null>
  ): void {
    if (!this.tracer) {
      return;
    }

    for (const op of operations) {
      try {
        const runInfo = this.deserializeRunInfo(op);
        if (!runInfo) {
          continue;
        }

        if (op.operation === "post") {
          const span = this.createSpanForRun(
            op,
            runInfo,
            otelContextMap.get(op.id) || null
          );
          if (span) {
            this.spans.set(op.id, span);
          }
        } else {
          this.updateSpanForRun(op, runInfo);
        }
      } catch (e) {
        console.error(`Error processing operation ${op.id}:`, e);
      }
    }
  }

  private deserializeRunInfo(op: SerializedRunOperation): Run | null {
    try {
      return JSON.parse(op._none) as Run;
    } catch (e) {
      console.error(`Failed to deserialize run info for ${op.id}:`, e);
      return null;
    }
  }

  private createSpanForRun(
    op: SerializedRunOperation,
    runInfo: Run,
    otelContext: OTELContext | null = null
  ): OTELSpan | null {
    if (!this.tracer) {
      return null;
    }

    try {
      const startTime = runInfo.start_time;
      const endTime = runInfo.end_time;

      // Create deterministic trace and span IDs would require hex conversion utilities
      // For now, using the run structure as-is

      const spanOptions: any = {
        startTime: startTime ? new Date(startTime) : undefined,
      };

      // Handle parent context
      const parentRunId = runInfo.parent_run_id;
      if (parentRunId && this.spans.has(parentRunId)) {
        // Set parent context - actual implementation would require OTEL context handling
        spanOptions.parent = this.spans.get(parentRunId);
      } else if (otelContext) {
        spanOptions.parent = otelContext;
      }

      const span = this.tracer.startSpan(runInfo.name, spanOptions);

      // Set all attributes
      this.setSpanAttributes(span, runInfo, op);

      // Set status based on error
      if (runInfo.error) {
        span.setStatus({ code: 2 }); // ERROR status
        span.recordException(new Error(runInfo.error));
      } else {
        span.setStatus({ code: 1 }); // OK status
      }

      // End the span if end_time is present
      if (endTime) {
        span.end(endTime);
      }

      return span;
    } catch (e) {
      console.error(`Failed to create span for run ${op.id}:`, e);
      return null;
    }
  }

  private updateSpanForRun(op: SerializedRunOperation, runInfo: Run): void {
    try {
      const span = this.spans.get(op.id);
      if (!span) {
        console.debug(`No span found for run ${op.id} during update`);
        return;
      }

      // Update attributes
      this.setSpanAttributes(span, runInfo, op);

      // Update status based on error
      if (runInfo.error) {
        span.setStatus({ code: 2 }); // ERROR status
        span.recordException(new Error(runInfo.error));
      } else {
        span.setStatus({ code: 1 }); // OK status
      }

      // End the span if end_time is present
      const endTime = runInfo.end_time;
      if (endTime) {
        span.end(endTime);
        // Remove the span from our dictionary
        this.spans.delete(op.id);
      }
    } catch (e) {
      console.error(`Failed to update span for run ${op.id}:`, e);
    }
  }

  private extractModelName(runInfo: Run): string | null {
    // Try to get model name from metadata
    if (runInfo.extra?.metadata) {
      const metadata = runInfo.extra.metadata;

      // First check for ls_model_name in metadata
      if (metadata.ls_model_name) {
        return metadata.ls_model_name;
      }

      // Then check invocation_params for model info
      if (metadata.invocation_params) {
        const invocationParams = metadata.invocation_params;
        if (invocationParams.model) {
          return invocationParams.model;
        } else if (invocationParams.model_name) {
          return invocationParams.model_name;
        }
      }
    }

    return null;
  }

  private setSpanAttributes(
    span: OTELSpan,
    runInfo: Run,
    op: SerializedRunOperation
  ): void {
    // Set LangSmith-specific attributes
    span.setAttribute(LANGSMITH_RUN_ID, op.id);
    span.setAttribute(LANGSMITH_TRACE_ID, op.trace_id);

    if (runInfo.dotted_order) {
      span.setAttribute(LANGSMITH_DOTTED_ORDER, runInfo.dotted_order);
    }

    if (runInfo.parent_run_id) {
      span.setAttribute(LANGSMITH_PARENT_RUN_ID, runInfo.parent_run_id);
    }

    if (runInfo.run_type) {
      span.setAttribute(LANGSMITH_RUN_TYPE, runInfo.run_type);
    }

    if (runInfo.name) {
      span.setAttribute(LANGSMITH_NAME, runInfo.name);
    }

    if (runInfo.session_id) {
      span.setAttribute(LANGSMITH_SESSION_ID, runInfo.session_id);
    }

    // Set GenAI attributes according to OTEL semantic conventions
    const operationName = getOperationName(runInfo.run_type || "chain");
    span.setAttribute(GEN_AI_OPERATION_NAME, operationName);

    // Set gen_ai.system
    this.setGenAiSystem(span, runInfo);

    // Set model name if available
    const modelName = this.extractModelName(runInfo);
    if (modelName) {
      span.setAttribute(GEN_AI_REQUEST_MODEL, modelName);
    }

    // Set token usage information
    if (runInfo.prompt_tokens !== undefined) {
      span.setAttribute(GEN_AI_USAGE_INPUT_TOKENS, runInfo.prompt_tokens);
    }

    if (runInfo.completion_tokens !== undefined) {
      span.setAttribute(GEN_AI_USAGE_OUTPUT_TOKENS, runInfo.completion_tokens);
    }

    if (runInfo.total_tokens !== undefined) {
      span.setAttribute(GEN_AI_USAGE_TOTAL_TOKENS, runInfo.total_tokens);
    }

    // Set other parameters from invocation_params
    this.setInvocationParameters(span, runInfo);

    // Set metadata and tags if available
    const metadata = runInfo.extra?.metadata || {};
    for (const [key, value] of Object.entries(metadata)) {
      if (value !== null && value !== undefined) {
        span.setAttribute(`${LANGSMITH_METADATA}.${key}`, String(value));
      }
    }

    const tags = runInfo.tags;
    if (tags && Array.isArray(tags)) {
      span.setAttribute(LANGSMITH_TAGS, tags.join(", "));
    } else if (tags) {
      span.setAttribute(LANGSMITH_TAGS, String(tags));
    }

    // Support additional serialized attributes, if present
    if (runInfo.serialized && typeof runInfo.serialized === "object") {
      const serialized = runInfo.serialized as KVMap;
      if (serialized.name) {
        span.setAttribute(GEN_AI_SERIALIZED_NAME, String(serialized.name));
      }
      if (serialized.signature) {
        span.setAttribute(
          GEN_AI_SERIALIZED_SIGNATURE,
          String(serialized.signature)
        );
      }
      if (serialized.doc) {
        span.setAttribute(GEN_AI_SERIALIZED_DOC, String(serialized.doc));
      }
    }

    // Set inputs/outputs if available
    this.setIOAttributes(span, op);
  }

  private setGenAiSystem(span: OTELSpan, runInfo: Run): void {
    // Default to "langchain" if we can't determine the system
    let system = "langchain";

    // Extract model name to determine the system
    const modelName = this.extractModelName(runInfo);
    if (modelName) {
      const modelLower = modelName.toLowerCase();
      if (modelLower.includes("anthropic") || modelLower.startsWith("claude")) {
        system = "anthropic";
      } else if (modelLower.includes("bedrock")) {
        system = "aws.bedrock";
      } else if (
        modelLower.includes("azure") &&
        modelLower.includes("openai")
      ) {
        system = "az.ai.openai";
      } else if (
        modelLower.includes("azure") &&
        modelLower.includes("inference")
      ) {
        system = "az.ai.inference";
      } else if (modelLower.includes("cohere")) {
        system = "cohere";
      } else if (modelLower.includes("deepseek")) {
        system = "deepseek";
      } else if (modelLower.includes("gemini")) {
        system = "gemini";
      } else if (modelLower.includes("groq")) {
        system = "groq";
      } else if (modelLower.includes("watson") || modelLower.includes("ibm")) {
        system = "ibm.watsonx.ai";
      } else if (modelLower.includes("mistral")) {
        system = "mistral_ai";
      } else if (modelLower.includes("gpt") || modelLower.includes("openai")) {
        system = "openai";
      } else if (
        modelLower.includes("perplexity") ||
        modelLower.includes("sonar")
      ) {
        system = "perplexity";
      } else if (modelLower.includes("vertex")) {
        system = "vertex_ai";
      } else if (modelLower.includes("xai") || modelLower.includes("grok")) {
        system = "xai";
      }
    }

    span.setAttribute(GEN_AI_SYSTEM, system);
  }

  private setInvocationParameters(span: OTELSpan, runInfo: Run): void {
    if (!runInfo.extra?.metadata?.invocation_params) {
      return;
    }

    const invocationParams = runInfo.extra.metadata.invocation_params;

    // Set relevant invocation parameters
    if (invocationParams.max_tokens !== undefined) {
      span.setAttribute(GEN_AI_REQUEST_MAX_TOKENS, invocationParams.max_tokens);
    }

    if (invocationParams.temperature !== undefined) {
      span.setAttribute(
        GEN_AI_REQUEST_TEMPERATURE,
        invocationParams.temperature
      );
    }

    if (invocationParams.top_p !== undefined) {
      span.setAttribute(GEN_AI_REQUEST_TOP_P, invocationParams.top_p);
    }

    if (invocationParams.frequency_penalty !== undefined) {
      span.setAttribute(
        GEN_AI_REQUEST_FREQUENCY_PENALTY,
        invocationParams.frequency_penalty
      );
    }

    if (invocationParams.presence_penalty !== undefined) {
      span.setAttribute(
        GEN_AI_REQUEST_PRESENCE_PENALTY,
        invocationParams.presence_penalty
      );
    }
  }

  private setIOAttributes(span: OTELSpan, op: SerializedRunOperation): void {
    if (op.inputs) {
      try {
        const inputs = JSON.parse(op.inputs);

        if (typeof inputs === "object" && inputs !== null) {
          if (inputs.model && Array.isArray(inputs.messages) && inputs.model) {
            span.setAttribute(GEN_AI_REQUEST_MODEL, inputs.model);
          }

          // Set additional request attributes if available
          if (inputs.stream !== undefined) {
            span.setAttribute(LANGSMITH_REQUEST_STREAMING, inputs.stream);
          }
          if (inputs.extra_headers) {
            span.setAttribute(
              LANGSMITH_REQUEST_HEADERS,
              JSON.stringify(inputs.extra_headers)
            );
          }
          if (inputs.extra_query) {
            span.setAttribute(
              GEN_AI_REQUEST_EXTRA_QUERY,
              JSON.stringify(inputs.extra_query)
            );
          }
          if (inputs.extra_body) {
            span.setAttribute(
              GEN_AI_REQUEST_EXTRA_BODY,
              JSON.stringify(inputs.extra_body)
            );
          }
        }

        span.setAttribute(GENAI_PROMPT, op.inputs);
      } catch (e) {
        console.debug(`Failed to process inputs for run ${op.id}`, e);
      }
    }

    if (op.outputs) {
      try {
        const outputs = JSON.parse(op.outputs);

        // Extract token usage from outputs (for LLM runs)
        const tokenUsage = this.getUnifiedRunTokens(outputs);
        if (tokenUsage) {
          span.setAttribute(GEN_AI_USAGE_INPUT_TOKENS, tokenUsage[0]);
          span.setAttribute(GEN_AI_USAGE_OUTPUT_TOKENS, tokenUsage[1]);
          span.setAttribute(
            GEN_AI_USAGE_TOTAL_TOKENS,
            tokenUsage[0] + tokenUsage[1]
          );
        }

        if (outputs && typeof outputs === "object") {
          if (outputs.model) {
            span.setAttribute(GEN_AI_RESPONSE_MODEL, String(outputs.model));
          }

          // Extract additional response attributes
          if (outputs.id) {
            span.setAttribute(GEN_AI_RESPONSE_ID, outputs.id);
          }

          if (outputs.choices && Array.isArray(outputs.choices)) {
            const finishReasons = outputs.choices
              .map((choice: any) => choice.finish_reason)
              .filter((reason: any) => reason)
              .map(String);
            if (finishReasons.length > 0) {
              span.setAttribute(
                GEN_AI_RESPONSE_FINISH_REASONS,
                finishReasons.join(", ")
              );
            }
          }

          if (outputs.service_tier) {
            span.setAttribute(
              GEN_AI_RESPONSE_SERVICE_TIER,
              outputs.service_tier
            );
          }

          if (outputs.system_fingerprint) {
            span.setAttribute(
              GEN_AI_RESPONSE_SYSTEM_FINGERPRINT,
              outputs.system_fingerprint
            );
          }

          if (
            outputs.usage_metadata &&
            typeof outputs.usage_metadata === "object"
          ) {
            const usageMetadata = outputs.usage_metadata;
            if (usageMetadata.input_token_details) {
              span.setAttribute(
                GEN_AI_USAGE_INPUT_TOKEN_DETAILS,
                JSON.stringify(usageMetadata.input_token_details)
              );
            }
            if (usageMetadata.output_token_details) {
              span.setAttribute(
                GEN_AI_USAGE_OUTPUT_TOKEN_DETAILS,
                JSON.stringify(usageMetadata.output_token_details)
              );
            }
          }
        }

        span.setAttribute(GENAI_COMPLETION, op.outputs);
      } catch (e) {
        console.debug(`Failed to process outputs for run ${op.id}`, e);
      }
    }
  }

  private getUnifiedRunTokens(outputs: any): [number, number] | null {
    if (!outputs) {
      return null;
    }

    // Search in non-generations lists
    let tokenUsage = this.extractUnifiedRunTokens(outputs.usage_metadata);
    if (tokenUsage) {
      return tokenUsage;
    }

    // Find if direct kwarg in outputs
    const keys = Object.keys(outputs);
    for (const key of keys) {
      const haystack = outputs[key];
      if (!haystack || typeof haystack !== "object") {
        continue;
      }

      tokenUsage = this.extractUnifiedRunTokens(haystack.usage_metadata);
      if (tokenUsage) {
        return tokenUsage;
      }

      if (
        haystack.lc === 1 &&
        haystack.kwargs &&
        typeof haystack.kwargs === "object"
      ) {
        tokenUsage = this.extractUnifiedRunTokens(
          haystack.kwargs.usage_metadata
        );
        if (tokenUsage) {
          return tokenUsage;
        }
      }
    }

    // Find in generations
    const generations = outputs.generations || [];
    if (!Array.isArray(generations)) {
      return null;
    }

    const flatGenerations = Array.isArray(generations[0])
      ? generations.flat()
      : generations;

    for (const generation of flatGenerations) {
      if (
        typeof generation === "object" &&
        generation.message &&
        typeof generation.message === "object" &&
        generation.message.kwargs &&
        typeof generation.message.kwargs === "object"
      ) {
        tokenUsage = this.extractUnifiedRunTokens(
          generation.message.kwargs.usage_metadata
        );
        if (tokenUsage) {
          return tokenUsage;
        }
      }
    }

    return null;
  }

  private extractUnifiedRunTokens(outputs: any): [number, number] | null {
    if (!outputs || typeof outputs !== "object") {
      return null;
    }

    if (
      typeof outputs.input_tokens !== "number" ||
      typeof outputs.output_tokens !== "number"
    ) {
      return null;
    }

    return [outputs.input_tokens, outputs.output_tokens];
  }
}
