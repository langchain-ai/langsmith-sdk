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

  ls.test.skip(
    "should report output on thrown errors/assertion failures",
    {
      inputs: { foo: "qux" },
      referenceOutputs: { foo: "qux" },
    },
    async ({ referenceOutputs }) => {
      const myApp = () => {
        return referenceOutputs;
      };
      const res = myApp();
      ls.logOutputs({ res });
      // Will fail, can't run in CI because Vitest doesn't have xfail
      await ls.expect(res).evaluatedBy(myEvaluator).toBeLessThanOrEqual(0.5);
    }
  );
});
