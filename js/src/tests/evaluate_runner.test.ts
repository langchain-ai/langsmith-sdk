import { jest } from "@jest/globals";
import type { Run as V2Run } from "../_openapi_client/resources/runs/runs.js";
import type { Client } from "../client.js";
import {
  _collectEvaluatorKeys,
  _extractEvaluatorFeedbackKeys,
  _mapWithConcurrency,
  _reorderResultRowsByExampleIndex,
  evaluate,
} from "../evaluation/_runner.js";
import { loadTracesForExperiment } from "../evaluation/evaluate_comparative.js";
import { PQueue } from "../utils/p-queue.js";
import { Example, Run, TracerSession } from "../schemas.js";

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
      }),
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
      }),
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
      }),
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
        }),
      ),
    ).rejects.toThrow("mapper boom");
  });

  test("mapWithConcurrency propagates source iterable errors", async () => {
    async function* source(): AsyncGenerator<number> {
      yield 1;
      throw new Error("source boom");
    }

    const queue = new PQueue({ concurrency: 2 });
    await expect(
      collect(_mapWithConcurrency(source(), queue, async (value) => value)),
    ).rejects.toThrow("source boom");
  });

  test("evaluate supplies the experiment ID when logging run feedback", async () => {
    const experimentId = "00000000-0000-0000-0000-000000000004";
    const datasetId = "00000000-0000-0000-0000-000000000000";
    const now = new Date().toISOString();
    const feedbackCalls: any[][] = [];
    const mockClient = {
      createProject: async () => ({
        id: experimentId,
        name: "test-project",
        reference_dataset_id: datasetId,
      }),
      updateProject: async () => ({}),
      logEvaluationFeedback: async (...args: any[]) => {
        feedbackCalls.push(args);
        return [];
      },
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(async () => ({ output: "ok" }), {
      data: [
        {
          id: "00000000-0000-0000-0000-000000000001",
          inputs: { input: "hello" },
          outputs: {},
          dataset_id: datasetId,
          created_at: now,
          modified_at: now,
          runs: [],
        },
      ],
      evaluators: [async () => ({ key: "quality", score: 1 })],
      client: mockClient,
    });
    for await (const _ of results) {
      // Drain the result stream.
    }

    expect(feedbackCalls).toHaveLength(1);
    expect(feedbackCalls[0]).toEqual([
      expect.objectContaining({
        run: expect.objectContaining({ start_time: expect.anything() }),
        projectId: experimentId,
      }),
    ]);
  });

  test("evaluate resolves existing runs by session_id and logs routing fields", async () => {
    const experimentId = "00000000-0000-0000-0000-000000000004";
    const datasetId = "00000000-0000-0000-0000-000000000000";
    const exampleId = "00000000-0000-0000-0000-000000000001";
    const runId = "00000000-0000-0000-0000-000000000002";
    const startTime = "2026-07-21T12:34:56.789Z";
    const readProject = jest.fn(async () => ({
      id: experimentId,
      name: "existing-project",
      reference_dataset_id: datasetId,
    }));
    const logEvaluationFeedback = jest.fn(async () => []);
    const mockClient = {
      readProject,
      logEvaluationFeedback,
      getDatasetUrl: async () => "http://test.com",
      createRun: async () => undefined,
      updateRun: async () => undefined,
      awaitPendingTraceBatches: async () => undefined,
    } as any;
    const run = {
      id: runId,
      name: "existing-run",
      run_type: "chain",
      start_time: startTime,
      trace_id: runId,
      dotted_order: "",
      session_id: experimentId,
      reference_example_id: exampleId,
      inputs: { input: "hello" },
      outputs: { output: "ok" },
    } as Run;
    const now = new Date().toISOString();

    const results = await evaluate(fromArray([run]) as never, {
      data: [
        {
          id: exampleId,
          inputs: { input: "hello" },
          outputs: {},
          dataset_id: datasetId,
          created_at: now,
          modified_at: now,
          runs: [],
        },
      ],
      evaluators: [async () => ({ key: "quality", score: 1 })],
      client: mockClient,
    });
    for await (const _ of results) {
      // Drain the result stream.
    }

    expect(readProject).toHaveBeenCalledWith({ projectId: experimentId });
    expect(logEvaluationFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        run: expect.objectContaining({
          session_id: experimentId,
          start_time: startTime,
        }),
        projectId: experimentId,
      }),
    );
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
      orderedRows.map((row) => row.evaluationResults.results[0].key),
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
      },
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

  test("evaluate infers numExamples from list data", async () => {
    const now = new Date().toISOString();
    const examples: Example[] = [1, 2, 3].map((v) => ({
      id: `e${v}`,
      inputs: { value: v },
      outputs: {},
      dataset_id: "test",
      created_at: now,
      modified_at: now,
      runs: [],
    }));

    const createProjectCalls: any[] = [];
    const mockClient = {
      createProject: async (params: any) => {
        createProjectCalls.push(params);
        return { id: "test", name: "test", reference_dataset_id: "test" };
      },
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(
      async (input: any) => ({ result: input.value }),
      {
        data: examples,
        evaluators: [],
        numRepetitions: 4,
        client: mockClient,
      },
    );
    const collected = [];
    for await (const r of results) {
      collected.push(r);
    }

    expect(createProjectCalls).toHaveLength(1);
    expect(createProjectCalls[0].numExamples).toBe(3);
    expect(createProjectCalls[0].numRepetitions).toBe(4);
  });

  test("evaluate omits numExamples for async-iterable data", async () => {
    const now = new Date().toISOString();
    const examples: Example[] = [1, 2, 3].map((v) => ({
      id: `e${v}`,
      inputs: { value: v },
      outputs: {},
      dataset_id: "test",
      created_at: now,
      modified_at: now,
      runs: [],
    }));

    async function* exampleGen() {
      for (const e of examples) yield e;
    }

    const createProjectCalls: any[] = [];
    const mockClient = {
      createProject: async (params: any) => {
        createProjectCalls.push(params);
        return { id: "test", name: "test", reference_dataset_id: "test" };
      },
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(
      async (input: any) => ({ result: input.value }),
      {
        data: exampleGen(),
        evaluators: [],
        client: mockClient,
      },
    );
    for await (const _ of results) {
      // drain
    }

    expect(createProjectCalls).toHaveLength(1);
    expect(createProjectCalls[0].numExamples).toBeNull();
    expect(createProjectCalls[0].numRepetitions).toBe(1);
  });
});

