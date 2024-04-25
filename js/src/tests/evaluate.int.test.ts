import { EvaluationResult } from "../evaluation/evaluator.js";
import { evaluate } from "../evaluation/runner.js";
import { Example, Run } from "../schemas.js";

const dummyDatasetName = "ds-internal-laborer-16";

test("evaluate can evaluate", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(targetFunc, { data: dummyDatasetName });
  // console.log(evalRes.results)
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();
  const firstRun = evalRes.results[0].run;
  expect(firstRun.outputs).toEqual({ foo: 3 });

  const firstRunResults = evalRes.results[0].evaluationResults;
  expect(firstRunResults.results).toHaveLength(0);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();
  const secondRun = evalRes.results[1].run;
  expect(secondRun.outputs).toEqual({ foo: 2 });

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

  const customEvaluator = async (_: Run) => {
    return Promise.resolve({
      key: "key",
      score: 1,
    });
  };
  const evaluator = {
    evaluateRun: customEvaluator,
  };
  const evalRes = await evaluate(targetFunc, {
    data: dummyDatasetName,
    evaluators: [evaluator],
  });

  console.log(evalRes.results);
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  expect(firstRun.outputs).toEqual({ foo: 3 });

  const firstEvalResults = evalRes.results[0].evaluationResults;
  expect(firstEvalResults.results).toHaveLength(1);
  expect(firstEvalResults.results[0].key).toEqual("key");
  expect(firstEvalResults.results[0].score).toEqual(1);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  expect(secondRun.outputs).toEqual({ foo: 2 });

  const secondEvalResults = evalRes.results[1].evaluationResults;
  expect(secondEvalResults.results).toHaveLength(1);
  expect(secondEvalResults.results[0].key).toEqual("key");
  expect(secondEvalResults.results[0].score).toEqual(1);
});

test("evaluate can evaluate with custom evaluators", async () => {
  const targetFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run, example?: Example) => {
    console.log("customEvaluator", run.id, example?.id);
    return {
      key: "key",
      score: 1,
    };
  };

  const evalRes = await evaluate(targetFunc, {
    data: dummyDatasetName,
    evaluators: [customEvaluator],
  });

  // console.log(evalRes.results);
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  expect(firstRun.outputs).toEqual({ foo: 3 });

  const firstEvalResults = evalRes.results[0].evaluationResults;
  expect(firstEvalResults.results).toHaveLength(1);
  expect(firstEvalResults.results[0].key).toEqual("key");
  expect(firstEvalResults.results[0].score).toEqual(1);

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  expect(secondRun.outputs).toEqual({ foo: 2 });

  const secondEvalResults = evalRes.results[1].evaluationResults;
  expect(secondEvalResults.results).toHaveLength(1);
  expect(secondEvalResults.results[0].key).toEqual("key");
  expect(secondEvalResults.results[0].score).toEqual(1);
});

test.skip("evaluate can evaluate with summary evaluators", async () => {
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
    const comment = runs.map(({ id }) => id).join(", ");
    console.log("customSummaryEvaluator", runs.length, examples?.length);
    return Promise.resolve({
      key: "key",
      score: 1,
      comment,
    });
  };

  const evalRes = await evaluate(targetFunc, {
    data: dummyDatasetName,
    summaryEvaluators: [customSummaryEvaluator],
  });
  // console.log(evalRes)

  expect(evalRes.summaryResults.results).toHaveLength(1);
  expect(evalRes.summaryResults.results[0].key).toBe("key");
  expect(evalRes.summaryResults.results[0].score).toBe(1);
  const allRuns = evalRes.results.map(({ run }) => run);
  expect(evalRes.summaryResults.results[0].comment).toBe(allRuns.map(({ id }) => id).join(", "));
  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  expect(evalRes.results[0].evaluationResults).toBeDefined();

  const firstRun = evalRes.results[0].run;
  expect(firstRun.outputs).toEqual({ foo: 3 });

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  expect(evalRes.results[1].evaluationResults).toBeDefined();

  const secondRun = evalRes.results[1].run;
  expect(secondRun.outputs).toEqual({ foo: 2 });
});
