import { AsyncLocalStorage } from "node:async_hooks";
import ls, { type SimpleEvaluator } from "../jest/index.js";

const myEvaluator: SimpleEvaluator = ({ expected, actual }) => {
  if (actual.bar === expected.bar) {
    return {
      key: "quality",
      score: 1,
    };
  } else if (actual.bar === "goodval") {
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

const unrelatedStore = new AsyncLocalStorage();
unrelatedStore.enterWith("value"); // Ensure that this works despite https://github.com/jestjs/jest/issues/13653

ls.describe("js unit testing test demo", () => {
  ls.test({ inputs: { foo: "bar" }, outputs: { bar: "qux" } })(
    "Should succeed with some defined evaluator",
    async ({ inputs: _inputs, outputs }) => {
      const myApp = () => {
        return outputs;
      };
      const res = myApp();
      await expect(res).gradedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    },
    180_000
  );

  ls.test({ inputs: { foo: "bar" }, outputs: { foo: "bar" } })(
    "Should kind of succeed with some defined evaluator",
    async ({ inputs: _inputs, outputs: _outputs }) => {
      const myApp = () => {
        return { bar: "goodval" };
      };
      const res = myApp();
      await expect(res).gradedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    },
    180_000
  );

  ls.test({ inputs: { foo: "bad" }, outputs: { baz: "qux" } })(
    "Should fail with some defined evaluator",
    async ({ inputs: _inputs, outputs: _outputs }) => {
      const myApp = () => {
        return { bar: "bad" };
      };
      const res = myApp();
      await expect(res).gradedBy(myEvaluator).not.toBeGreaterThanOrEqual(0.5);
      return res;
    },
    180_000
  );

  ls.test.each([
    {
      inputs: {
        one: "uno",
      },
      outputs: {
        ein: "un",
      },
    },
    {
      inputs: {
        two: "dos",
      },
      outputs: {
        zwei: "deux",
      },
    },
  ])("Does the thing", async ({ inputs: _inputs, outputs: _outputs }) => {
    const myApp = () => {
      return { bar: "bad" };
    };
    const res = myApp();
    await expect(res).gradedBy(myEvaluator).not.toBeGreaterThanOrEqual(0.5);
    return res;
  });
});
