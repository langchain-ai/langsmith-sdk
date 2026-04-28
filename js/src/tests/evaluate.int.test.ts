import {
  EvaluationResult,
  EvaluationResults,
} from "../evaluation/evaluator.js";
import { evaluate } from "../evaluation/_runner.js";
import { waitUntilRunFound } from "./utils.js";
import { Example, Run, TracerSession } from "../schemas.js";
import { Client } from "../index.js";
import { afterAll, beforeAll } from "@jest/globals";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";

import * as ai from "ai";
import { openai } from "@ai-sdk/openai";
import { wrapAISDK } from "../experimental/vercel/index.js";

const { generateText } = wrapAISDK(ai);

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

// Consolidated: covers basic `evaluate`, multiple evaluators, array / AsyncIterable
// data inputs. Previously split across "evaluate can evaluate",
// "can pass multiple evaluators", "can pass AsyncIterable of Example's...",
// and "evaluate can accept array of examples".
test("evaluate handles various data inputs and evaluator shapes", async () => {
  const client = new Client();
  const targetFunc = (input: Record<string, any>) => {
    return {
      foo: input.input + 1,
    };
  };

  const makeEvaluator = () => (run: Run, example?: Example) =>
    Promise.resolve({
      key: "key",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });

  // 1) Basic evaluate with no evaluators, dataset-name data.
  const basicRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    description: "Experiment from evaluate can evaluate integration test",
  });
  expect(basicRes.results).toHaveLength(2);
  for (const result of basicRes.results) {
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();
    expect(result.run.outputs?.foo).toBeGreaterThanOrEqual(2);
    expect(result.run.outputs?.foo).toBeLessThanOrEqual(3);
    expect(result.evaluationResults.results).toHaveLength(0);
  }

  // 2) Multiple evaluators (object-form with evaluateRun) against dataset-name data.
  const multiEvalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [
      { evaluateRun: makeEvaluator() },
      { evaluateRun: makeEvaluator() },
    ],
    description: "can pass multiple evaluators",
  });
  expect(multiEvalRes.results).toHaveLength(2);
  const multiFirst = multiEvalRes.results[0];
  expect(multiFirst.evaluationResults.results).toHaveLength(2);
  const multiExpected = `Run: ${multiFirst.run.id} Example: ${multiFirst.example?.id}`;
  expect(
    multiFirst.evaluationResults.results
      .map(({ comment }) => comment)
      .filter((c): c is string => !!c),
  ).toEqual(expect.arrayContaining([multiExpected, multiExpected]));

  // 3) AsyncIterable of Examples as data input.
  const asyncIterableRes = await evaluate(targetFunc, {
    data: client.listExamples({ datasetName: TESTING_DATASET_NAME }),
    evaluators: [makeEvaluator()],
    description: "can pass AsyncIterable of Example's to evaluator",
  });
  expect(asyncIterableRes.results).toHaveLength(2);
  const asyncIterableFirst = asyncIterableRes.results[0];
  expect(asyncIterableFirst.evaluationResults.results).toHaveLength(1);
  expect(asyncIterableFirst.evaluationResults.results[0].comment).toEqual(
    `Run: ${asyncIterableFirst.run.id} Example: ${asyncIterableFirst.example.id}`,
  );

  // 4) Array of Examples as data input.
  const examples: Example[] = [];
  for await (const example of client.listExamples({
    datasetName: TESTING_DATASET_NAME,
  })) {
    examples.push(example);
  }
  const arrayRes = await evaluate(targetFunc, {
    data: examples,
    evaluators: [makeEvaluator()],
    description: "evaluate can accept array of examples",
  });
  expect(arrayRes.results).toHaveLength(2);
  const arrayFirst = arrayRes.results[0];
  expect(arrayFirst.evaluationResults.results).toHaveLength(1);
  expect(arrayFirst.evaluationResults.results[0].comment).toEqual(
    `Run: ${arrayFirst.run.id} Example: ${arrayFirst.example.id}`,
  );
});

test("evaluate can repeat", async () => {
  const client = new Client();
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

  // numRepetitions should also be honored when data is a pre-fetched Example[].
  const examples: Example[] = [];
  for await (const example of client.listExamples({
    datasetName: TESTING_DATASET_NAME,
  })) {
    examples.push(example);
  }
  const arrayRepeatRes = await evaluate(targetFunc, {
    data: examples,
    description: "numRepetitions honored with Example[] data",
    numRepetitions: 3,
  });
  expect(arrayRepeatRes.results).toHaveLength(examples.length * 3);
  const runCountByExampleId = new Map<string, number>();
  for (const result of arrayRepeatRes.results) {
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    const exampleId = result.example.id;
    runCountByExampleId.set(
      exampleId,
      (runCountByExampleId.get(exampleId) ?? 0) + 1,
    );
  }
  for (const example of examples) {
    expect(runCountByExampleId.get(example.id)).toBe(3);
  }
});

