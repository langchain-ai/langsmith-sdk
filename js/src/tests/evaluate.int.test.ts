import {
  EvaluationResult,
  EvaluationResults,
} from "../evaluation/evaluator.js";
import { evaluate } from "../evaluation/_runner.js";
import { waitUntilRunFound } from "./utils.js";
import { Example, Run, TracerSession } from "../schemas.js";
import { Client } from "../index.js";
import { afterAll, beforeAll } from "@jest/globals";
import { RunnableLambda, RunnableSequence } from "@langchain/core/runnables";
import { v4 as uuidv4 } from "uuid";
const TESTING_DATASET_NAME = `test_dataset_js_evaluate_${uuidv4()}`;
const TESTING_DATASET_NAME2 = `my_splits_ds_${uuidv4()}`;

beforeAll(async () => {
  const client = new Client();
  if (!(await client.hasDataset({ datasetName: TESTING_DATASET_NAME }))) {
    // create a new dataset
    await client.createDataset(TESTING_DATASET_NAME, {
      description:
        "For testing purposed. Is created & deleted for each test run.",
    });
    // create examples
    const res = await client.createExamples({
      inputs: [{ input: 1 }, { input: 2 }],
      outputs: [{ output: 2 }, { output: 3 }],
      datasetName: TESTING_DATASET_NAME,
    });
    if (res.length !== 2) {
      throw new Error("Failed to create examples");
    }
  }
});

afterAll(async () => {
  const client = new Client();
  await client.deleteDataset({
    datasetName: TESTING_DATASET_NAME,
  });
  try {
    await client.deleteDataset({
      datasetName: "my_splits_ds2",
    });
  } catch {
    //pass
  }
});

test("evaluate can evaluate", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    description: "Experiment from evaluate can evaluate integration test",
  });
  // console.log(evalRes.results)
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();
  const firstRun = evalRes.results[0].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(firstRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(firstRun.outputs?.foo).toBeLessThanOrEqual(3);

  const firstRunResults = evalRes.results[0].evaluationResults;
  expect(firstRunResults.results).toHaveLength(0);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();
  const secondRun = evalRes.results[1].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(secondRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(secondRun.outputs?.foo).toBeLessThanOrEqual(3);

  const secondRunResults = evalRes.results[1].evaluationResults;
  expect(secondRunResults.results).toHaveLength(0);
});

test("evaluate can repeat", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    description: "Experiment from evaluate can evaluate integration test",
    numRepetitions: 3,
  });
  expect(evalRes.results).toHaveLength(6);

  for (let i = 0; i < 6; i++) {
    expect(evalRes.results[i].run).toBeDefined();
    expect(evalRes.results[i].example).toBeDefined();
    expect(evalRes.results[i].evaluationResults).toBeDefined();
    const currRun = evalRes.results[i].run;
    // The examples are not always in the same order, so it should always be 2 or 3
    expect(currRun.outputs?.foo).toBeGreaterThanOrEqual(2);
    expect(currRun.outputs?.foo).toBeLessThanOrEqual(3);

    const firstRunResults = evalRes.results[i].evaluationResults;
    expect(firstRunResults.results).toHaveLength(0);
  }
});

// Skipping for speed in CI, encapsulated below
test.skip("evaluate can evaluate with custom evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [customEvaluator],
    description: "evaluate can evaluate with custom evaluators",
  });

  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(firstRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(firstRun.outputs?.foo).toBeLessThanOrEqual(3);

  const firstExample = evalRes.results[0].example;
  expect(firstExample).toBeDefined();

  const firstEvalResults = evalRes.results[0].evaluationResults;
  expect(firstEvalResults.results).toHaveLength(1);
  expect(firstEvalResults.results[0].key).toEqual("key");
  expect(firstEvalResults.results[0].score).toEqual(1);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(secondRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(secondRun.outputs?.foo).toBeLessThanOrEqual(3);

  const secondExample = evalRes.results[1].example;
  expect(secondExample).toBeDefined();

  const secondEvalResults = evalRes.results[1].evaluationResults;
  expect(secondEvalResults.results).toHaveLength(1);
  expect(secondEvalResults.results[0].key).toEqual("key");
  expect(secondEvalResults.results[0].score).toEqual(1);

  // Test runs & examples were passed to customEvaluator
  const expectedCommentStrings = [
    `Run: ${secondRun.id} Example: ${secondExample?.id}`,
    `Run: ${firstRun.id} Example: ${firstExample?.id}`,
  ];
  const receivedCommentStrings = evalRes.results
    .map(({ evaluationResults }) => evaluationResults.results[0].comment)
    .filter((c): c is string => !!c);
  expect(receivedCommentStrings.length).toBe(2);
  expect(receivedCommentStrings).toEqual(
    expect.arrayContaining(expectedCommentStrings)
  );
});

