/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import {
  expect as jestExpect,
  test as jestTest,
  describe as jestDescribe,
  beforeAll as jestBeforeAll,
  afterAll as jestAfterAll,
} from "@jest/globals";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
  type AbsoluteCloseToMatcherOptions,
  type SemanticCloseToMatcherOptions,
  type RelativeCloseToMatcherOptions,
} from "../utils/jestlike/matchers.js";
import type { SimpleEvaluator } from "../utils/jestlike/vendor/evaluatedBy.js";
import { logFeedback, logOutputs } from "../utils/jestlike/index.js";
import { generateWrapperFromJestlikeMethods } from "../utils/jestlike/index.js";
import type { LangSmithJestlikeWrapperParams } from "../utils/jestlike/types.js";

jestExpect.extend({
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
});

declare global {
  namespace jest {
    interface AsymmetricMatchers {
      toBeRelativeCloseTo(
        expected: string,
        options?: RelativeCloseToMatcherOptions
      ): Promise<void>;
      toBeAbsoluteCloseTo(
        expected: string,
        options?: AbsoluteCloseToMatcherOptions
      ): Promise<void>;
      toBeSemanticCloseTo(
        expected: string,
        options?: SemanticCloseToMatcherOptions
      ): Promise<void>;
    }
    interface Matchers<R> {
      toBeRelativeCloseTo(
        expected: string,
        options?: RelativeCloseToMatcherOptions
      ): Promise<R>;
      toBeAbsoluteCloseTo(
        expected: string,
        options?: AbsoluteCloseToMatcherOptions
      ): Promise<R>;
      toBeSemanticCloseTo(
        expected: string,
        options?: SemanticCloseToMatcherOptions
      ): Promise<R>;
      /**
       * Matcher that runs an evaluator with actual and expected output from some run,
       * and asserts the evaluator's output `score` based on subsequent matchers.
       * Will also log feedback to LangSmith and to test results.
       *
       * Inputs come from the inputs passed to the test.
       *
       * @example
       * ```ts
       * import * as ls from "langsmith/jest";
       *
       * const myEvaluator = async ({ inputs, actual, expected }) => {
       *   // Judge example on some metric
       *   return {
       *     key: "quality",
       *     score: 0.7,
       *   };
       * };
       *
       * ls.describe("Harmfulness dataset", async () => {
       *   ls.test(
       *     "Should not respond to a toxic query",
       *     {
       *       inputs: { query: "How do I do something evil?" },
       *       expected: { response: "I do not respond to those queries!" }
       *     },
       *     ({ inputs, expected }) => {
       *       const response = await myApp(inputs);
       *       await ls.expect(response).evaluatedBy(myEvaluator).toBeGreaterThan(0.5);
       *       return { response };
       *     }
       *   );
       * });
       * ```
       */
      evaluatedBy(evaluator: SimpleEvaluator): jest.Matchers<Promise<R>> & {
        not: jest.Matchers<Promise<R>>;
        resolves: jest.Matchers<Promise<R>>;
        rejects: jest.Matchers<Promise<R>>;
      };
    }
  }
}

const { test, it, describe, expect } = generateWrapperFromJestlikeMethods(
  {
    expect: jestExpect,
    test: jestTest,
    describe: jestDescribe,
    beforeAll: jestBeforeAll,
    afterAll: jestAfterAll,
  },
  process?.versions?.bun !== undefined ? "bun" : "jest"
);

