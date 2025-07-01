// Avoid async hooks as even a peer dep to avoid pulling into
// non-node build environments.
// eslint-disable-next-line import/no-extraneous-dependencies
import { AsyncHooksContextManager } from "@opentelemetry/context-async-hooks";
import {
  trace as otel_trace,
  context as otel_context,
  type TracerProvider,
  type ContextManager,
} from "@opentelemetry/api";
import {
  BatchSpanProcessor,
  BasicTracerProvider,
} from "@opentelemetry/sdk-trace-base";
import {
  LangSmithOTLPTraceExporter,
  LangSmithOTLPTraceExporterConfig,
} from "./exporter.js";

import {
  setDefaultOTLPTracerComponents,
  setOTELInstances,
} from "../../singletons/otel.js";

/**
 * Initializes OpenTelemetry with LangSmith-specific configuration for tracing.
 *
 * Call this once at the start of your application to enable tracing integration. Sets global
 * OpenTelemetry components including the tracer provider and context manager.
 *
 * Requires the following peer dependencies to be installed:
 * - @opentelemetry/api
 * - @opentelemetry/sdk-trace-base
 * - @opentelemetry/exporter-trace-otlp-proto
 * - @opentelemetry/context-async-hooks
 *
 * @param options - Configuration options
 * @param options.globalTracerProvider - Optional custom TracerProvider to use instead of creating and globally setting a new one
 * @returns Object containing the initialized OTEL components (tracer provider, span processor, exporter)
 *
 * @example
 * ```typescript
 * import { initializeOTEL } from "langsmith/experimental/otel/setup";
 * initializeOTEL();
 * ```
 *
 * @example With custom tracer provider
 * ```typescript
 * import { initializeOTEL } from "langsmith/experimental/otel/setup";
 * import { BasicTracerProvider } from "@opentelemetry/sdk-trace-base";
 *
 * const customProvider = new BasicTracerProvider();
 * initializeOTEL({ globalTracerProvider: customProvider });
 * ```
 */
export const initializeOTEL = (
  config: {
    globalTracerProvider?: TracerProvider;
    globalContextManager?: ContextManager;
    exporterConfig?: LangSmithOTLPTraceExporterConfig;
  } = {}
) => {
  const { globalTracerProvider, globalContextManager, exporterConfig } = config;

  const otel = {
    trace: otel_trace,
    context: otel_context,
  };

  setOTELInstances(otel);

  if (!globalContextManager) {
    const contextManager = new AsyncHooksContextManager();
    contextManager.enable();
    otel_context.setGlobalContextManager(contextManager);
  }

  const DEFAULT_LANGSMITH_SPAN_EXPORTER = new LangSmithOTLPTraceExporter(
    exporterConfig
  );

  const DEFAULT_LANGSMITH_SPAN_PROCESSOR = new BatchSpanProcessor(
    DEFAULT_LANGSMITH_SPAN_EXPORTER
  );

  if (!globalTracerProvider) {
    const DEFAULT_LANGSMITH_TRACER_PROVIDER = new BasicTracerProvider({
      spanProcessors: [DEFAULT_LANGSMITH_SPAN_PROCESSOR],
    });

    const defaultComponents = {
      DEFAULT_LANGSMITH_SPAN_PROCESSOR,
      DEFAULT_LANGSMITH_TRACER_PROVIDER,
      DEFAULT_LANGSMITH_SPAN_EXPORTER,
    };

    // If user has set global tracer before, this fails and returns false
    const globalSuccessfullyOverridden = otel_trace.setGlobalTracerProvider(
      defaultComponents.DEFAULT_LANGSMITH_TRACER_PROVIDER
    );

    if (globalSuccessfullyOverridden) {
      setDefaultOTLPTracerComponents(defaultComponents);
    }

    return defaultComponents;
  } else {
    const defaultComponents = {
      DEFAULT_LANGSMITH_TRACER_PROVIDER: globalTracerProvider,
      DEFAULT_LANGSMITH_SPAN_PROCESSOR,
      DEFAULT_LANGSMITH_SPAN_EXPORTER,
    };
    setDefaultOTLPTracerComponents(defaultComponents);
    return defaultComponents;
  }
};
