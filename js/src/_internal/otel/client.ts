import { type TracerProvider as OTELTracerProvider } from "@opentelemetry/api";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import {
  BatchSpanProcessor,
  BasicTracerProvider,
} from "@opentelemetry/sdk-trace-base";

import {
  getEnvironmentVariable,
  setEnvironmentVariable,
} from "../../utils/env.js";

const HAS_OTEL = getEnvironmentVariable("OTEL_ENABLED") === "true";

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

export function getOtlpTracerProvider(): OTELTracerProvider {
  if (!HAS_OTEL) {
    throw new Error(
      "OpenTelemetry packages are required to use this function. " +
        "Please install the required OpenTelemetry packages."
    );
  }

  // Set LangSmith-specific defaults if not already set in environment
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT")) {
    const lsEndpoint =
      getEnvironmentVariable("LANGSMITH_ENDPOINT") ||
      getEnvironmentVariable("LANGCHAIN_ENDPOINT") ||
      "https://api.smith.langchain.com";
    setEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT", `${lsEndpoint}/otel`);
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

  const langsmithSpanExporter = new OTLPTraceExporter({
    url: getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT"),
    headers: headersObj,
  });
  const spanProcessor = new BatchSpanProcessor(langsmithSpanExporter);

  return new BasicTracerProvider({
    spanProcessors: [spanProcessor],
  });
}
