import {
  trace as otel_trace,
  context as otel_context,
} from "@opentelemetry/api";
import { AsyncHooksContextManager } from "@opentelemetry/context-async-hooks";
import { type TracerProvider as OTELTracerProvider } from "@opentelemetry/api";
import {
  BatchSpanProcessor,
  BasicTracerProvider,
} from "@opentelemetry/sdk-trace-base";

import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
  setEnvironmentVariable,
} from "../utils/env.js";
import { LangSmithOTLPTraceExporter } from "./exporter.js";

import {
  setDefaultOTLPTracerProviderGetter,
  setOTELInstances,
} from "../singletons/otel.js";

const otel = {
  trace: otel_trace,
  context: otel_context,
};

setOTELInstances(otel);

const contextManager = new AsyncHooksContextManager();
contextManager.enable();
otel_context.setGlobalContextManager(contextManager);

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

function getDefaultOTLPTracerProvider(): OTELTracerProvider {
  // Set LangSmith-specific defaults if not already set in environment
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT")) {
    const lsEndpoint =
      getLangSmithEnvironmentVariable("ENDPOINT") ||
      "https://api.smith.langchain.com";
    const baseUrl = lsEndpoint.replace(/\/$/, "");
    setEnvironmentVariable(
      "OTEL_EXPORTER_OTLP_ENDPOINT",
      `${baseUrl}/otel/v1/traces`
    );
  }

  // Configure headers with API key and project if available
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS")) {
    const apiKey = getLangSmithEnvironmentVariable("API_KEY");

    if (!apiKey) {
      throw new Error(
        "LANGSMITH_API_KEY or LANGCHAIN_API_KEY environment variable is required"
      );
    }

    let headers = `x-api-key=${apiKey}`;

    const project = getLangSmithEnvironmentVariable("PROJECT");
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

setDefaultOTLPTracerProviderGetter(getDefaultOTLPTracerProvider);
