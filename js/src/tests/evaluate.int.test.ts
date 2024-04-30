import { EvaluationResult } from "../evaluation/evaluator.js";
import { evaluate } from "../evaluation/_runner.js";
import { Example, Run } from "../schemas.js";
import { Client } from "../index.js";
import { afterAll, beforeAll } from "@jest/globals";
import { RunnableLambda } from "@langchain/core/runnables";

const TESTING_DATASET_NAME = "test_dataset_js_evaluate_123";

beforeAll(async () => {
  const client = new Client();
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
});

afterAll(async () => {
  const client = new Client();
  await client.deleteDataset({
    datasetName: TESTING_DATASET_NAME,
  });
});

test("evaluate can evaluate", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(targetFunc, { data: TESTING_DATASET_NAME });
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

test("evaluate can evaluate with RunEvaluator evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
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

test("evaluate can evaluate with custom evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
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
    console.log("__input__", input);
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
  });

  expect(evalRes.summaryResults.results).toHaveLength(1);
  expect(evalRes.summaryResults.results[0].key).toBe("key");
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
    console.log("__input__", input);
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
  });

  for await (const item of evalRes) {
    console.log("item", item);
  }
});

test("can pass multiple evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
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
    {
      evaluateRun: customEvaluatorOne,
    },
    {
      evaluateRun: customEvaluatorTwo,
    },
  ];
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: evaluators,
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

test("can pass multiple summary evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
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
    console.log("__input__", input);
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
    console.log("__input__", input);
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
    console.log("__input__", input);
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

test("Target func can be a runnable", async () => {
  const targetFunc = new RunnableLambda({
    func: (input: Record<string, any>) => {
      console.log("__input__", input);
      return {
        foo: input.input + 1,
      };
    },
  });

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
    console.log("__input__", input);
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
