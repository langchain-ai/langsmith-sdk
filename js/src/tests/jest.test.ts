/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { RunEvaluatorLike } from "../evaluation/evaluator.js";
import { ls } from "../jest.js";

ls.setup({
  datasetId: "00000000-0000-0000-0000-000000000000",
});

const myEvaluator: RunEvaluatorLike = ({ inputs, outputs }) => {
  if (inputs?.foo === "bar") {
    return {
      key: "quality",
      score: 1,
    };
  } else if (outputs?.foo === "bar") {
    return {
      key: "quality",
      score: 0.5,
    };
  } else {
    return {
      key: "quality",
      score: 0,
    };
  }
};

ls.test({ foo: "bar" })(
  "Should succeed with some defined evaluator",
  async (input) => {
    console.log(input.foo);
    // @ts-expect-error Not a param in the input
    console.log(input.bar);
    const res = { baz: "qux" };
    expect(res).toPassEvaluator(myEvaluator, {});
    return res;
  },
  180_000
);

ls.test("00000000-0000-0000-0000-000000000000")(
  "Should succeed with some defined evaluator",
  async (_inputFromDataset) => {
    const res = { baz: "qux" };
    expect(res).toPassEvaluator(myEvaluator, {});
    return res;
  },
  180_000
);

ls.test.only({ foo: "bad" })(
  "Should fail with some defined evaluator",
  async (input) => {
    console.log(input.foo);
    const res = { baz: "qux" };
    expect(res).toPassEvaluator(myEvaluator, {});
    return res;
  },
  180_000
);
