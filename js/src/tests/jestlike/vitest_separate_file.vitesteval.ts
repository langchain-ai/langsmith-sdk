/* eslint-disable import/no-extraneous-dependencies */
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../../vitest/index.mjs";

const myEvaluator = () => {
  return { key: "accuracy", score: Math.random() };
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
      { repetitions: 3, metadata: { something: "cool" } }
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

ls.describe(
  "js vitest 3",
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
      { repetitions: 3, metadata: { something: "cool" } }
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
