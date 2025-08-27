/* eslint-disable import/no-extraneous-dependencies */
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../../vitest/index.mjs";
import { type SimpleEvaluator } from "../../vitest/index.mjs";

const myEvaluator: SimpleEvaluator = (params) => {
  const { referenceOutputs, outputs } = params;
  if (outputs.bar === referenceOutputs.bar) {
    return {
      key: "quality",
      score: 1,
    };
  } else if (outputs.bar === "goodval") {
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

ls.describe(
  "js vitest",
  () => {
    ls.test(
      "Should succeed with some defined evaluator",
      { inputs: { foo: "bar" }, referenceOutputs: { bar: "qux" } },
      async ({ inputs: _inputs, referenceOutputs }) => {
        const myApp = () => {
          return referenceOutputs;
        };
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .toBeGreaterThanOrEqual(0.5);
        ls.logFeedback({
          key: "coolness",
          score: 0.5,
        });
        ls.logOutputs({
          testLoggedOutput: "logged",
        });
      }
    );

    ls.test(
      "Should work with repetitions",
      {
        inputs: { foo: "bar" },
        referenceOutputs: { foo: "bar" },
        config: { repetitions: 3 },
      },
      async ({ inputs: _inputs, referenceOutputs: _referenceOutputs }) => {
        const myApp = () => {
          return { bar: "goodval" };
        };
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .toBeGreaterThanOrEqual(0.5);
        return res;
      }
    );

    ls.test(
      "Should fail with some defined evaluator",
      { inputs: { foo: "bad" }, referenceOutputs: { baz: "qux" } },
      async ({ inputs: _inputs, referenceOutputs: _expected }) => {
        const myApp = () => {
          return { bar: "bad" };
        };
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .not.toBeGreaterThanOrEqual(0.5);
        return res;
      }
    );

    ls.test.concurrent.each(
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
    )(
      "Does the thing",
      async ({ inputs: _inputs, referenceOutputs: _outputs }) => {
        const myApp = () => {
          return { bar: "bad" };
        };
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .not.toBeGreaterThanOrEqual(0.5);
        return res;
      }
    );
  },
  {
    metadata: {
      model: "test-model",
    },
    testSuiteName: "js-vitest-testing",
  }
);
