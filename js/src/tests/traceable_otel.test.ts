/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { traceable } from "../traceable.js";
import { RunTree } from "../run_trees.js";

describe("Traceable OTEL Integration", () => {
  let originalRequire: any;
  let mockOTEL: any;

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup OTEL mocks
    mockOTEL = {
      trace: { setSpanInContext: jest.fn(() => "mock-span-context") },
      SpanContext: jest.fn(),
      NonRecordingSpan: jest.fn(),
      TraceFlags: { SAMPLED: 1 },
      TraceState: jest.fn(),
      context: {
        active: jest.fn(() => "active-context"),
        with: jest.fn((_ctx: any, fn: () => any) => fn()),
      },
    };

    // Mock require to return our OTEL mock
    originalRequire = (global as any).require;
    (global as any).require = jest.fn((module) => {
      if (module === "@opentelemetry/api") {
        return mockOTEL;
      }
      return originalRequire(module);
    });
  });

  afterEach(() => {
    delete process.env.OTEL_ENABLED;
    (global as any).require = originalRequire;
  });

  it("does not create OTEL context when OTEL_ENABLED is false", async () => {
    process.env.OTEL_ENABLED = "false";

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    expect(mockOTEL.context.with).not.toHaveBeenCalled();
  });

  it("does not create OTEL context when OTEL_ENABLED is undefined", async () => {
    // OTEL_ENABLED not set

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    expect(mockOTEL.context.with).not.toHaveBeenCalled();
  });

  it("creates OTEL context when OTEL_ENABLED is true", async () => {
    process.env.OTEL_ENABLED = "true";

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    expect(mockOTEL.context.with).toHaveBeenCalled();
  });

  it("handles async traceable functions with OTEL context", async () => {
    process.env.OTEL_ENABLED = "true";

    const asyncFunction = traceable(
      async (input: string) => {
        return `async result: ${input}`;
      },
      { name: "async-function" }
    );

    const result = await asyncFunction("test");

    expect(result).toBe("async result: test");
    expect(mockOTEL.context.with).toHaveBeenCalled();
    expect(mockOTEL.trace.setSpanInContext).toHaveBeenCalled();
  });

  it("propagates OTEL context through nested traceable calls", async () => {
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
    // Should be called twice - once for parent, once for child
    expect(mockOTEL.context.with).toHaveBeenCalledTimes(2);
  });

  it("handles OTEL package import failures gracefully", async () => {
    process.env.OTEL_ENABLED = "true";

    // Mock require to throw for OTEL
    (global as any).require = jest.fn((module) => {
      if (module === "@opentelemetry/api") {
        throw new Error("Package not found");
      }
      return originalRequire(module);
    });

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    // Should not call OTEL methods when import fails
    expect(mockOTEL.context.with).not.toHaveBeenCalled();
  });

  it("handles OTEL context creation failures gracefully", async () => {
    process.env.OTEL_ENABLED = "true";

    // Mock SpanContext constructor to throw
    const failingOTEL = {
      ...mockOTEL,
      SpanContext: jest.fn(() => {
        throw new Error("SpanContext creation failed");
      }),
    };

    (global as any).require = jest.fn((module) => {
      if (module === "@opentelemetry/api") {
        return failingOTEL;
      }
      return originalRequire(module);
    });

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    const result = await testFunction("test");

    expect(result).toBe("result: test");
    // Should not call context.with when span creation fails
    expect(failingOTEL.context.with).not.toHaveBeenCalled();
  });

  it("creates deterministic span IDs from RunTree UUIDs", async () => {
    process.env.OTEL_ENABLED = "true";

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
    expect(mockOTEL.SpanContext).toHaveBeenCalledWith({
      traceId: expect.any(Number),
      spanId: expect.any(Number),
      isRemote: false,
      traceFlags: 1, // SAMPLED
      traceState: expect.any(Object),
    });
  });

  it("works with generator functions", async () => {
    process.env.OTEL_ENABLED = "true";

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
    expect(mockOTEL.context.with).toHaveBeenCalled();
  });

  it("works with async generator functions", async () => {
    process.env.OTEL_ENABLED = "true";

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
    expect(mockOTEL.context.with).toHaveBeenCalled();
  });

  it("maintains OTEL context across promise chains", async () => {
    process.env.OTEL_ENABLED = "true";

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
    expect(mockOTEL.context.with).toHaveBeenCalled();
  });

  it("handles errors without breaking OTEL context", async () => {
    process.env.OTEL_ENABLED = "true";

    const errorFunction = traceable(
      () => {
        throw new Error("Test error");
      },
      { name: "error-function" }
    );

    await expect(errorFunction()).rejects.toThrow("Test error");

    expect(mockOTEL.context.with).toHaveBeenCalled();
  });
});
