import {
  _mapWithConcurrency,
  _reorderResultRowsByExampleIndex,
  evaluate,
} from "../evaluation/_runner.js";
import { PQueue } from "../utils/p-queue.js";
import { Example } from "../schemas.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function* fromArray<T>(items: T[]): AsyncGenerator<T> {
  for (const item of items) {
    yield item;
  }
}

async function collect<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const results: T[] = [];
  for await (const item of iterable) {
    results.push(item);
  }
  return results;
}

describe("evaluation runner internals", () => {
  test("mapWithConcurrency with concurrency Infinity runs all tasks at once", async () => {
    let active = 0;
    let maxActive = 0;
    const queue = new PQueue({ concurrency: Infinity });

    const output = await collect(
      _mapWithConcurrency(fromArray([1, 2, 3, 4, 5]), queue, async (value) => {
        active += 1;
        maxActive = Math.max(maxActive, active);
        await sleep(10);
        active -= 1;
        return value;
      })
    );

    expect(output).toHaveLength(5);
    expect(maxActive).toBe(5); // All 5 should run concurrently
  });

  test("mapWithConcurrency with concurrency 1 runs tasks one at a time", async () => {
    let active = 0;
    let maxActive = 0;
    const queue = new PQueue({ concurrency: 1 });

    const output = await collect(
      _mapWithConcurrency(fromArray([1, 2, 3]), queue, async (value) => {
        active += 1;
        maxActive = Math.max(maxActive, active);
        await sleep(10);
        active -= 1;
        return value;
      })
    );

    expect(output).toEqual([1, 2, 3]);
    expect(maxActive).toBe(1);
  });

  test("mapWithConcurrency yields by completion order and honors concurrency", async () => {
    let active = 0;
    let maxActive = 0;
    const delays: Record<number, number> = {
      1: 30,
      2: 5,
      3: 10,
    };

    const queue = new PQueue({ concurrency: 2 });
    const output = await collect(
      _mapWithConcurrency(fromArray([1, 2, 3]), queue, async (value) => {
        active += 1;
        maxActive = Math.max(maxActive, active);
        await sleep(delays[value]);
        active -= 1;
        return value;
      })
    );

    expect(output).toEqual([2, 3, 1]);
    expect(maxActive).toBeLessThanOrEqual(2);
    expect(maxActive).toBe(2);
  });

  test("mapWithConcurrency propagates mapper errors", async () => {
    const queue = new PQueue({ concurrency: 2 });
    await expect(
      collect(
        _mapWithConcurrency(fromArray([1, 2, 3]), queue, async (value) => {
          if (value === 2) {
            throw new Error("mapper boom");
          }
          await sleep(1);
          return value;
        })
      )
    ).rejects.toThrow("mapper boom");
  });

  test("mapWithConcurrency propagates source iterable errors", async () => {
    async function* source(): AsyncGenerator<number> {
      yield 1;
      throw new Error("source boom");
    }

    const queue = new PQueue({ concurrency: 2 });
    await expect(
      collect(_mapWithConcurrency(source(), queue, async (value) => value))
    ).rejects.toThrow("source boom");
  });

  test("reorderResultRowsByExampleIndex restores original example order", () => {
    const inputRows = [
      {
        exampleIndex: 2,
        run: { id: "run-2" },
        example: { id: "example-2" },
        evaluationResults: { results: [{ key: "key-2" }] },
      },
      {
        exampleIndex: 0,
        run: { id: "run-0" },
        example: { id: "example-0" },
        evaluationResults: { results: [{ key: "key-0" }] },
      },
      {
        exampleIndex: 1,
        run: { id: "run-1" },
        example: { id: "example-1" },
        evaluationResults: { results: [{ key: "key-1" }] },
      },
    ] as unknown as Parameters<typeof _reorderResultRowsByExampleIndex>[0];

    const { orderedRows, orderedRuns } =
      _reorderResultRowsByExampleIndex(inputRows);

    expect(orderedRows.map((row) => row.example.id)).toEqual([
      "example-0",
      "example-1",
      "example-2",
    ]);
    expect(
      orderedRows.map((row) => row.evaluationResults.results[0].key)
    ).toEqual(["key-0", "key-1", "key-2"]);
    expect(orderedRuns.map((run) => run.id)).toEqual([
      "run-0",
      "run-1",
      "run-2",
    ]);
    expect(inputRows.map((row) => row.exampleIndex)).toEqual([2, 0, 1]);
  });

  test("reorderResultRowsByExampleIndex keeps stable order for ties", () => {
    const inputRows = [
      {
        exampleIndex: 1,
        run: { id: "run-a" },
        example: { id: "example-a" },
        evaluationResults: { results: [] },
      },
      {
        exampleIndex: 1,
        run: { id: "run-b" },
        example: { id: "example-b" },
        evaluationResults: { results: [] },
      },
      {
        exampleIndex: 0,
        run: { id: "run-c" },
        example: { id: "example-c" },
        evaluationResults: { results: [] },
      },
    ] as unknown as Parameters<typeof _reorderResultRowsByExampleIndex>[0];

    const { orderedRuns } = _reorderResultRowsByExampleIndex(inputRows);
    expect(orderedRuns.map((run) => run.id)).toEqual([
      "run-c",
      "run-a",
      "run-b",
    ]);
  });

  test("fast results can be processed while slow tasks are still running", async () => {
    const queue = new PQueue({ concurrency: 3 });
    const delays: Record<number, number> = {
      1: 100, // slow
      2: 10, // fast
      3: 10, // fast
      4: 10, // fast
    };

    const resultsOrder: number[] = [];
    const startTime = Date.now();

    for await (const value of _mapWithConcurrency(
      fromArray([1, 2, 3, 4]),
      queue,
      async (value) => {
        await sleep(delays[value]);
        return value;
      }
    )) {
      resultsOrder.push(value);
      const elapsed = Date.now() - startTime;

      // If we got value 2, 3, or 4, task 1 (100ms) should still be running
      if ([2, 3, 4].includes(value)) {
        expect(elapsed).toBeLessThan(100);
      }
    }

    // Fast tasks (2, 3, 4) should complete before slow task (1)
    expect(resultsOrder.slice(0, 3)).toContain(2);
    expect(resultsOrder.slice(0, 3)).toContain(3);
    expect(resultsOrder.slice(0, 3)).toContain(4);
    expect(resultsOrder[3]).toBe(1); // Slow task completes last
  });

  test("separate queues allow independent concurrency control", async () => {
    let maxTargetActive = 0;
    let currentTargetActive = 0;
    let maxEvalActive = 0;
    let currentEvalActive = 0;

    const now = new Date().toISOString();
    const examples: Example[] = [
      {
        id: "1",
        inputs: { value: 1 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "2",
        inputs: { value: 2 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "3",
        inputs: { value: 3 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
    ];

    const target = async (input: { value: number }) => {
      currentTargetActive++;
      maxTargetActive = Math.max(maxTargetActive, currentTargetActive);
      await sleep(10);
      currentTargetActive--;
      return { result: input.value };
    };

    const evaluator = async () => {
      currentEvalActive++;
      maxEvalActive = Math.max(maxEvalActive, currentEvalActive);
      await sleep(10);
      currentEvalActive--;
      return { key: "test", score: 1 };
    };

    const mockClient = {
      createProject: async () => ({
        id: "test",
        name: "test",
        reference_dataset_id: "test",
      }),
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(target, {
      data: examples,
      evaluators: [evaluator],
      targetConcurrency: 1,
      evaluationConcurrency: 2,
      client: mockClient,
    });

    const allResults = [];
    for await (const result of results) {
      allResults.push(result);
    }

    // Target should have max concurrency of 1
    expect(maxTargetActive).toBe(1);
    // Evaluator should have max concurrency of 2
    expect(maxEvalActive).toBe(2);
  }, 10000);

  test("end-to-end: evaluations run on fast predictions before slow predictions finish", async () => {
    const delays: Record<number, number> = {
      0: 100, // slow prediction
      1: 10, // fast prediction
      2: 10, // fast prediction
    };

    const datasetId = "00000000-0000-0000-0000-000000000000";
    const now = new Date().toISOString();
    const examples: Example[] = [
      {
        id: "00000000-0000-0000-0000-000000000001",
        inputs: { value: 0 },
        outputs: {},
        dataset_id: datasetId,
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "00000000-0000-0000-0000-000000000002",
        inputs: { value: 1 },
        outputs: {},
        dataset_id: datasetId,
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "00000000-0000-0000-0000-000000000003",
        inputs: { value: 2 },
        outputs: {},
        dataset_id: datasetId,
        created_at: now,
        modified_at: now,
        runs: [],
      },
    ];

    const predictionTimes: Record<number, number> = {};
    const evaluationTimes: Record<number, number> = {};
    const startTime = Date.now();

    // Target function with varying delays
    const target = async (input: { value: number }) => {
      await sleep(delays[input.value]);
      predictionTimes[input.value] = Date.now() - startTime;
      return { result: input.value };
    };

    // Evaluator that records when it runs
    const evaluator = async ({ example }: any) => {
      evaluationTimes[example.inputs.value] = Date.now() - startTime;
      return { key: "test", score: 1 };
    };

    // Mock client to avoid real API calls
    const mockClient = {
      createProject: async () => ({
        id: "00000000-0000-0000-0000-000000000004",
        name: "test-project",
        reference_dataset_id: datasetId,
      }),
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(target, {
      data: examples,
      evaluators: [evaluator],
      targetConcurrency: 3,
      evaluationConcurrency: 3,
      client: mockClient,
    });

    // Wait for all results to be processed
    const allResults = [];
    for await (const result of results) {
      allResults.push(result);
    }

    // Fast predictions (1, 2) should complete and be evaluated before slow prediction (0) finishes
    expect(predictionTimes[1]).toBeLessThan(predictionTimes[0]);
    expect(predictionTimes[2]).toBeLessThan(predictionTimes[0]);

    // Fast predictions should be evaluated before slow prediction finishes
    expect(evaluationTimes[1]).toBeLessThan(predictionTimes[0]);
    expect(evaluationTimes[2]).toBeLessThan(predictionTimes[0]);

    // All evaluations should have run
    expect(Object.keys(evaluationTimes)).toHaveLength(3);
  }, 10000);

  test("maxConcurrency=0 runs tasks sequentially (matching Python behavior)", async () => {
    const executionOrder: number[] = [];
    let currentlyExecuting: number | null = null;

    const now = new Date().toISOString();
    const examples: Example[] = [
      {
        id: "1",
        inputs: { value: 1 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "2",
        inputs: { value: 2 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
      {
        id: "3",
        inputs: { value: 3 },
        outputs: {},
        dataset_id: "test",
        created_at: now,
        modified_at: now,
        runs: [],
      },
    ];

    const target = async (input: { value: number }) => {
      // Verify no other task is executing
      expect(currentlyExecuting).toBeNull();
      currentlyExecuting = input.value;
      executionOrder.push(input.value);
      await sleep(10);
      currentlyExecuting = null;
      return { result: input.value };
    };

    const mockClient = {
      createProject: async () => ({
        id: "test",
        name: "test",
        reference_dataset_id: "test",
      }),
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(target, {
      data: examples,
      evaluators: [],
      maxConcurrency: 0, // Sequential execution
      client: mockClient,
    });

    const allResults = [];
    for await (const result of results) {
      allResults.push(result);
    }

    // Verify sequential execution - order should match input order
    expect(executionOrder).toEqual([1, 2, 3]);
  }, 10000);
});
