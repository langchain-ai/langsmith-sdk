import { test } from "@jest/globals";
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../../jest/index.js";
import { type SimpleEvaluator } from "../../jest/index.js";
import { _objectHash } from "../../utils/jestlike/index.js";
import { traceable } from "../../traceable.js";

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
  "js unit testing test demo",
  () => {
    ls.test(
      "Should succeed with a defined evaluator",
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
          key: "readability",
          score: 0.9,
        });
        ls.logFeedback({
          key: "readability 2",
          score: 0.9,
        });
        ls.logFeedback({
          key: "readability 3",
          score: 0.9,
        });
        ls.logFeedback({
          key: "readability 4",
          score: 0.9,
        });
        ls.logFeedback({
          key: "readability 5",
          score: 0.9,
        });
        ls.logOutputs({
          bar: "perfect",
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
        ls.logFeedback({
          key: "readability",
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
      "Logging feedback should work in nested traceable",
      {
        inputs: { nested: "nested" },
        referenceOutputs: { nested: "nested" },
      },
      async ({ inputs: _inputs, referenceOutputs: _referenceOutputs }) => {
        const myApp = () => {
          return { bar: "goodval" };
        };
        const res = myApp();
        const nested = traceable(() => {
          ls.logFeedback({
            key: "nested",
            score: 0.8,
          });
        });
        await nested();
        return res;
      }
    );

    ls.test(
      "Should fail with some defined evaluator",
      { inputs: { foo: "bad" }, referenceOutputs: { baz: "qux" } },
      async ({ inputs: _inputs, referenceOutputs: _referenceOutputs }) => {
        const myApp = () => {
          return { bar: "bad" };
        };
        const res = myApp();
        ls.logFeedback({
          key: "readability",
          score: 0.1,
        });
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
          split: "test-split",
          metadata: {
            foo: "bar",
          },
        },
      ],
      { repetitions: 3, metadata: { something: "cool" } }
    )(
      "Counts to ten",
      async ({ inputs: _inputs, referenceOutputs: _referenceOutputs }) => {
        const myApp = () => {
          return { bar: "bad" };
        };
        ls.logFeedback({
          key: "readability",
          score: 0.6,
        });
        const res = myApp();
        await ls
          .expect(res)
          .evaluatedBy(myEvaluator)
          .not.toBeGreaterThanOrEqual(0.5);
        ls.logOutputs(res);
      }
    );

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

const scoreMarketingCopyAgent = async () => {
  return {
    key: "marketing_copy_score",
    score: 0.5,
  };
};

ls.describe("Test Tweet", () => {
  ls.test(
    "should generate a tweet LS",
    {
      inputs: {
        request: "Write a tweet about LLMs",
      },
      referenceOutputs: {},
    },
    async ({ inputs: { request } }: { inputs: { request: string } }) => {
      const result = request.repeat(2);
      ls.logOutputs({ response: result });
      ls.logFeedback({
        key: "length",
        score: result.length,
      });
      ls.logFeedback({
        key: "twitter_length",
        score: result.length <= 280,
      });
      const wrappedEvaluator = ls.wrapEvaluator(scoreMarketingCopyAgent);
      await wrappedEvaluator({
        content: result,
        query_type: "tweet",
      });
    }
  );
});

ls.describe("Test Linkedin Post", () => {
  ls.test(
    "should generate a linkedin post LS",
    {
      inputs: {
        request: "Write a linkedin post about LLMs",
      },
      referenceOutputs: {},
    },
    async ({ inputs: { request } }: { inputs: { request: string } }) => {
      const result = request.repeat(2);
      ls.logOutputs({ response: result });
      ls.logFeedback({
        key: "length",
        score: result.length,
      });
      ls.logFeedback({
        key: "linkedin_length",
        score: result.length > 280,
      });
      ls.logFeedback({
        key: "multiline",
        score: result.split("\n").length > 2,
      });
      const wrappedEvaluator = ls.wrapEvaluator(scoreMarketingCopyAgent);
      await wrappedEvaluator({
        content: result,
        query_type: "linkedin post",
      });
    }
  );
});

test("object hash should work on undefined values", async () => {
  expect(
    _objectHash({
      foo: "bar",
      baz: undefined,
      qux: null,
    })
  ).toEqual("88d67a35803b03a787d9fce25ebed027807c68ce0c3dee9f818fc58a43dd10af");
});
