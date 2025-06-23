/* eslint-disable @typescript-eslint/no-explicit-any */

describe("Traceable OTEL Integration", () => {
  afterEach(() => {
    delete process.env.OTEL_ENABLED;
  });

  it("works correctly when OTEL_ENABLED is false", async () => {
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
  });

  it("works correctly when OTEL_ENABLED is undefined", async () => {
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
  });

  it("works correctly when OTEL_ENABLED is true", async () => {
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

  it("handles async traceable functions correctly", async () => {
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
  });

  it("handles nested traceable calls correctly", async () => {
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

  it("works correctly with RunTree UUIDs", async () => {
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
