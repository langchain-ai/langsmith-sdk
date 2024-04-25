import { evaluate } from "../evaluation/runner.js";
import { Run } from "../schemas.js";

const dummyDatasetName = "ds-internal-laborer-16";

test("evaluate can evaluate", async () => {
  const evalFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(evalFunc, { data: dummyDatasetName });
  // console.log(evalRes.results)
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

test("evaluate can evaluate with RunEvaluator evaluators", async () => {
  const evalFunc = (input: Record<string, any>) => {
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
  const evalRes = await evaluate(evalFunc, {
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

test.skip("evaluate can evaluate with custom evaluators", async () => {
  const evalFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const customEvaluator = (run: Run) => {
    return {
      key: run.id,
    };
  };

  const evalRes = await evaluate(evalFunc, {
    data: dummyDatasetName,
    evaluators: [customEvaluator],
  });
  console.log(evalRes.results);
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

test.skip("evaluate can evaluate with summary evaluators", async () => {
  const evalFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(evalFunc, { data: dummyDatasetName });
  // console.log(evalRes.results)
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