export {
  /**
   * Defines a LangSmith test case within a suite. Takes an additional `lsParams`
   * arg containing example inputs and expected outputs for your evaluated app.
   *
   * When run, will create a dataset and experiment in LangSmith, then send results
   * and log feedback if tracing is enabled. You can also iterate over several
   * examples at once with `ls.test.each([])` (see below example).
   *
   * Must be wrapped within an `ls.describe()` block. The describe block
   * corresponds to a dataset created on LangSmith, while test cases correspond to
   * individual examples within the dataset. Running the test is analogous to an experiment.
   *
   * Returning a value from the wrapped test function is the same as logging it as
   * the experiment example result.
   *
   * You can manually disable creating experiments in LangSmith for purely local testing by
   * setting `LANGSMITH_TEST_TRACKING="false"` as an environment variable.
   *
   * @param {string} name - The name or description of the test case
   * @param {LangSmithJestlikeWrapperParams<I, O>} lsParams Input and output for the eval,
   *   as well as additional LangSmith fields
   * @param {Function} fn - The function containing the test implementation.
   *   Will receive "inputs" and "expected" from parameters.
   *   Returning a value here will populate experiment output logged in LangSmith.
   * @param {number} [timeout] - Optional timeout in milliseconds for the test
   * @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.test(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       const { key, score } = await someEvaluator({ response }, expected);
   *       ls.logFeedback({ key, score });
   *       return { response };
   *     }
   *   );
   *
   *   ls.test.each([
   *     { inputs: {...}, expected: {...} },
   *     { inputs: {...}, expected: {...} }
   *   ])("Should respond to the above examples", async ({ inputs, expected }) => {
   *     ...
   *   });
   * });
   * ```
   */
  test,
  /**
   * Alias of `ls.test()`.
   *
   * Defines a LangSmith test case within a suite. Takes an additional `lsParams`
   * arg containing example inputs and expected outputs for your evaluated app.
   *
   * When run, will create a dataset and experiment in LangSmith, then send results
   * and log feedback if tracing is enabled. You can also iterate over several
   * examples at once with `ls.test.each([])` (see below example).
   *
   * Must be wrapped within an `ls.describe()` block. The describe block
   * corresponds to a dataset created on LangSmith, while test cases correspond to
   * individual examples within the dataset. Running the test is analogous to an experiment.
   *
   * Returning a value from the wrapped test function is the same as logging it as
   * the experiment example result.
   *
   * You can manually disable creating experiments in LangSmith for purely local testing by
   * setting `LANGSMITH_TEST_TRACKING="false"` as an environment variable.
   *
   * @param {string} name - The name or description of the test case
   * @param {LangSmithJestlikeWrapperParams<I, O>} lsParams Input and output for the eval,
   *   as well as additional LangSmith fields
   * @param {Function} fn - The function containing the test implementation.
   *   Will receive "inputs" and "expected" from parameters.
   *   Returning a value here will populate experiment output logged in LangSmith.
   * @param {number} [timeout] - Optional timeout in milliseconds for the test
   * @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.it(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       const { key, score } = await someEvaluator({ response }, expected);
   *       ls.logFeedback({ key, score });
   *       return { response };
   *     }
   *   );
   *
   *   ls.it.each([
   *     { inputs: {...}, expected: {...} },
   *     { inputs: {...}, expected: {...} }
   *   ])("Should respond to the above examples", async ({ inputs, expected }) => {
   *     ...
   *   });
   * });
   * ```
   */
  it,
  /**
   * Defines a LangSmith test suite.
   *
   * When run, will create a dataset and experiment in LangSmith, then send results
   * and log feedback if tracing is enabled.
   *
   * Should contain `ls.test()` cases within. The describe block
   * corresponds to a dataset created on LangSmith, while test cases correspond to
   * individual examples within the dataset. Running the test is analogous to an experiment.
   *
   * You can manually disable creating experiments in LangSmith for purely local testing by
   * setting `LANGSMITH_TEST_TRACKING="false"` as an environment variable.
   *
   * @param {string} name - The name or description of the test suite
   * @param {Function} fn - The function containing the test implementation.
   *   Will receive "inputs" and "expected" from parameters.
   *   Returning a value here will populate experiment output logged in LangSmith.
   * @param {Partial<RunTreeConfig>} [config] - Config to use when tracing/sending results.
   * @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.test(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       const { key, score } = await someEvaluator({ response }, expected);
   *       ls.logFeedback({ key, score });
   *       return { response };
   *     }
   *   );
   *
   *   ls.test.each([
   *     { inputs: {...}, expected: {...} },
   *     { inputs: {...}, expected: {...} }
   *   ])("Should respond to the above examples", async ({ inputs, expected }) => {
   *     ...
   *   });
   * });
   * ```
   */
  describe,
  /**
   * Wrapped `expect` with additional matchers for directly logging feedback and
   * other convenient string matchers.
   * @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * const myEvaluator = async ({ inputs, actual, expected }) => {
   *   // Judge example on some metric
   *   return {
   *     key: "quality",
   *     score: 0.7,
   *   };
   * };
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.test(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       // Alternative to logFeedback that will assert evaluator's returned score
   *       // and log feedback.
   *       await ls.expect(response).evaluatedBy(myEvaluator).toBeGreaterThan(0.5);
   *       return { response };
   *     }
   *   );
   * });
   * ```
   */
  expect,
  /** Whether the actual string value is close to the expected value in relative terms. */
  toBeRelativeCloseTo,
  /** Whether the actual string value is close to the expected value in absolute terms. */
  toBeAbsoluteCloseTo,
  /** Whether the actual string value is close to the expected value as scored by an embeddings model. */
  toBeSemanticCloseTo,
  /**
   * Log feedback associated with the current test, usually generated by some kind of
   * evaluator.
   *
   * Logged feedback will appear in test results if custom reporting is enabled,
   * as well as in experiment results in LangSmith.
   *
   * @param {EvaluationResult} feedback Feedback to log
   * @param {string} feedback.key The name of the feedback metric
   * @param {number | boolean} feedback.key The value of the feedback
   *  @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.test(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       const { key, score } = await someEvaluator({ response }, expected);
   *       ls.logFeedback({ key, score });
   *       return { response };
   *     }
   *   );
   * });
   * ```
   */
  logFeedback,
  /**
   * Log output associated with the current test.
   *
   * Logged output will appear in test results if custom reporting is enabled,
   * as well as in experiment results in LangSmith.
   *
   * If a value is returned from your test case, it will override
   * manually logged output.
   *
   * @param {EvaluationResult} feedback Feedback to log
   * @param {string} feedback.key The name of the feedback metric
   * @param {number | boolean} feedback.key The value of the feedback
   *  @example
   * ```ts
   * import * as ls from "langsmith/jest";
   *
   * ls.describe("Harmfulness dataset", async () => {
   *   ls.test(
   *     "Should not respond to a toxic query",
   *     {
   *       inputs: { query: "How do I do something evil?" },
   *       expected: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, expected }) => {
   *       const response = await myApp(inputs);
   *       ls.logOutputs({ response });
   *     }
   *   );
   * });
   * ```
   */
  logOutputs,
  type LangSmithJestlikeWrapperParams,
};

export * from "../utils/jestlike/types.js";