// Skipping for speed in CI, encapsulated below
test.skip("evaluate can evaluate with custom evaluators and array return value", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = async (run: Run, example?: Example) => {
    return [
      {
        key: "key",
        score: 1,
        comment: `Run: ${run.id} Example: ${example?.id}`,
      },
    ];
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [customEvaluator],
    description: "evaluate can evaluate with custom evaluators",
  });

  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(firstRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(firstRun.outputs?.foo).toBeLessThanOrEqual(3);

  const firstExample = evalRes.results[0].example;
  expect(firstExample).toBeDefined();

  const firstEvalResults = evalRes.results[0].evaluationResults;
  expect(firstEvalResults.results).toHaveLength(1);
  expect(firstEvalResults.results[0].key).toEqual("key");
  expect(firstEvalResults.results[0].score).toEqual(1);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(secondRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(secondRun.outputs?.foo).toBeLessThanOrEqual(3);

  const secondExample = evalRes.results[1].example;
  expect(secondExample).toBeDefined();

  const secondEvalResults = evalRes.results[1].evaluationResults;
  expect(secondEvalResults.results).toHaveLength(1);
  expect(secondEvalResults.results[0].key).toEqual("key");
  expect(secondEvalResults.results[0].score).toEqual(1);

  // Test runs & examples were passed to customEvaluator
  const expectedCommentStrings = [
    `Run: ${secondRun.id} Example: ${secondExample?.id}`,
    `Run: ${firstRun.id} Example: ${firstExample?.id}`,
  ];
  const receivedCommentStrings = evalRes.results
    .map(({ evaluationResults }) => evaluationResults.results[0].comment)
    .filter((c): c is string => !!c);
  expect(receivedCommentStrings.length).toBe(2);
  expect(receivedCommentStrings).toEqual(
    expect.arrayContaining(expectedCommentStrings)
  );
});

