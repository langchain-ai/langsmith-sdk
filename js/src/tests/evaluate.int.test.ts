import { evaluate } from "../evaluation/runner.js";

test("evaluate can evaluate", async () => {
  const dummyDatasetName = "ds-somber-yesterday-36";
  const evalFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return {
      foo: input.input + 1,
    };
  };

  const evalRes = await evaluate(evalFunc, { data: dummyDatasetName });

  expect(evalRes.results).toHaveLength(2);

  expect(evalRes.results[0].run).toBeDefined();
  expect(evalRes.results[0].example).toBeDefined();
  // expect(evalRes.results[0].evaluationResults).toBeDefined();
  const firstRun = evalRes.results[0].run;
  expect(firstRun.outputs).toEqual({ foo: 3 });

  expect(evalRes.results[1].run).toBeDefined();
  expect(evalRes.results[1].example).toBeDefined();
  // expect(evalRes.results[1].evaluationResults).toBeDefined();
  const secondRun = evalRes.results[1].run;
  expect(secondRun.outputs).toEqual({ foo: 2 });
});