// Consolidated: covers summary evaluators end-to-end with single evaluator,
// multiple evaluators, maxConcurrency, and object-style parameters (inputs,
// outputs, referenceOutputs). Previously split across
// "evaluate can evaluate with summary evaluators",
// "can pass multiple summary evaluators",
// "max concurrency works with summary evaluators", and
// "evaluate handles summary evaluator parameters correctly".
test("evaluate works with summary evaluators in various configurations", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return { foo: input.input + 1 };
  };

  // Traditional-signature summary evaluator (runs, examples) -> EvaluationResult.
  const positionalSummaryEvaluator = (
    runs: Run[],
    examples?: Example[],
  ): Promise<EvaluationResult> => {
    const runIds = runs.map(({ id }) => id).join(", ");
    const exampleIds = examples?.map(({ id }) => id).join(", ");
    return Promise.resolve({
      key: "MyCustomScore",
      score: 1,
      comment: `Runs: ${runIds} Examples: ${exampleIds}`,
    });
  };

  // Object-style summary evaluator that uses inputs / outputs / referenceOutputs.
  const objectStyleSummaryEvaluator = ({
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

  // Run with multiple summary evaluators (both positional-signature variants)
  // plus an object-style evaluator, and use maxConcurrency=1 to exercise the
  // concurrency path.
  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    summaryEvaluators: [
      positionalSummaryEvaluator,
      positionalSummaryEvaluator,
      objectStyleSummaryEvaluator,
    ],
    maxConcurrency: 1,
    description:
      "evaluate works with summary evaluators in various configurations",
  });

  expect(evalRes.results).toHaveLength(2);
  for (const result of evalRes.results) {
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();
    expect(result.run.outputs?.foo).toBeGreaterThanOrEqual(2);
    expect(result.run.outputs?.foo).toBeLessThanOrEqual(3);
  }

  const summaryResults = evalRes.summaryResults.results;
  expect(summaryResults).toHaveLength(3);

  const allRuns = evalRes.results.map(({ run }) => run);
  const allExamples = evalRes.results.map(({ example }) => example);
  const runIds = allRuns.map(({ id }) => id).join(", ");
  const exampleIds = allExamples.map(({ id }) => id).join(", ");
  const expectedPositionalComment = `Runs: ${runIds} Examples: ${exampleIds}`;

  // Both positional summary evaluators produced identical feedback.
  const positionalResults = summaryResults.filter(
    (r) => r.key === "MyCustomScore",
  );
  expect(positionalResults).toHaveLength(2);
  for (const r of positionalResults) {
    expect(r.score).toBe(1);
    expect(r.comment).toBe(expectedPositionalComment);
  }

  // Object-style summary evaluator received inputs/outputs/referenceOutputs.
  const objectStyleResult = summaryResults.find(
    (r) => r.key === "OutputOnlySummaryEvaluator",
  );
  expect(objectStyleResult).toBeDefined();
  expect(typeof objectStyleResult?.score).toBe("number");

  const allInputs = evalRes.results.map(({ example }) => example.inputs);
  const allOutputs = evalRes.results.map(({ run }) => run.outputs);
  const allReferenceOutputs = evalRes.results.map(
    ({ example }) => example.outputs,
  );
  const inputValues = allInputs.map((input) => input.input).join(", ");
  const outputValues = allOutputs.map((output) => output?.foo).join(", ");
  const referenceOutputValues = allReferenceOutputs
    .map((ref) => ref?.output)
    .join(", ");
  const expectedAvgDiff =
    allOutputs.reduce((sum, output, i) => {
      return sum + Math.abs(output?.foo - allReferenceOutputs[i]?.output);
    }, 0) / allOutputs.length;
  expect(objectStyleResult?.comment).toBe(
    `Inputs: ${inputValues} Outputs: ${outputValues} ReferenceOutputs: ${referenceOutputValues} AvgDiff: ${expectedAvgDiff}`,
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
    ["test", "train", "validation"].sort(),
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
    ["test", "validation"].sort(),
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
    ["train"].sort(),
  );
});

