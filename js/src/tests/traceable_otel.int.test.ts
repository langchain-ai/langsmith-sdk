/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { traceable } from "../traceable.js";
import { RunTree } from "../run_trees.js";
import { trace, context } from "@opentelemetry/api";

describe("Traceable OTEL Integration Tests", () => {
  beforeEach(() => {
    process.env.LANGCHAIN_TRACING_V2 = "true";
  });

  afterEach(() => {
    delete process.env.OTEL_ENABLED;
    delete process.env.LANGCHAIN_TRACING_V2;
  });

  it("works gracefully when OTEL_ENABLED is true but packages not available", async () => {
    process.env.OTEL_ENABLED = "true";

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    // Should work even if OTEL packages aren't installed
    const result = await testFunction("test");
    expect(result).toBe("result: test");
  });

  it("handles nested calls with OTEL context", async () => {
    process.env.OTEL_ENABLED = "true";

    const childFunction = traceable(
      async (input: string) => {
        return `child: ${input}`;
      },
      { name: "child-function" }
    );

    const parentFunction = traceable(
      async (input: string) => {
        const childResult = await childFunction(input);
        return `parent: ${childResult}`;
      },
      { name: "parent-function" }
    );

    const result = await parentFunction("test");
    expect(result).toBe("parent: child: test");
  });

  it("integrates with real OTEL API when available", async () => {
    process.env.OTEL_ENABLED = "true";

    // Verify we can access OTEL APIs
    expect(typeof trace.getActiveSpan).toBe("function");
    expect(typeof context.active).toBe("function");

    const runTree = new RunTree({
      name: "otel-test-run",
      id: "550e8400-e29b-41d4-a716-446655440000",
      trace_id: "550e8400-e29b-41d4-a716-446655440000",
    });

    const otelFunction = traceable(
      (input: string) => {
        // Test that we can access OTEL context within traceable function
        const activeContext = context.active();
        expect(activeContext).toBeDefined();

        return `otel integration: ${input}`;
      },
      { name: "otel-function" }
    );

    const result = await otelFunction(runTree, "test");
    expect(result).toBe("otel integration: test");
  });
});
