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

ls.describe("js unit testing test demo", () => {
  ls.test({ inputs: { foo: "bar" }, outputs: { bar: "qux" } })(
    "Should succeed with some defined evaluator",
    async ({}) => {
      const myApp = () => {
        return { bar: "qux" };
      };
      const res = myApp();
      await expect(res).gradedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    },
    180_000
  );

  ls.test({ inputs: { foo: "bar" }, outputs: { foo: "bar" } })(
    "Should kind of succeed with some defined evaluator",
    async ({}) => {
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
    async ({}) => {
      const myApp = () => {
        return { bar: "bad" };
      };
      const res = myApp();
      await expect(res).gradedBy(myEvaluator).not.toBeGreaterThanOrEqual(0.5);
      return res;
    },
    180_000
  );
});
