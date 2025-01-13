/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import {
  expect as vitestExpect,
  test as vitestTest,
  describe as vitestDescribe,
  beforeAll as vitestBeforeAll,
  afterAll as vitestAfterAll,
  Assertion,
} from "vitest";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
  type AbsoluteCloseToMatcherOptions,
  type SemanticCloseToMatcherOptions,
  type RelativeCloseToMatcherOptions,
} from "../utils/jestlike/matchers.js";
import type { SimpleEvaluator } from "../utils/jestlike/vendor/evaluatedBy.js";
import { logFeedback, logOutput } from "../utils/jestlike/index.js";
import { generateWrapperFromJestlikeMethods } from "../utils/jestlike/index.js";

vitestExpect.extend({
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
});

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

const { test, it, describe, expect } = generateWrapperFromJestlikeMethods({
  expect: vitestExpect,
  test: vitestTest,
  describe: vitestDescribe,
  beforeAll: vitestBeforeAll,
  afterAll: vitestAfterAll,
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

export * from "../utils/jestlike/types.js";