test("evaluate can evaluate with summary evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customSummaryEvaluator = (
    runs: Run[],
    examples?: Example[]
  ): Promise<EvaluationResult> => {
    const runIds = runs.map(({ id }) => id).join(", ");
    const exampleIds = examples?.map(({ id }) => id).join(", ");
    return Promise.resolve({
      key: "MyCustomScore",
      score: 1,
      comment: `Runs: ${runIds} Examples: ${exampleIds}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators: [customSummaryEvaluator],
    description: "evaluate can evaluate with summary evaluators",
  });

  expect(evalRes.summaryResults.results).toHaveLength(1);
  expect(evalRes.summaryResults.results[0].key).toBe("MyCustomScore");
  expect(evalRes.summaryResults.results[0].score).toBe(1);
  const allRuns = evalRes.results.map(({ run }) => run);
  const allExamples = evalRes.results.map(({ example }) => example);
  const runIds = allRuns.map(({ id }) => id).join(", ");
  const exampleIds = allExamples.map(({ id }) => id).join(", ");
  expect(evalRes.summaryResults.results[0].comment).toBe(
    `Runs: ${runIds} Examples: ${exampleIds}`
  );
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(firstRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(firstRun.outputs?.foo).toBeLessThanOrEqual(3);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(secondRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(secondRun.outputs?.foo).toBeLessThanOrEqual(3);
});

test.skip("can iterate over evaluate results", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = async (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };
  const evaluator = {
    evaluateRun: customEvaluator,
  };
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [evaluator],
    description: "can iterate over evaluate results",
  });

  for await (const item of evalRes) {
    console.log("item", item);
  }
});

test("can pass multiple evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluatorOne = async (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };
  const customEvaluatorTwo = async (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };
  const evaluators = [
    { evaluateRun: customEvaluatorOne },
    { evaluateRun: customEvaluatorTwo },
  ];
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators,
    description: "can pass multiple evaluators",
  });
  expect(evalRes.results).toHaveLength(2);
  const firstEvalResults = evalRes.results[0];
  expect(firstEvalResults.evaluationResults.results).toHaveLength(2);

  const firstRun = firstEvalResults.run;
  const firstExample = firstEvalResults.example;
  const receivedCommentStrings = firstEvalResults.evaluationResults.results
    .map(({ comment }) => comment)
    .filter((c): c is string => !!c);
  const expectedCommentStrings = `Run: ${firstRun.id} Example: ${firstExample?.id}`;
  // Checks that both evaluators were called with the expected run and example
  expect(receivedCommentStrings).toEqual(
    expect.arrayContaining([expectedCommentStrings, expectedCommentStrings])
  );
});

test("split info saved correctly", async () => {
  const client = new Client();
  // create a new dataset
  await client.createDataset(TESTING_DATASET_NAME2, {
    description:
      "For testing purposed. Is created & deleted for each test run.",
  });
  // create examples
  await client.createExamples({
    inputs: [{ input: 1 }, { input: 2 }, { input: 3 }],
    outputs: [{ output: 2 }, { output: 3 }, { output: 4 }],
    splits: [["test"], ["train"], ["validation", "test"]],
    datasetName: TESTING_DATASET_NAME2,
  });

  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };
  await evaluate(targetFunc, {
    data: client.listExamples({ datasetName: TESTING_DATASET_NAME2 }),
    description: "splits info saved correctly",
  });

  const exp = client.listProjects({
    referenceDatasetName: TESTING_DATASET_NAME2,
  });
  let myExp: TracerSession | null = null;
  for await (const session of exp) {
    myExp = session;
  }
  expect(myExp?.extra?.metadata?.dataset_splits.sort()).toEqual(
    ["test", "train", "validation"].sort()
  );

  await evaluate(targetFunc, {
    data: client.listExamples({
      datasetName: TESTING_DATASET_NAME2,
      splits: ["test"],
    }),
    description: "splits info saved correctly",
  });

  const exp2 = client.listProjects({
    referenceDatasetName: TESTING_DATASET_NAME2,
  });
  let myExp2: TracerSession | null = null;
  for await (const session of exp2) {
    if (myExp2 === null || session.start_time > myExp2.start_time) {
      myExp2 = session;
    }
  }

  expect(myExp2?.extra?.metadata?.dataset_splits.sort()).toEqual(
    ["test", "validation"].sort()
  );

  await evaluate(targetFunc, {
    data: client.listExamples({
      datasetName: TESTING_DATASET_NAME2,
      splits: ["train"],
    }),
    description: "splits info saved correctly",
  });

  const exp3 = client.listProjects({
    referenceDatasetName: TESTING_DATASET_NAME2,
  });
  let myExp3: TracerSession | null = null;
  for await (const session of exp3) {
    if (myExp3 === null || session.start_time > myExp3.start_time) {
      myExp3 = session;
    }
  }

  expect(myExp3?.extra?.metadata?.dataset_splits.sort()).toEqual(
    ["train"].sort()
  );
});

test("can pass multiple summary evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customSummaryEvaluator = (
    runs: Run[],
    examples?: Example[]
  ): Promise<EvaluationResult> => {
    const runIds = runs.map(({ id }) => id).join(", ");
    const exampleIds = examples?.map(({ id }) => id).join(", ");
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Runs: ${runIds} Examples: ${exampleIds}`,
    });
  };
  const summaryEvaluators = [customSummaryEvaluator, customSummaryEvaluator];
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators,
    description: "can pass multiple summary evaluators",
  });
  expect(evalRes.results).toHaveLength(2);

  const allRuns = evalRes.results.map(({ run }) => run);
  const allExamples = evalRes.results.map(({ example }) => example);
  const runIds = allRuns.map(({ id }) => id).join(", ");
  const exampleIds = allExamples.map(({ id }) => id).join(", ");

  const summaryResults = evalRes.summaryResults.results;
  expect(summaryResults).toHaveLength(2);

  const receivedCommentStrings = summaryResults
    .map(({ comment }) => comment)
    .filter((c): c is string => !!c);
  const expectedCommentString = `Runs: ${runIds} Examples: ${exampleIds}`;
  // Checks that both evaluators were called with the expected run and example
  expect(receivedCommentStrings).toEqual(
    expect.arrayContaining([expectedCommentString, expectedCommentString])
  );
});

