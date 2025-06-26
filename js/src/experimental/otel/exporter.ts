import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { ReadableSpan } from "@opentelemetry/sdk-trace-base";
import * as constants from "./constants.js";
import { isTracingEnabled } from "../../env.js";

export class LangSmithOTLPTraceExporter extends OTLPTraceExporter {
  export(
    spans: ReadableSpan[],
    resultCallback: Parameters<OTLPTraceExporter["export"]>[1]
  ): void {
    if (!isTracingEnabled()) {
      return;
    }
    for (const span of spans) {
      if (!span.attributes[constants.GENAI_PROMPT]) {
        if (span.attributes["ai.prompt"]) {
          span.attributes[constants.GENAI_PROMPT] =
            span.attributes["ai.prompt"];
        }
        if (
          span.attributes["ai.prompt.messages"] &&
          typeof span.attributes["ai.prompt.messages"] === "string"
        ) {
          let messages;
          try {
            messages = JSON.parse(span.attributes["ai.prompt.messages"]);
          } catch (e) {
            console.error("Failed to parse ai.prompt.messages", e);
          }
          if (messages && Array.isArray(messages)) {
            span.attributes[constants.GENAI_PROMPT] = JSON.stringify({
              input: messages,
            });
          }
        }
        if (span.attributes["ai.toolCall.args"]) {
          span.attributes[constants.GENAI_PROMPT] =
            span.attributes["ai.toolCall.args"];
        }
      }
      if (!span.attributes[constants.GENAI_COMPLETION]) {
        if (span.attributes["ai.response.text"]) {
          span.attributes[constants.GENAI_COMPLETION] =
            span.attributes["ai.response.text"];
        }
        if (span.attributes["ai.response.choices"]) {
          span.attributes[constants.GENAI_COMPLETION] =
            span.attributes["ai.response.choices"];
        }
        if (span.attributes["ai.response.object"]) {
          span.attributes[constants.GENAI_COMPLETION] =
            span.attributes["ai.response.object"];
        }
        if (span.attributes["ai.response.toolCalls"]) {
          span.attributes[constants.GENAI_COMPLETION] =
            span.attributes["ai.response.toolCalls"];
        }
        if (span.attributes["ai.toolCall.result"]) {
          span.attributes[constants.GENAI_COMPLETION] =
            span.attributes["ai.toolCall.result"];
        }
      }
      if (
        typeof span.attributes["ai.operationId"] === "string" &&
        constants.AI_SDK_LLM_OPERATIONS.includes(
          span.attributes["ai.operationId"]
        )
      ) {
        span.attributes[constants.LANGSMITH_RUN_TYPE] = "llm";
      } else if (
        typeof span.attributes["ai.operationId"] === "string" &&
        constants.AI_SDK_TOOL_OPERATIONS.includes(
          span.attributes["ai.operationId"]
        )
      ) {
        span.attributes[constants.LANGSMITH_RUN_TYPE] = "tool";
        if (span.attributes["ai.toolCall.name"]) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (span as any).name = span.attributes["ai.toolCall.name"];
        }
      }
    }
    super.export(spans, resultCallback);
  }
}
