import { evaluate } from "../evaluation/runner.js";

test("evaluate can evaluate", async () => {
  const dummyDatasetName = "ds-somber-yesterday-36";
  const evalFunc = (input: Record<string, any>) => {
    console.log("__input__", input);
    return input;
  };
  // const evalRunnable = new RunnableLambda({ func: (input: Record<string, any>) => {
  //   console.log("input", input);
  // }});

  const evalRes = await evaluate(evalFunc, dummyDatasetName);
  console.log(evalRes.results);
  expect(evalRes.processedCount).toBeGreaterThan(0);
});