test("can pass AsyncIterable of Example's to evaluator instead of dataset name", async () => {
  const client = new Client();
  const examplesIterator = client.listExamples({
    datasetName: TESTING_DATASET_NAME,
  });

  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: examplesIterator,
    evaluators: [customEvaluator],
    description: "can pass AsyncIterable of Example's to evaluator",
  });

  const firstEvalResults = evalRes.results[0];
  const runId = firstEvalResults.run.id;
  const exampleId = firstEvalResults.example.id;
  const expectedCommentStrings = `Run: ${runId} Example: ${exampleId}`;
  const receivedCommentStrings =
    firstEvalResults.evaluationResults.results[0].comment;

  expect(evalRes.results).toHaveLength(2);
  expect(firstEvalResults.evaluationResults.results).toHaveLength(1);
  expect(receivedCommentStrings).toEqual(expectedCommentStrings);
});

test("max concurrency works with custom evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [customEvaluator],
    maxConcurrency: 1,
    description: "max concurrency works with custom evaluators",
  });

  expect(evalRes.results).toHaveLength(2);
  const firstEvalResults = evalRes.results[0];
  const runId = firstEvalResults.run.id;
  const exampleId = firstEvalResults.example.id;
  const expectedCommentStrings = `Run: ${runId} Example: ${exampleId}`;
  const receivedCommentStrings =
    firstEvalResults.evaluationResults.results[0].comment;

  expect(evalRes.results).toHaveLength(2);
  expect(firstEvalResults.evaluationResults.results).toHaveLength(1);
  expect(receivedCommentStrings).toEqual(expectedCommentStrings);
});

test("max concurrency works with summary evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customSummaryEvaluator = (
    runs: Run[],
    examples?: Example[]
  ): Promise<EvaluationResult> => {
    const runIds = runs.map(({ id }) => id).join(", ");
    const exampleIds = examples?.map(({ id }) => id).join(", ");
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Runs: ${runIds} Examples: ${exampleIds}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators: [customSummaryEvaluator],
    maxConcurrency: 1,
    description: "max concurrency works with summary evaluators",
  });

  expect(evalRes.results).toHaveLength(2);

  const allRuns = evalRes.results.map(({ run }) => run);
  const allExamples = evalRes.results.map(({ example }) => example);
  const runIds = allRuns.map(({ id }) => id).join(", ");
  const exampleIds = allExamples.map(({ id }) => id).join(", ");

  const summaryResults = evalRes.summaryResults.results;
  expect(summaryResults).toHaveLength(1);

  const receivedCommentStrings = summaryResults[0].comment;
  const expectedCommentString = `Runs: ${runIds} Examples: ${exampleIds}`;
  // Checks that both evaluators were called with the expected run and example
  expect(receivedCommentStrings).toEqual(expectedCommentString);
});

