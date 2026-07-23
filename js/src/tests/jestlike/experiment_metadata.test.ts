import { jest } from "@jest/globals";

import { Client } from "../../client.js";
import {
  evaluatorLogFeedbackPromises,
  syncExamplePromises,
} from "../../utils/jestlike/globals.js";
import { generateWrapperFromJestlikeMethods } from "../../utils/jestlike/index.js";

const FUTURE_MODIFIED_AT = "2099-01-01T00:00:00.000Z";

test("records the final example version on the experiment", async () => {
  syncExamplePromises.clear();
  evaluatorLogFeedbackPromises.clear();

  let beforeAllHook: (() => Promise<void>) | undefined;
  let afterAllHook: (() => Promise<void>) | undefined;
  let testFunction: (() => Promise<void>) | undefined;

  const describe = Object.assign((_name: string, fn: () => void) => fn(), {
    only: (_name: string, fn: () => void) => fn(),
    skip: jest.fn(),
    concurrent: (_name: string, fn: () => void) => fn(),
  });
  const testMethod = Object.assign(
    (_name: string, fn: () => Promise<void>) => {
      testFunction = fn;
    },
    {
      only: jest.fn(),
      skip: jest.fn(),
      concurrent: jest.fn(),
      each: jest.fn(),
    },
  );

  const resolved = <T>(value: T) =>
    jest.fn<() => Promise<T>>().mockResolvedValue(value);
  const updateProject = jest
    .fn<(_projectId: string, _options: unknown) => Promise<void>>()
    .mockResolvedValue(undefined);
  const client = {
    readDataset: resolved({
      id: "11111111-1111-4111-8111-111111111111",
      name: "test-dataset",
    }),
    createProject: resolved({
      id: "22222222-2222-4222-8222-222222222222",
      name: "test-project",
    }),
    getDatasetUrl: resolved("https://example.com/datasets/1"),
    readExample: resolved({
      id: "33333333-3333-4333-8333-333333333333",
      dataset_id: "11111111-1111-4111-8111-111111111111",
      inputs: { question: "test" },
      outputs: { answer: "test" },
      metadata: {},
      created_at: FUTURE_MODIFIED_AT,
      modified_at: FUTURE_MODIFIED_AT,
    }),
    createRun: resolved(undefined),
    updateRun: resolved(undefined),
    logEvaluationFeedback: resolved(undefined),
    awaitPendingTraceBatches: resolved(undefined),
    updateProject,
    updateDatasetTag: resolved(undefined),
  } as unknown as Client;

  const ls = generateWrapperFromJestlikeMethods(
    {
      expect,
      test: testMethod,
      describe,
      beforeAll: (fn: () => Promise<void>) => {
        beforeAllHook = fn;
      },
      afterAll: (fn: () => Promise<void>) => {
        afterAllHook = fn;
      },
    },
    "jest",
  );

  ls.describe(
    "test-dataset",
    () => {
      ls.test(
        "test-case",
        {
          inputs: { question: "test" },
          referenceOutputs: { answer: "test" },
        },
        () => ({ answer: "test" }),
      );
    },
    { client, enableTestTracking: true },
  );

  await beforeAllHook?.();
  await testFunction?.();
  await afterAllHook?.();

  expect(updateProject).toHaveBeenCalledWith(
    "22222222-2222-4222-8222-222222222222",
    expect.objectContaining({
      metadata: expect.objectContaining({
        dataset_version: FUTURE_MODIFIED_AT,
      }),
    }),
  );

  syncExamplePromises.clear();
  evaluatorLogFeedbackPromises.clear();
});
