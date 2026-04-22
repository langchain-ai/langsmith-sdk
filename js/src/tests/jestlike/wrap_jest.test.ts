import * as jest from "@jest/globals";
import { SimpleEvaluator, wrapJest } from "../../jest/index.js";

const ls = wrapJest(jest);

const myEvaluator: SimpleEvaluator = () => {
  return {
    key: "quality",
    score: 1,
  };
};

ls.describe("wrapped jest", () => {
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
