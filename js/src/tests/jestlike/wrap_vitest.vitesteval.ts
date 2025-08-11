/* eslint-disable import/no-extraneous-dependencies */
import * as vitest from "vitest";
import { SimpleEvaluator, wrapVitest } from "../../vitest/index.mjs";

const ls = wrapVitest(vitest);

const myEvaluator: SimpleEvaluator = () => {
  return {
    key: "quality",
    score: 1,
  };
};

ls.describe("wrapped vitest", () => {
  ls.test(
    "should work",
    {
      inputs: { foo: "bar" },
      referenceOutputs: { foo: "bar" },
    },
    async ({ referenceOutputs }) => {
      const myApp = () => {
        return referenceOutputs;
      };
      const res = myApp();
      await ls.expect(res).evaluatedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
    }
  );
});
