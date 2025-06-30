import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { ReadableSpan } from "@opentelemetry/sdk-trace-base";
import * as constants from "./constants.js";
import { isTracingEnabled } from "../../env.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "../../utils/env.js";

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

/**
 * LangSmith OpenTelemetry trace exporter that extends the standard OTLP trace exporter
 * with LangSmith-specific configuration and span attribute transformations.
 *
 * This exporter automatically configures itself with LangSmith endpoints and API keys,
 * based on your LANGSMITH_API_KEY and LANGSMITH_PROJECT environment variables.
 * Will also respect OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_HEADERS environment
 * variables if set.
 *
 * @param config - Optional configuration object that accepts all OTLPTraceExporter parameters.
 *                 If not provided, uses default LangSmith configuration:
 *                 - `url`: Defaults to LangSmith OTEL endpoint (`${LANGSMITH_ENDPOINT}/otel/v1/traces`)
 *                 - `headers`: Auto-configured with LangSmith API key and project headers
 *                 Any provided config will override these defaults.
 */
export class LangSmithOTLPTraceExporter extends OTLPTraceExporter {
  constructor(config?: ConstructorParameters<typeof OTLPTraceExporter>[0]) {
    const lsEndpoint =
      getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT") ||
      getLangSmithEnvironmentVariable("ENDPOINT") ||
      "https://api.smith.langchain.com";
    const defaultBaseUrl = lsEndpoint.replace(/\/$/, "");
    const defaultUrl = `${defaultBaseUrl}/otel/v1/traces`;
    // Configure headers with API key and project if available
    let defaultHeaderString =
      getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS") ?? "";
    if (!defaultHeaderString) {
      const apiKey = getLangSmithEnvironmentVariable("API_KEY");
      if (apiKey) {
        defaultHeaderString = `x-api-key=${apiKey}`;
      }

      const project = getLangSmithEnvironmentVariable("PROJECT");
      if (project) {
        defaultHeaderString += `,Langsmith-Project=${project}`;
      }
    }

    super({
      url: defaultUrl,
      headers: parseHeadersString(defaultHeaderString),
      ...config,
    });
  }

  export(
    spans: ReadableSpan[],
    resultCallback: Parameters<OTLPTraceExporter["export"]>[1]
  ): void {
    if (!isTracingEnabled()) {
      return resultCallback({ code: 0 });
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
