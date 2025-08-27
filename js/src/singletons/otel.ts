// Should not import any OTEL packages to avoid pulling in optional deps.

import { getOtelEnabled } from "../utils/env.js";

interface OTELTraceInterface {
  getTracer: (name: string, version?: string) => any;
  getActiveSpan: () => any;
  setSpan: (context: any, span: any) => any;
  getSpan: (context: any) => any;
  setSpanContext: (context: any, spanContext: any) => any;
  getTracerProvider: () => any;
  setGlobalTracerProvider: (tracerProvider: any) => boolean;
}

interface OTELContextInterface {
  active: () => any;
  with: <T>(context: any, fn: () => T) => T;
}

interface OTELInterface {
  trace: OTELTraceInterface;
  context: OTELContextInterface;
}

class MockTracer {
  private hasWarned = false;

  startActiveSpan<T>(_name: string, ...args: any[]): T | undefined {
    if (!this.hasWarned && getOtelEnabled()) {
      console.warn(
        "You have enabled OTEL export via the `OTEL_ENABLED` or `LANGSMITH_OTEL_ENABLED` environment variable, but have not initialized the required OTEL instances. " +
          'Please add:\n```\nimport { initializeOTEL } from "langsmith/experimental/otel/setup";\ninitializeOTEL();\n```\nat the beginning of your code.'
      );
      this.hasWarned = true;
    }

    // Handle different overloads:
    // startActiveSpan(name, fn)
    // startActiveSpan(name, options, fn)
    // startActiveSpan(name, options, context, fn)
    let fn: ((...args: any[]) => T) | undefined;

    if (args.length === 1 && typeof args[0] === "function") {
      fn = args[0];
    } else if (args.length === 2 && typeof args[1] === "function") {
      fn = args[1];
    } else if (args.length === 3 && typeof args[2] === "function") {
      fn = args[2];
    }

    if (typeof fn === "function") {
      return fn();
    }
    return undefined;
  }
}

class MockOTELTrace implements OTELTraceInterface {
  private mockTracer = new MockTracer();

  getTracer(_name: string, _version?: string) {
    return this.mockTracer;
  }

  getActiveSpan() {
    return undefined;
  }

  setSpan(context: any, _span: any) {
    return context;
  }

  getSpan(_context: any) {
    return undefined;
  }

  setSpanContext(context: any, _spanContext: any) {
    return context;
  }

  getTracerProvider() {
    return undefined;
  }

  setGlobalTracerProvider(_tracerProvider: any) {
    return false;
  }
}

class MockOTELContext implements OTELContextInterface {
  active() {
    return {};
  }

  with<T>(_context: any, fn: () => T): T {
    return fn();
  }
}

const OTEL_TRACE_KEY = Symbol.for("ls:otel_trace");
const OTEL_CONTEXT_KEY = Symbol.for("ls:otel_context");
const OTEL_GET_DEFAULT_OTLP_TRACER_PROVIDER_KEY = Symbol.for(
  "ls:otel_get_default_otlp_tracer_provider"
);

const mockOTELTrace = new MockOTELTrace();
const mockOTELContext = new MockOTELContext();

class OTELProvider {
  getTraceInstance(): OTELTraceInterface {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (globalThis as any)[OTEL_TRACE_KEY] ?? mockOTELTrace;
  }

  getContextInstance(): OTELContextInterface {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (globalThis as any)[OTEL_CONTEXT_KEY] ?? mockOTELContext;
  }

  initializeGlobalInstances(otel: OTELInterface) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((globalThis as any)[OTEL_TRACE_KEY] === undefined) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any)[OTEL_TRACE_KEY] = otel.trace;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((globalThis as any)[OTEL_CONTEXT_KEY] === undefined) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any)[OTEL_CONTEXT_KEY] = otel.context;
    }
  }

  setDefaultOTLPTracerComponents(components: {
    DEFAULT_LANGSMITH_SPAN_PROCESSOR: any;
    DEFAULT_LANGSMITH_TRACER_PROVIDER: any;
    DEFAULT_LANGSMITH_SPAN_EXPORTER: any;
  }) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any)[OTEL_GET_DEFAULT_OTLP_TRACER_PROVIDER_KEY] = components;
  }

  getDefaultOTLPTracerComponents() {
    return (
      (globalThis as any)[OTEL_GET_DEFAULT_OTLP_TRACER_PROVIDER_KEY] ??
      undefined
    );
  }
}

export const OTELProviderSingleton = new OTELProvider();

/**
 * Get the current OTEL trace instance.
 * Returns a mock implementation if OTEL is not available.
 */
export function getOTELTrace(): OTELTraceInterface {
  return OTELProviderSingleton.getTraceInstance();
}

/**
 * Get the current OTEL context instance.
 * Returns a mock implementation if OTEL is not available.
 */
export function getOTELContext(): OTELContextInterface {
  return OTELProviderSingleton.getContextInstance();
}

/**
 * Initialize the global OTEL instances.
 * Should be called once when OTEL packages are available.
 */
export function setOTELInstances(otel: OTELInterface): void {
  OTELProviderSingleton.initializeGlobalInstances(otel);
}

/**
 * Set a getter function for the default OTLP tracer provider.
 * This allows lazy initialization of the tracer provider.
 */
export function setDefaultOTLPTracerComponents(components: {
  DEFAULT_LANGSMITH_SPAN_PROCESSOR: any;
  DEFAULT_LANGSMITH_TRACER_PROVIDER: any;
  DEFAULT_LANGSMITH_SPAN_EXPORTER: any;
}): void {
  OTELProviderSingleton.setDefaultOTLPTracerComponents(components);
}

/**
 * Get the default OTLP tracer provider instance.
 * Returns undefined if not set.
 */
export function getDefaultOTLPTracerComponents():
  | {
      DEFAULT_LANGSMITH_SPAN_PROCESSOR: any;
      DEFAULT_LANGSMITH_TRACER_PROVIDER: any;
      DEFAULT_LANGSMITH_SPAN_EXPORTER: any;
    }
  | undefined {
  return OTELProviderSingleton.getDefaultOTLPTracerComponents();
}