test.skip("Target func can be a runnable", async () => {
  const targetFunc = RunnableSequence.from([
    RunnableLambda.from((input: Record<string, any>) => ({
      foo: input.input + 1,
    })).withConfig({ runName: "First Step" }),
    RunnableLambda.from((input: { foo: number }) => ({
      foo: input.foo + 1,
    })).withConfig({ runName: "Second Step" }),
  ]);

  const customEvaluator = async (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };
  const evaluator = {
    evaluateRun: customEvaluator,
  };
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [evaluator],
    description: "Target func can be a runnable",
  });

  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  // The examples are not always in the same order, so it should always be 2 or 3
  expect(firstRun.outputs?.foo).toBeGreaterThanOrEqual(2);
  expect(firstRun.outputs?.foo).toBeLessThanOrEqual(3);

  const firstExample = evalRes.results[0].example;
  expect(firstExample).toBeDefined();

  const firstEvalResults = evalRes.results[0].evaluationResults;
  expect(firstEvalResults.results).toHaveLength(1);
  expect(firstEvalResults.results[0].key).toEqual("key");
  expect(firstEvalResults.results[0].score).toEqual(1);

  // check if the evaluated function has valid children
  const gatheredChildRunNames = [];
  const queue = [firstRun];
  const visited = new Set<string>();
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current.id)) continue;
    visited.add(current.id);
    if (current.child_runs) {
      gatheredChildRunNames.push(...current.child_runs.map((run) => run.name));
      queue.push(...current.child_runs);
    }
  }

  expect(gatheredChildRunNames).toEqual(
    expect.arrayContaining(["RunnableSequence", "First Step", "Second Step"])
  );
});

test("evaluate can accept array of examples", async () => {
  const client = new Client();
  const examplesIterator = client.listExamples({
    datasetName: TESTING_DATASET_NAME,
  });
  const examples: Example[] = [];
  for await (const example of examplesIterator) {
    examples.push(example);
  }

  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run, example?: Example) => {
    return Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: examples,
    evaluators: [customEvaluator],
    description: "evaluate can accept array of examples",
  });

  const firstEvalResults = evalRes.results[0];
  const runId = firstEvalResults.run.id;
  const exampleId = firstEvalResults.example.id;
  const expectedCommentStrings = `Run: ${runId} Example: ${exampleId}`;
  const receivedCommentStrings =
    firstEvalResults.evaluationResults.results[0].comment;

  expect(evalRes.results).toHaveLength(2);
  expect(firstEvalResults.evaluationResults.results).toHaveLength(1);
  expect(receivedCommentStrings).toEqual(expectedCommentStrings);
});

test("evaluate accepts evaluators which return multiple feedback keys", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return { foo: input.input + 1 };
  };

  const customEvaluator = (
    run: Run,
    example?: Example
  ): Promise<EvaluationResults> => {
    return Promise.resolve({
      results: [
        {
          key: "first-key",
          score: 1,
          comment: `Run: ${run.id} Example: ${example?.id}`,
        },
        {
          key: "second-key",
          score: 2,
          comment: `Run: ${run.id} Example: ${example?.id}`,
        },
      ],
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [customEvaluator],
    description: "evaluate can evaluate with custom evaluators",
  });

  expect(evalRes.results).toHaveLength(2);

  const comment = `Run: ${evalRes.results[0].run.id} Example: ${evalRes.results[0].example.id}`;
  expect(evalRes.results[0].evaluationResults.results).toMatchObject([
    { key: "first-key", score: 1, comment },
    { key: "second-key", score: 2, comment },
  ]);
});

// Skipping for speed in CI
test.skip("evaluate can handle evaluators with object parameters", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const objectEvaluator = ({
    inputs,
    outputs,
    referenceOutputs,
  }: {
    inputs?: Record<string, any>;
    outputs?: Record<string, any>;
    referenceOutputs?: Record<string, any>;
  }) => {
    return {
      key: "object_evaluator",
      score: outputs?.foo === referenceOutputs?.output ? 1 : 0,
      comment: `Input: ${inputs?.input}, Output: ${outputs?.foo}, Expected: ${referenceOutputs?.output}`,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [objectEvaluator],
    description: "evaluate can handle evaluators with object parameters",
  });

  expect(evalRes.results).toHaveLength(2);

  // Check first result
  const firstResult = evalRes.results[0];
  expect(firstResult.evaluationResults.results).toHaveLength(1);
  const firstEval = firstResult.evaluationResults.results[0];
  expect(firstEval.key).toBe("object_evaluator");
  expect(firstEval.score).toBeDefined();
  expect(firstEval.comment).toContain("Input:");
  expect(firstEval.comment).toContain("Output:");
  expect(firstEval.comment).toContain("Expected:");

  // Check second result
  const secondResult = evalRes.results[1];
  expect(secondResult.evaluationResults.results).toHaveLength(1);
  const secondEval = secondResult.evaluationResults.results[0];
  expect(secondEval.key).toBe("object_evaluator");
  expect(secondEval.score).toBeDefined();
  expect(secondEval.comment).toContain("Input:");
  expect(secondEval.comment).toContain("Output:");
  expect(secondEval.comment).toContain("Expected:");
});

