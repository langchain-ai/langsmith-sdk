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
} from "./utils/jestlike/matchers.js";
import type { SimpleEvaluator } from "./utils/jestlike/vendor/evaluatedBy.js";
import { logFeedback, logOutput } from "./utils/jestlike/index.js";
import { generateWrapperFromJestlikeMethods } from "./utils/jestlike/index.js";

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
      evaluatedBy(evaluator: SimpleEvaluator): jest.Matchers<Promise<R>> & {
        not: jest.Matchers<Promise<R>>;
        resolves: jest.Matchers<Promise<R>>;
        rejects: jest.Matchers<Promise<R>>;
      };
    }
  }
}

const { test, it, describe, expect } = generateWrapperFromJestlikeMethods({
  expect: jestExpect,
  test: jestTest,
  describe: jestDescribe,
  beforeAll: jestBeforeAll,
  afterAll: jestAfterAll,
});

export {
  test,
  it,
  describe,
  expect,
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
  logFeedback,
  logOutput,
};

export * from "./utils/jestlike/types.js";