// Consolidated: covers maxConcurrency, multi-feedback-key evaluator return values,
// and async object-style evaluators running together. Previously split across
// "max concurrency works with custom evaluators",
// "evaluate accepts evaluators which return multiple feedback keys", and
// "evaluate handles async object-style evaluators".
test("evaluate supports concurrency limits and varied evaluator return types", async () => {
  const targetFunc = (input: Record<string, any>) => {
    return { foo: input.input + 1 };
  };

  // Evaluator that returns a single EvaluationResult (traditional signature).
  const singleKeyEvaluator = (run: Run, example?: Example) =>
    Promise.resolve({
      key: "single",
      score: 1,
      comment: `Run: ${run.id} Example: ${example?.id}`,
    });

  // Evaluator that returns multiple feedback keys via an EvaluationResults object.
  const multiKeyEvaluator = (
    run: Run,
    example?: Example,
  ): Promise<EvaluationResults> =>
    Promise.resolve({
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

  // Async object-style evaluator receiving `{ outputs, referenceOutputs }`.
  const asyncObjectEvaluator = async ({
    outputs,
    referenceOutputs,
  }: {
    outputs?: Record<string, any>;
    referenceOutputs?: Record<string, any>;
  }) => {
    await new Promise((resolve) => setTimeout(resolve, 10));
    return {
      key: "async_evaluator",
      score: outputs?.foo === referenceOutputs?.output ? 1 : 0,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [singleKeyEvaluator, multiKeyEvaluator, asyncObjectEvaluator],
    maxConcurrency: 1,
    description:
      "evaluate supports concurrency limits and varied evaluator return types",
  });

  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    // 1 (single) + 2 (multi) + 1 (async object) = 4 feedback entries per example.
    expect(result.evaluationResults.results).toHaveLength(4);

    const expectedComment = `Run: ${result.run.id} Example: ${result.example?.id}`;

    const single = result.evaluationResults.results.find(
      (r) => r.key === "single",
    );
    expect(single).toBeDefined();
    expect(single?.comment).toEqual(expectedComment);

    const firstKey = result.evaluationResults.results.find(
      (r) => r.key === "first-key",
    );
    expect(firstKey).toMatchObject({
      key: "first-key",
      score: 1,
      comment: expectedComment,
    });

    const secondKey = result.evaluationResults.results.find(
      (r) => r.key === "second-key",
    );
    expect(secondKey).toMatchObject({
      key: "second-key",
      score: 2,
      comment: expectedComment,
    });

    const asyncResult = result.evaluationResults.results.find(
      (r) => r.key === "async_evaluator",
    );
    expect(asyncResult).toBeDefined();
    expect(typeof asyncResult?.score).toBe("number");
  }
});

test("concurrent evaluate restores dataset order before summary", async () => {
  const client = new Client();
  const exampleIterator = client.listExamples({
    datasetName: TESTING_DATASET_NAME,
  });
  const examples: Example[] = [];
  for await (const example of exampleIterator) {
    examples.push(example);
  }

  const orderedExamples = examples.sort(
    (a, b) => Number(a.inputs.input) - Number(b.inputs.input),
  );
  const expectedInputs = orderedExamples.map((example) =>
    Number(example.inputs.input),
  );

  const targetFunc = async (input: Record<string, any>) => {
    await new Promise((resolve) =>
      setTimeout(resolve, input.input === 1 ? 100 : 10),
    );
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = async (run: Run, example?: Example) => {
    await new Promise((resolve) =>
      setTimeout(resolve, Number(example?.inputs.input) === 1 ? 10 : 100),
    );
    return {
      key: "paired",
      score:
        run.outputs?.foo === Number(example?.inputs.input ?? Number.NaN) + 1
          ? 1
          : 0,
      comment: `input:${example?.inputs.input}`,
    };
  };

  const inputOrderSummaryEvaluator = ({
    inputs,
  }: {
    inputs?: Record<string, any>[];
  }): EvaluationResult => {
    return {
      key: "input_order",
      score: 1,
      comment: (inputs ?? []).map((input) => input.input).join(","),
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: orderedExamples,
    evaluators: [customEvaluator],
    summaryEvaluators: [inputOrderSummaryEvaluator],
    targetConcurrency: 2,
    evaluationConcurrency: 2,
    description:
      "concurrent evaluate restores dataset order before summary integration test",
  });

  expect(
    evalRes.results.map(({ example }) => Number(example.inputs.input)),
  ).toEqual(expectedInputs);
  expect(evalRes.results.map(({ run }) => run.outputs?.foo)).toEqual(
    expectedInputs.map((input) => input + 1),
  );
  expect(
    evalRes.results.map(
      ({ evaluationResults }) => evaluationResults.results[0].comment,
    ),
  ).toEqual(expectedInputs.map((input) => `input:${input}`));
  expect(evalRes.summaryResults.results[0].comment).toBe(
    expectedInputs.join(","),
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
      results.flatMap(({ run }) => waitUntilRunFound(client, run.id)),
    ),
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
      ]),
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
    },
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
    },
  );

  const exp2 = await evaluate(
    (input: Record<string, any>) => ({ foo: input.input + 2 }),
    {
      data: TESTING_DATASET_NAME,
    },
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
    }),
  ).rejects.toThrow(); // You might want to be more specific about the error message
});

test("evaluate succeeds with child runs that take a while to resolve", async () => {
  const target = async () => {
    void generateText({
      prompt: "Hello world",
      model: openai("gpt-5-nano"),
    });
    return { foo: "foo" };
  };
  const res = await evaluate(target, {
    data: TESTING_DATASET_NAME,
  });
  expect(res.results.length).toEqual(2);
  for (const result of res.results) {
    // This check is important to ensure the output is set before child promises resolve
    // for AI SDK
    expect(result.run.outputs).toEqual({ foo: "foo" });
  }
});