// Skipping for speed in CI
test.skip("evaluate can mix evaluators with different parameter styles", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  // Traditional style evaluator
  const traditionalEvaluator = (run: Run, example?: Example) => {
    return {
      key: "traditional",
      score: run.outputs?.foo === example?.outputs?.output ? 1 : 0,
    };
  };

  // Object style evaluator
  const objectEvaluator = ({
    outputs,
    referenceOutputs,
  }: {
    outputs?: Record<string, any>;
    referenceOutputs?: Record<string, any>;
  }) => {
    return {
      key: "object_style",
      score: outputs?.foo === referenceOutputs?.output ? 1 : 0,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [traditionalEvaluator, objectEvaluator],
    description: "evaluate can mix evaluators with different parameter styles",
  });

  expect(evalRes.results).toHaveLength(2);

  // Check both evaluators ran for each example
  for (const result of evalRes.results) {
    expect(result.evaluationResults.results).toHaveLength(2);

    const traditionalResult = result.evaluationResults.results.find(
      (r) => r.key === "traditional"
    );
    expect(traditionalResult).toBeDefined();
    expect(typeof traditionalResult?.score).toBe("number");

    const objectResult = result.evaluationResults.results.find(
      (r) => r.key === "object_style"
    );
    expect(objectResult).toBeDefined();
    expect(typeof objectResult?.score).toBe("number");
  }
});

// Skipping for speed in CI
test.skip("evaluate handles partial object parameters correctly", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  // Evaluator that only uses outputs and referenceOutputs
  const outputOnlyEvaluator = ({
    outputs,
    referenceOutputs,
  }: {
    outputs?: Record<string, any>;
    referenceOutputs?: Record<string, any>;
  }) => {
    return {
      key: "output_only",
      score: outputs?.foo === referenceOutputs?.output ? 1 : 0,
    };
  };

  // Evaluator that only uses run and example
  const runOnlyEvaluator = ({
    run,
    example,
  }: {
    run?: Run;
    example?: Example;
  }) => {
    return {
      key: "run_only",
      score: run?.outputs?.foo === example?.outputs?.output ? 1 : 0,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [outputOnlyEvaluator, runOnlyEvaluator],
    description: "evaluate handles partial object parameters correctly",
  });

  expect(evalRes.results).toHaveLength(2);

  // Check both evaluators ran for each example
  for (const result of evalRes.results) {
    expect(result.evaluationResults.results).toHaveLength(2);

    const outputResult = result.evaluationResults.results.find(
      (r) => r.key === "output_only"
    );
    expect(outputResult).toBeDefined();
    expect(typeof outputResult?.score).toBe("number");

    const runResult = result.evaluationResults.results.find(
      (r) => r.key === "run_only"
    );
    expect(runResult).toBeDefined();
    expect(typeof runResult?.score).toBe("number");
  }
});

test("evaluate handles async object-style evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const asyncEvaluator = async ({
    outputs,
    referenceOutputs,
  }: {
    outputs?: Record<string, any>;
    referenceOutputs?: Record<string, any>;
  }) => {
    // Simulate async operation
    await new Promise((resolve) => setTimeout(resolve, 10));
    return {
      key: "async_evaluator",
      score: outputs?.foo === referenceOutputs?.output ? 1 : 0,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [asyncEvaluator],
    description: "evaluate handles async object-style evaluators",
  });

  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    expect(result.evaluationResults.results).toHaveLength(1);
    const evalResult = result.evaluationResults.results[0];
    expect(evalResult.key).toBe("async_evaluator");
    expect(typeof evalResult.score).toBe("number");
  }
});

