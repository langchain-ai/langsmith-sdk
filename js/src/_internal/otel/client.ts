import { type TracerProvider as OTELTracerProvider } from "@opentelemetry/api";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import {
  BatchSpanProcessor,
  BasicTracerProvider,
  ReadableSpan,
} from "@opentelemetry/sdk-trace-base";

import {
  getEnvironmentVariable,
  setEnvironmentVariable,
} from "../../utils/env.js";
import * as constants from "./constants.js";

export class LangSmithOTLPTraceExporter extends OTLPTraceExporter {
  constructor(options: ConstructorParameters<typeof OTLPTraceExporter>[0]) {
    super(options);
  }
  export(
    spans: ReadableSpan[],
    resultCallback: Parameters<OTLPTraceExporter["export"]>[1]
  ): void {
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
      }
    }
    super.export(spans, resultCallback);
  }
}

/**
 * Convert headers string in format "name=value,name2=value2" to object
 */
function parseHeadersString(headersStr: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (!headersStr) return headers;

  headersStr.split(",").forEach((pair) => {
    const [name, ...valueParts] = pair.split("=");
    if (name && valueParts.length > 0) {
      headers[name.trim()] = valueParts.join("=").trim();
    }
  });

  return headers;
}

export function getOTLPTracerProvider(): OTELTracerProvider {
  // Set LangSmith-specific defaults if not already set in environment
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT")) {
    const lsEndpoint =
      getEnvironmentVariable("LANGSMITH_ENDPOINT") ||
      getEnvironmentVariable("LANGCHAIN_ENDPOINT") ||
      "https://api.smith.langchain.com";
    const baseUrl = lsEndpoint.replace(/\/$/, "");
    setEnvironmentVariable(
      "OTEL_EXPORTER_OTLP_ENDPOINT",
      `${baseUrl}/otel/v1/traces`
    );
  }

  // Configure headers with API key and project if available
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS")) {
    const apiKey =
      getEnvironmentVariable("LANGSMITH_API_KEY") ||
      getEnvironmentVariable("LANGCHAIN_API_KEY");

    if (!apiKey) {
      throw new Error(
        "LANGSMITH_API_KEY or LANGCHAIN_API_KEY environment variable is required"
      );
    }

    let headers = `x-api-key=${apiKey}`;

    const project =
      getEnvironmentVariable("LANGSMITH_PROJECT") ||
      getEnvironmentVariable("LANGCHAIN_PROJECT");
    if (project) {
      headers += `,Langsmith-Project=${project}`;
    }

    setEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS", headers);
  }

  const headersStr = getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS") || "";
  const headersObj = parseHeadersString(headersStr);

  const langsmithSpanExporter = new LangSmithOTLPTraceExporter({
    url: getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT"),
    headers: headersObj,
  });
  const spanProcessor = new BatchSpanProcessor(langsmithSpanExporter);

  return new BasicTracerProvider({
    spanProcessors: [spanProcessor],
  });
}
