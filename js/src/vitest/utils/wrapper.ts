import type { Assertion } from "vitest";
import {
  type AbsoluteCloseToMatcherOptions,
  type SemanticCloseToMatcherOptions,
  type RelativeCloseToMatcherOptions,
} from "../../utils/jestlike/matchers.js";
import type { SimpleEvaluator } from "../../utils/jestlike/vendor/evaluatedBy.js";
import { generateWrapperFromJestlikeMethods } from "../../utils/jestlike/index.js";
import { logFeedback, logOutputs } from "../../utils/jestlike/index.js";
import { wrapEvaluator } from "../../utils/jestlike/vendor/evaluatedBy.js";

interface CustomMatchers<R = unknown> {
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
   * Matcher that runs an evaluator with actual outputs and reference outputs from some run,
   * and asserts the evaluator's output `score` based on subsequent matchers.
   * Will also log feedback to LangSmith and to test results.
   *
   * Inputs come from the inputs passed to the test.
   *
   * @example
   * ```ts
   * import * as ls from "langsmith/vitest";
   *
   * const myEvaluator = async ({ inputs, actual, referenceOutputs }) => {
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
   *       referenceOutputs: { response: "I do not respond to those queries!" }
   *     },
   *     ({ inputs, referenceOutputs }) => {
   *       const response = await myApp(inputs);
   *       await ls.expect(response).evaluatedBy(myEvaluator).toBeGreaterThan(0.5);
   *       return { response };
   *     }
   *   );
   * });
   * ```
   */
  evaluatedBy(evaluator: SimpleEvaluator): Assertion<Promise<R>> & {
    not: Assertion<Promise<R>>;
    resolves: Assertion<Promise<R>>;
    rejects: Assertion<Promise<R>>;
  };
}

declare module "vitest" {
  interface Assertion<T = any> extends CustomMatchers<T> {}
  interface AsymmetricMatchersContaining extends CustomMatchers {}
}

/**
 * Dynamically wrap original Vitest imports.
 *
 * This may be necessary to ensure you are wrapping the correct
 * Vitest version if you are using a monorepo whose workspaces
 * use multiple versions of Vitest.
 *
 * @param originalVitestMethods - The original Vitest imports to wrap.
 * @returns The wrapped Vitest imports.
 * See https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest
 * for more details.
 */
export const wrapVitest = (originalVitestMethods: Record<string, unknown>) => {
  if (
    typeof originalVitestMethods !== "object" ||
    originalVitestMethods == null
  ) {
    throw new Error("originalVitestMethods must be an non-null object.");
  }
  if (
    !("expect" in originalVitestMethods) ||
    typeof originalVitestMethods.expect !== "function"
  ) {
    throw new Error("Your passed object must contain a `expect` method.");
  }
  if (
    !("it" in originalVitestMethods) ||
    typeof originalVitestMethods.it !== "function"
  ) {
    throw new Error("Your passed object must contain a `it` method.");
  }
  if (
    !("test" in originalVitestMethods) ||
    typeof originalVitestMethods.test !== "function"
  ) {
    throw new Error("Your passed object must contain a `test` method.");
  }
  if (
    !("describe" in originalVitestMethods) ||
    typeof originalVitestMethods.describe !== "function"
  ) {
    throw new Error("Your passed object must contain a `describe` method.");
  }
  if (
    !("beforeAll" in originalVitestMethods) ||
    typeof originalVitestMethods.beforeAll !== "function"
  ) {
    throw new Error("Your passed object must contain a `beforeAll` method.");
  }
  if (
    !("afterAll" in originalVitestMethods) ||
    typeof originalVitestMethods.afterAll !== "function"
  ) {
    throw new Error("Your passed object must contain a `afterAll` method.");
  }

  const wrappedMethods = generateWrapperFromJestlikeMethods(
    {
      expect: originalVitestMethods.expect,
      it: originalVitestMethods.it,
      test: originalVitestMethods.test,
      describe: originalVitestMethods.describe,
      beforeAll: originalVitestMethods.beforeAll,
      afterAll: originalVitestMethods.afterAll,
    },
    "vitest"
  );

  return {
    ...wrappedMethods,
    logFeedback,
    logOutputs,
    wrapEvaluator,
  };
};
