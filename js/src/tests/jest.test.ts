import { test } from "@jest/globals";
import { AsyncLocalStorage } from "node:async_hooks";

import * as ls from "../jest/index.js";
import { type SimpleEvaluator } from "../jest/index.js";

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
      await ls.expect(res).gradedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    }
  );

  ls.test({ inputs: { foo: "bar" }, outputs: { foo: "bar" } }, { n: 3 })(
    "Should work with repetitions",
    async ({ inputs: _inputs, outputs: _outputs }) => {
      const myApp = () => {
        return { bar: "goodval" };
      };
      const res = myApp();
      await ls.expect(res).gradedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    }
  );

  ls.test({ inputs: { foo: "bad" }, outputs: { baz: "qux" } })(
    "Should fail with some defined evaluator",
    async ({ inputs: _inputs, outputs: _outputs }) => {
      const myApp = () => {
        return { bar: "bad" };
      };
      const res = myApp();
      await ls
        .expect(res)
        .gradedBy(myEvaluator)
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
    ],
    { n: 3, metadata: { something: "cool" } }
  )("Does the thing", async ({ inputs: _inputs, outputs: _outputs }) => {
    const myApp = () => {
      return { bar: "bad" };
    };
    const res = myApp();
    await ls.expect(res).gradedBy(myEvaluator).not.toBeGreaterThanOrEqual(0.5);
    return res;
  });

  test("Should test absolute closeness custom matcher", async () => {
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

  test("Should test relative closeness custom matcher", async () => {
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
});