describe("evaluator feedback-key extraction", () => {
  test("prefers the returned key over the function name", () => {
    // The bug: function name (binding) != returned feedback key.
    const completenessEvaluator = async ({
      outputs,
    }: {
      outputs?: Record<string, any>;
    }) => ({
      key: "field_completeness",
      score: Object.keys(outputs ?? {}).length,
    });
    expect(_extractEvaluatorFeedbackKeys(completenessEvaluator as any)).toEqual(
      ["field_completeness"],
    );
  });

  test("named function literal key", () => {
    function relevance({ outputs }: { outputs?: Record<string, any> }) {
      return { key: "answer_relevance", score: outputs ? 1 : 0 };
    }
    expect(_extractEvaluatorFeedbackKeys(relevance as any)).toEqual([
      "answer_relevance",
    ]);
  });

  test("multi-result evaluator returns all keys", () => {
    const multi = ({ outputs }: { outputs?: Record<string, any> }) => ({
      results: [
        { key: "k1", score: outputs ? 1 : 0 },
        { key: "k2", score: 0 },
      ],
    });
    expect(_extractEvaluatorFeedbackKeys(multi as any)).toEqual(["k1", "k2"]);
  });

  test("falls back to the function name when the key is dynamic", () => {
    const dynamicKey = "computed_at_runtime";
    function dynamicEval({ outputs }: { outputs?: Record<string, any> }) {
      return { key: dynamicKey, score: outputs ? 1 : 0 };
    }
    expect(_extractEvaluatorFeedbackKeys(dynamicEval as any)).toEqual([
      "dynamicEval",
    ]);
  });

  test("returns empty when neither a literal key nor a name is available", () => {
    const runtimeKey = "x";
    expect(
      _extractEvaluatorFeedbackKeys(((_args: any) => ({
        key: runtimeKey,
        score: 1,
      })) as any),
    ).toEqual([]);
  });

  test("_collectEvaluatorKeys aggregates across evaluators", () => {
    const completenessEvaluator = async ({
      outputs,
    }: {
      outputs?: Record<string, any>;
    }) => ({ key: "field_completeness", score: outputs ? 1 : 0 });
    const qualityEvaluator = async ({
      outputs,
    }: {
      outputs?: Record<string, any>;
    }) => ({ key: "analysis_quality", score: outputs ? 1 : 0 });
    expect(
      _collectEvaluatorKeys([
        completenessEvaluator as any,
        qualityEvaluator as any,
      ]),
    ).toEqual(["field_completeness", "analysis_quality"]);
  });

  test("createProject receives the returned feedback keys, not function names", async () => {
    const now = new Date().toISOString();
    const examples: Example[] = [1, 2, 3].map((v) => ({
      id: `e${v}`,
      inputs: { value: v },
      outputs: {},
      dataset_id: "test",
      created_at: now,
      modified_at: now,
      runs: [],
    }));

    const completenessEvaluator = async ({
      outputs,
    }: {
      outputs?: Record<string, any>;
    }) => ({ key: "field_completeness", score: outputs ? 1 : 0 });
    const qualityEvaluator = async ({
      outputs,
    }: {
      outputs?: Record<string, any>;
    }) => ({ key: "analysis_quality", score: outputs ? 1 : 0 });

    const createProjectCalls: any[] = [];
    const mockClient = {
      createProject: async (params: any) => {
        createProjectCalls.push(params);
        return { id: "test", name: "test", reference_dataset_id: "test" };
      },
      updateProject: async () => ({}),
      createFeedback: async () => ({}),
      logEvaluationFeedback: async () => [],
      awaitPendingTraceBatches: async () => undefined,
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const results = await evaluate(
      async (input: any) => ({ result: input.value }),
      {
        data: examples,
        evaluators: [completenessEvaluator, qualityEvaluator],
        client: mockClient,
      },
    );
    for await (const _ of results) {
      // drain
    }

    expect(createProjectCalls).toHaveLength(1);
    expect(createProjectCalls[0].evaluatorKeys).toEqual([
      "field_completeness",
      "analysis_quality",
    ]);
  });
});

describe("loadTracesForExperiment", () => {
  const project: TracerSession = {
    id: "00000000-0000-0000-0000-000000000001",
    tenant_id: "00000000-0000-0000-0000-000000000002",
    start_time: 0,
    end_time: 1_000,
  };

  const v2Run: V2Run = {
    id: "00000000-0000-0000-0000-000000000003",
    name: "root",
    run_type: "CHAIN",
    start_time: "1970-01-01T00:00:00.000Z",
    trace_id: "00000000-0000-0000-0000-000000000003",
    project_id: project.id,
    parent_run_ids: [],
    reference_example_id: "00000000-0000-0000-0000-000000000004",
    inputs: { question: "test" },
    outputs: { answer: "test" },
    status: "SUCCESS",
  };

  test("loads runs from v2 when SDB querying is enabled", async () => {
    const queryV2 = jest.fn(() => fromArray([v2Run]));
    const listRuns = jest.fn();
    const client = {
      _supportsSDBQuery: async () => true,
      runs: { queryV2 },
      listRuns,
    } as unknown as Client;

    const runs = await loadTracesForExperiment(client, project, {
      loadNested: false,
    });

    expect(runs).toHaveLength(1);
    expect(runs[0].session_id).toBe(project.id);
    expect(queryV2).toHaveBeenCalledWith(
      expect.objectContaining({
        project_ids: [project.id],
        min_start_time: "1970-01-01T00:00:00.000Z",
        max_start_time: "1970-01-01T00:00:01.000Z",
        is_root: true,
      }),
    );
    expect(listRuns).not.toHaveBeenCalled();
  });

  test("loads and nests runs from v1 when SDB querying is disabled", async () => {
    const root: Run = {
      id: "00000000-0000-0000-0000-000000000005",
      name: "root",
      run_type: "chain",
      inputs: {},
    };
    const child: Run = {
      id: "00000000-0000-0000-0000-000000000006",
      name: "child",
      run_type: "tool",
      inputs: {},
      parent_run_id: root.id,
      dotted_order: "2",
    };
    const listRuns = jest.fn(() => fromArray([child, root]));
    const queryV2 = jest.fn();
    const client = {
      _supportsSDBQuery: async () => false,
      runs: { queryV2 },
      listRuns,
    } as unknown as Client;

    const runs = await loadTracesForExperiment(client, project, {
      loadNested: true,
    });

    expect(runs).toEqual([root]);
    expect(root.child_runs).toEqual([child]);
    expect(listRuns).toHaveBeenCalledWith({
      projectId: project.id,
      executionOrder: undefined,
    });
    expect(queryV2).not.toHaveBeenCalled();
  });
});
