/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { jest } from "@jest/globals";
import {
  LangSmithToOTELTranslator,
  getOtelTraceIdFromUuid,
  getOtelSpanIdFromUuid,
  validateAndNormalizeUuid,
  type SerializedRunOperation,
} from "../_internal/otel/index.js";

describe("OTEL UUID Utils", () => {
  it("converts UUID to trace ID", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const traceId = getOtelTraceIdFromUuid(uuid);
    expect(traceId).toBe("550e8400e29b41d4a716446655440000");
  });

  it("converts UUID to span ID", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const spanId = getOtelSpanIdFromUuid(uuid);
    expect(spanId).toBe("550e8400e29b41d4");
  });

  it("validates UUID", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    expect(validateAndNormalizeUuid(uuid)).toBe(uuid);
  });

  it("throws on invalid UUID", () => {
    expect(() => validateAndNormalizeUuid("invalid")).toThrow("Invalid UUID");
  });
});

describe("OTEL Exporter", () => {
  let mockSpan: any;
  let mockTracer: any;

  beforeEach(() => {
    mockSpan = {
      setAttribute: jest.fn(),
      setStatus: jest.fn(),
      end: jest.fn(),
    };

    mockTracer = {
      startSpan: jest.fn().mockReturnValue(mockSpan),
    };
  });

  it("creates span for run", () => {
    const exporter = new LangSmithToOTELTranslator({
      getTracer: () => mockTracer,
    });
    // Manually set the tracer since HAS_OTEL might be false
    (exporter as any).tracer = mockTracer;

    const operation: SerializedRunOperation = {
      operation: "post",
      id: "run-123",
      trace_id: "trace-456",
      _none: JSON.stringify({
        name: "test-run",
        run_type: "llm",
        start_time: 1000,
      }),
    };

    exporter.exportBatch([operation], new Map());

    expect(mockSpan.setAttribute).toHaveBeenCalledWith(
      "langsmith.span.id",
      "run-123"
    );
    expect(mockSpan.setAttribute).toHaveBeenCalledWith(
      "gen_ai.operation.name",
      "chat"
    );
  });

  it("detects model systems", () => {
    const exporter = new LangSmithToOTELTranslator({
      getTracer: () => mockTracer,
    });
    (exporter as any).tracer = mockTracer;

    const operation: SerializedRunOperation = {
      operation: "post",
      id: "run-123",
      trace_id: "trace-456",
      _none: JSON.stringify({
        name: "test-run",
        run_type: "llm",
        extra: {
          metadata: {
            invocation_params: { model: "gpt-4" },
          },
        },
      }),
    };

    exporter.exportBatch([operation], new Map());

    expect(mockSpan.setAttribute).toHaveBeenCalledWith(
      "gen_ai.system",
      "openai"
    );
  });

  it("extracts token usage", () => {
    const exporter = new LangSmithToOTELTranslator({
      getTracer: () => mockTracer,
    });
    (exporter as any).tracer = mockTracer;

    const operation: SerializedRunOperation = {
      operation: "post",
      id: "run-123",
      trace_id: "trace-456",
      _none: JSON.stringify({ name: "test", run_type: "llm" }),
      outputs: JSON.stringify({
        usage_metadata: {
          input_tokens: 100,
          output_tokens: 50,
        },
      }),
    };

    exporter.exportBatch([operation], new Map());

    expect(mockSpan.setAttribute).toHaveBeenCalledWith(
      "gen_ai.usage.input_tokens",
      100
    );
    expect(mockSpan.setAttribute).toHaveBeenCalledWith(
      "gen_ai.usage.output_tokens",
      50
    );
  });
});

describe("Traceable OTEL Integration", () => {
  it("integrates with traceable functions gracefully when OTEL not available", async () => {
    // Set environment to enable OTEL but without actual OTEL packages
    process.env.OTEL_ENABLED = "true";

    try {
      const { traceable } = await import("../traceable.js");

      const testFunction = traceable(
        async (input: string) => {
          return `processed: ${input}`;
        },
        { name: "test-function" }
      );

      const result = await testFunction("hello");

      // Should work gracefully even without OTEL packages
      expect(result).toBe("processed: hello");
    } finally {
      delete process.env.OTEL_ENABLED;
    }
  });

  it("works when OTEL is disabled", async () => {
    // OTEL_ENABLED not set
    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      async (input: string) => {
        return `processed: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("hello");

    expect(result).toBe("processed: hello");
  });
});
