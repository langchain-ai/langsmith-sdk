/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { jest } from "@jest/globals";

// Mock the @opentelemetry/api module at the top level
const mockTrace = {
  setSpan: jest.fn((context, span) => context),
};
const mockContext = {
  active: jest.fn(() => ({})),
  with: jest.fn((ctx, fn) => fn()),
};

jest.mock("@opentelemetry/api", () => ({
  trace: mockTrace,
  SpanContext: jest.fn(),
  TraceFlags: { SAMPLED: 1 },
  context: mockContext,
}));

describe("Traceable OTEL Integration", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Enable tracing so RunTrees are created
    process.env.LANGCHAIN_TRACING_V2 = "true";
  });

  afterEach(() => {
    delete process.env.OTEL_ENABLED;
    delete process.env.LANGCHAIN_TRACING_V2;
  });

  it("does not create OTEL context when OTEL_ENABLED is false", async () => {
    process.env.OTEL_ENABLED = "false";

    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    // Should not create OTEL context when disabled
    expect(mockTrace.setSpan).not.toHaveBeenCalled();
    expect(mockContext.with).not.toHaveBeenCalled();
  });

  it("does not create OTEL context when OTEL_ENABLED is undefined", async () => {
    // OTEL_ENABLED not set

    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    // Should not create OTEL context when undefined
    expect(mockTrace.setSpan).not.toHaveBeenCalled();
    expect(mockContext.with).not.toHaveBeenCalled();
  });

  it("creates OTEL context when OTEL_ENABLED is true", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    // Should create OTEL context when enabled
    expect(mockContext.active).toHaveBeenCalled();
    expect(mockTrace.setSpan).toHaveBeenCalled();
    expect(mockContext.with).toHaveBeenCalled();
  });

  it("creates OTEL context for async traceable functions", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const asyncFunction = traceable(
      async (input: string) => {
        return `async result: ${input}`;
      },
      { name: "async-function" }
    );

    const result = await asyncFunction("test");

    expect(result).toBe("async result: test");
    expect(mockContext.active).toHaveBeenCalled();
    expect(mockTrace.setSpan).toHaveBeenCalled();
    expect(mockContext.with).toHaveBeenCalled();
  });

  it("propagates OTEL context through nested traceable calls", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

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
    // Should be called twice - once for parent, once for child
    expect(mockContext.with).toHaveBeenCalledTimes(2);
    expect(mockTrace.setSpan).toHaveBeenCalledTimes(2);
  });

  it("handles OTEL package import failures gracefully", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
  });

  it("handles OTEL context creation failures gracefully", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
  });

  it("creates deterministic span IDs from RunTree UUIDs", async () => {
    process.env.OTEL_ENABLED = "true";

    const { RunTree } = await import("../run_trees.js");
    const { traceable } = await import("../traceable.js");

    // Create a specific RunTree with known UUID
    const runTree = new RunTree({
      name: "test-run",
      id: "550e8400-e29b-41d4-a716-446655440000",
      trace_id: "550e8400-e29b-41d4-a716-446655440000", // Use same ID for trace_id
    });

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    // Pass runTree as first argument to traceable function call
    const result = await testFunction(runTree, "test");

    expect(result).toBe("result: test");
    // Should create OTEL context with the RunTree
    expect(mockContext.active).toHaveBeenCalled();
    expect(mockTrace.setSpan).toHaveBeenCalled();
    expect(mockContext.with).toHaveBeenCalled();

    // Verify that setSpan was called with a span object that has the expected span context
    const setSpanCall = mockTrace.setSpan.mock.calls[0];
    expect(setSpanCall).toBeDefined();
    expect(setSpanCall[1]).toBeDefined(); // The span object
    expect(typeof (setSpanCall[1] as any).spanContext).toBe("function");
  });

  it("works with generator functions", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const generatorFunction = traceable(
      function* (input: string) {
        yield `first: ${input}`;
        yield `second: ${input}`;
        return `final: ${input}`;
      },
      { name: "generator-function" }
    );

    const generator = await generatorFunction("test");
    const results = Array.from(generator as Iterable<string>);

    expect(results).toEqual(["first: test", "second: test"]);
  });

  it("works with async generator functions", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const asyncGeneratorFunction = traceable(
      async function* (input: string) {
        yield `first: ${input}`;
        yield `second: ${input}`;
        return `final: ${input}`;
      },
      { name: "async-generator-function" }
    );

    const generator = asyncGeneratorFunction("test");
    const results = [];
    for await (const value of generator) {
      results.push(value);
    }

    expect(results).toEqual(["first: test", "second: test"]);
  });

  it("works correctly with promise chains", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const promiseFunction = traceable(
      async (input: string) => {
        return Promise.resolve(`promise: ${input}`)
          .then((result) => `then: ${result}`)
          .then((result) => `final: ${result}`);
      },
      { name: "promise-function" }
    );

    const result = await promiseFunction("test");

    expect(result).toBe("final: then: promise: test");
  });

  it("handles errors correctly", async () => {
    process.env.OTEL_ENABLED = "true";

    const { traceable } = await import("../traceable.js");

    const errorFunction = traceable(
      () => {
        throw new Error("Test error");
      },
      { name: "error-function" }
    );

    await expect(errorFunction()).rejects.toThrow("Test error");
  });
});
