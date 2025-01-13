import { test } from "@jest/globals";
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../../jest/index.js";
import { type SimpleEvaluator } from "../../jest/index.js";

const myEvaluator: SimpleEvaluator = (params) => {
  const { expected, actual } = params;
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

ls.describe(
  "js unit testing test demo",
  () => {
    ls.test(
      "Should succeed with some defined evaluator",
      { inputs: { foo: "bar" }, expected: { bar: "qux" } },
      async ({ inputs: _inputs, expected }) => {
        const myApp = () => {
          return expected;
        };
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .toBeGreaterThanOrEqual(0.5);
        ls.logFeedback({
          key: "coolness",
          score: 0.9,
        });
        ls.logOutput({
          bar: "perfect",
        });
      }
    );

    ls.test(
      "Should work with repetitions",
      {
        inputs: { foo: "bar" },
        expected: { foo: "bar" },
        config: { iterations: 3 },
      },
      async ({ inputs: _inputs, expected: _expected }) => {
        const myApp = () => {
          return { bar: "goodval" };
        };
        const res = myApp();
        ls.logFeedback({
          key: "coolness",
          score: 0.8,
        });
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .toBeGreaterThanOrEqual(0.5);
        return res;
      }
    );

    ls.test(
      "Should fail with some defined evaluator",
      { inputs: { foo: "bad" }, expected: { baz: "qux" } },
      async ({ inputs: _inputs, expected: _expected }) => {
        const myApp = () => {
          return { bar: "bad" };
        };
        const res = myApp();
        ls.logFeedback({
          key: "coolness",
          score: 0,
        });
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .not.toBeGreaterThanOrEqual(0.5);
        return res;
      }
    );

    ls.test.each(
      [
        {
          inputs: {
            one: "uno",
          },
          expected: {
            ein: "un",
          },
        },
        {
          inputs: {
            two: "dos",
          },
          expected: {
            zwei: "deux",
          },
        },
      ],
      { iterations: 3, metadata: { something: "cool" } }
    )("Does the thing", async ({ inputs: _inputs, expected: _outputs }) => {
      const myApp = () => {
        return { bar: "bad" };
      };
      ls.logFeedback({
        key: "coolness",
        score: 0.2,
      });
      const res = myApp();
      await ls
        .expect(res)
        .evaluatedBy(myEvaluator)
        .not.toBeGreaterThanOrEqual(0.5);
      return res;
    });

    test("Absolute closeness custom matcher", async () => {
      await ls.expect("foobar").toBeAbsoluteCloseTo("foobaz", {
        threshold: 3,
      });
      await ls.expect("foobar").not.toBeAbsoluteCloseTo("foobaz", {
        threshold: 0,
      });
      await ls.expect("foobar").not.toBeAbsoluteCloseTo("barfoo", {
        threshold: 3,
      });
    });

    test("Relative closeness custom matcher", async () => {
      await ls.expect("0123456789").toBeRelativeCloseTo("1123456789", {
        threshold: 0.1,
      });
      await ls.expect("0123456789").not.toBeRelativeCloseTo("111111111", {
        threshold: 0.1,
      });
      await ls.expect("0123456789").not.toBeRelativeCloseTo("1", {
        threshold: 0,
      });
      await ls.expect("0123456789").toBeRelativeCloseTo("1", {
        threshold: 1,
      });
    });
  },
  {
    metadata: {
      model: "test-model",
    },
  }
);