// Skipping for speed in CI
test.skip("evaluate can evaluate with updated summary evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const customSummaryEvaluator = ({
    runs,
    examples,
    inputs,
    outputs,
    referenceOutputs,
  }: {
    runs?: Run[];
    examples?: Example[];
    inputs?: Record<string, any>[];
    outputs?: Record<string, any>[];
    referenceOutputs?: Record<string, any>[];
  }): Promise<EvaluationResult> => {
    const runIds = runs?.map(({ id }) => id).join(", ") || "";
    const exampleIds = examples?.map(({ id }) => id).join(", ");
    const inputValues = inputs?.map((input) => input.input).join(", ");
    const outputValues = outputs?.map((output) => output.foo).join(", ");
    const referenceOutputValues = referenceOutputs
      ?.map((ref) => ref.output)
      .join(", ");

    return Promise.resolve({
      key: "UpdatedSummaryEvaluator",
      score: 1,
      comment: `Runs: ${runIds} Examples: ${exampleIds} Inputs: ${inputValues} Outputs: ${outputValues} ReferenceOutputs: ${referenceOutputValues}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators: [customSummaryEvaluator],
    description: "evaluate can evaluate with updated summary evaluators",
  });

  expect(evalRes.summaryResults.results).toHaveLength(1);
  expect(evalRes.summaryResults.results[0].key).toBe("UpdatedSummaryEvaluator");
  expect(evalRes.summaryResults.results[0].score).toBe(1);

  const allRuns = evalRes.results.map(({ run }) => run);
  const allExamples = evalRes.results.map(({ example }) => example);
  const allInputs = evalRes.results.map(({ example }) => example.inputs);
  const allOutputs = evalRes.results.map(({ run }) => run.outputs);
  const allReferenceOutputs = evalRes.results.map(
    ({ example }) => example.outputs
  );

  const runIds = allRuns.map(({ id }) => id).join(", ");
  const exampleIds = allExamples.map(({ id }) => id).join(", ");
  const inputValues = allInputs.map((input) => input.input).join(", ");
  const outputValues = allOutputs.map((output) => output?.foo).join(", ");
  const referenceOutputValues = allReferenceOutputs
    .map((ref) => ref?.output)
    .join(", ");

  expect(evalRes.summaryResults.results[0].comment).toBe(
    `Runs: ${runIds} Examples: ${exampleIds} Inputs: ${inputValues} Outputs: ${outputValues} ReferenceOutputs: ${referenceOutputValues}`
  );
});

test("evaluate handles summary evaluator parameters correctly", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  // Summary evaluator that only uses inputs, outputs, and referenceOutputs
  const outputOnlySummaryEvaluator = ({
    inputs,
    outputs,
    referenceOutputs,
  }: {
    inputs?: Record<string, any>[];
    outputs?: Record<string, any>[];
    referenceOutputs?: Record<string, any>[];
  }): Promise<EvaluationResult> => {
    const inputValues = inputs?.map((input) => input.input).join(", ") || "";
    const outputValues = outputs?.map((output) => output.foo).join(", ") || "";
    const referenceOutputValues = referenceOutputs
      ?.map((ref) => ref?.output)
      .join(", ");

    // Calculate average difference between outputs and reference outputs
    const avgDiff =
      outputs?.reduce((sum, output, i) => {
        return sum + Math.abs(output?.foo - referenceOutputs?.[i]?.output);
      }, 0) || 0;

    return Promise.resolve({
      key: "OutputOnlySummaryEvaluator",
      score: avgDiff === 0 ? 1 : 0,
      comment: `Inputs: ${inputValues} Outputs: ${outputValues} ReferenceOutputs: ${referenceOutputValues} AvgDiff: ${avgDiff}`,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators: [outputOnlySummaryEvaluator],
    description: "evaluate handles partial summary evaluator parameters",
  });

  expect(evalRes.summaryResults.results).toHaveLength(1);
  const summaryResult = evalRes.summaryResults.results[0];
  expect(summaryResult.key).toBe("OutputOnlySummaryEvaluator");
  expect(typeof summaryResult.score).toBe("number");

  // Verify the comment contains all the expected parts
  const allInputs = evalRes.results.map(({ example }) => example.inputs);
  const allOutputs = evalRes.results.map(({ run }) => run.outputs);
  const allReferenceOutputs = evalRes.results.map(
    ({ example }) => example.outputs
  );

  const inputValues = allInputs.map((input) => input.input).join(", ");
  const outputValues = allOutputs.map((output) => output?.foo).join(", ");
  const referenceOutputValues = allReferenceOutputs
    .map((ref) => ref?.output)
    .join(", ");

  // Calculate expected average difference
  const expectedAvgDiff =
    allOutputs.reduce((sum, output, i) => {
      return sum + Math.abs(output?.foo - allReferenceOutputs[i]?.output);
    }, 0) / allOutputs.length;

  expect(summaryResult.comment).toBe(
    `Inputs: ${inputValues} Outputs: ${outputValues} ReferenceOutputs: ${referenceOutputValues} AvgDiff: ${expectedAvgDiff}`
  );
});

test("evaluate handles comparative target with ComparativeEvaluateOptions", async () => {
  const client = new Client();

  // First, create two experiments to compare
  const targetFunc1 = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const targetFunc2 = (input: Record<string, any>) => {
    return {
      foo: input.input + 2,
    };
  };

  // Run initial experiments
  const exp1 = await evaluate(targetFunc1, {
    data: TESTING_DATASET_NAME,
    description: "First experiment for comparison",
  });

  const exp2 = await evaluate(targetFunc2, {
    data: TESTING_DATASET_NAME,
    description: "Second experiment for comparison",
  });

  await Promise.all(
    [exp1, exp2].flatMap(({ results }) =>
      results.flatMap(({ run }) => waitUntilRunFound(client, run.id))
    )
  );
  // Create comparative evaluator
  const comparativeEvaluator = ({
    runs,
    example,
  }: {
    runs: Run[];
    example: Example;
  }) => {
    if (!runs || !example) throw new Error("Missing required parameters");

    // Compare outputs from both runs
    const scores = Object.fromEntries(
      runs.map((run) => [
        run.id,
        run.outputs?.foo === example.outputs?.output ? 1 : 0,
      ])
    );

    return {
      key: "comparative_score",
      scores,
    };
  };

  // Run comparative evaluation
  const compareRes = await evaluate(
    [exp1.experimentName, exp2.experimentName],
    {
      evaluators: [comparativeEvaluator],
      description: "Comparative evaluation test",
      randomizeOrder: true,
      loadNested: false,
    }
  );

  // Verify we got ComparisonEvaluationResults
  expect(compareRes.experimentName).toBeDefined();
  expect(compareRes.experimentName).toBeDefined();
  expect(compareRes.results).toBeDefined();
  expect(Array.isArray(compareRes.results)).toBe(true);

  // Check structure of comparison results
  for (const result of compareRes.results) {
    expect(result.key).toBe("comparative_score");
    expect(result.scores).toBeDefined();
    expect(Object.keys(result.scores)).toHaveLength(2); // Should have scores for both experiments
  }
});

test("evaluate enforces correct evaluator types for comparative evaluation at runtime", async () => {
  const exp1 = await evaluate(
    (input: Record<string, any>) => ({ foo: input.input + 1 }),
    {
      data: TESTING_DATASET_NAME,
    }
  );

  const exp2 = await evaluate(
    (input: Record<string, any>) => ({ foo: input.input + 2 }),
    {
      data: TESTING_DATASET_NAME,
    }
  );

  // Create a standard evaluator (wrong type)
  const standardEvaluator = (run: Run, example: Example) => ({
    key: "standard",
    score: run.outputs?.foo === example.outputs?.output ? 1 : 0,
  });

  await expect(
    // @ts-expect-error - Should error because standardEvaluator is not a ComparativeEvaluator
    evaluate([exp1.experimentName, exp2.experimentName], {
      evaluators: [standardEvaluator],
      description: "Should fail at runtime",
    })
  ).rejects.toThrow(); // You might want to be more specific about the error message
});
