/* eslint-disable import/no-extraneous-dependencies */
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../../vitest/index.js";
import { type SimpleEvaluator } from "../../vitest/index.js";

const myEvaluator: SimpleEvaluator = (params) => {
  const { referenceOutputs, outputs } = params;
  if (outputs.bar === referenceOutputs.bar) {
    return {
      key: "accuracy",
      score: 1,
    };
  } else if (outputs.bar === "goodval") {
    return {
      key: "accuracy",
      score: 0.5,
    };
  } else {
    return {
      key: "accuracy",
      score: 0,
    };
  }
};

const unrelatedStore = new AsyncLocalStorage();
unrelatedStore.enterWith("value"); // Ensure that this works despite https://github.com/jestjs/jest/issues/13653

ls.describe(
  "js vitest 2",
  () => {
    ls.test.each(
      [
        {
          inputs: {
            one: "uno",
          },
          referenceOutputs: {
            ein: "un",
          },
        },
        {
          inputs: {
            two: "dos",
          },
          referenceOutputs: {
            zwei: "deux",
          },
        },
      ],
      { iterations: 3, metadata: { something: "cool" } }
    )("Does the thing", async ({ inputs, referenceOutputs }) => {
      const myApp = () => {
        return { bar: "bad" };
      };
      const res = myApp();
      const evaluator = ls.wrapEvaluator(myEvaluator);
      await evaluator({ inputs, referenceOutputs, outputs: res });
      return res;
    });
  },
  {
    metadata: {
      model: "test-model",
    },
  }
);
