import { jest } from "@jest/globals";

import { Client } from "../../client.js";
import { evaluatorLogFeedbackPromises } from "../../utils/jestlike/globals.js";
import { generateWrapperFromJestlikeMethods } from "../../utils/jestlike/index.js";

const FIRST_MODIFIED_AT = "2099-01-01T00:00:00.000Z";
const SECOND_MODIFIED_AT = "2099-02-01T00:00:00.000Z";

test("scopes the final example version to each experiment", async () => {
  evaluatorLogFeedbackPromises.clear();

  const beforeAllHooks: Array<() => Promise<void>> = [];
  const afterAllHooks: Array<() => Promise<void>> = [];
  const testFunctions: Array<() => Promise<void>> = [];

  const describe = Object.assign((_name: string, fn: () => void) => fn(), {
    only: (_name: string, fn: () => void) => fn(),
    skip: jest.fn(),
    concurrent: (_name: string, fn: () => void) => fn(),
  });
  const testMethod = Object.assign(
    (_name: string, fn: () => Promise<void>) => {
      testFunctions.push(fn);
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
      name: "shared-dataset",
    }),
    createProject: jest
      .fn<() => Promise<{ id: string; name: string }>>()
      .mockResolvedValueOnce({
        id: "22222222-2222-4222-8222-222222222222",
        name: "first-project",
      })
      .mockResolvedValueOnce({
        id: "44444444-4444-4444-8444-444444444444",
        name: "second-project",
      }),
    getDatasetUrl: resolved("https://example.com/datasets/1"),
    readExample: jest
      .fn<() => Promise<Record<string, unknown>>>()
      .mockResolvedValueOnce({
        id: "33333333-3333-4333-8333-333333333333",
        dataset_id: "11111111-1111-4111-8111-111111111111",
        inputs: { question: "first" },
        outputs: { answer: "first" },
        metadata: {},
        created_at: FIRST_MODIFIED_AT,
        modified_at: FIRST_MODIFIED_AT,
      })
      .mockResolvedValueOnce({
        id: "55555555-5555-4555-8555-555555555555",
        dataset_id: "11111111-1111-4111-8111-111111111111",
        inputs: { question: "second" },
        outputs: { answer: "second" },
        metadata: {},
        created_at: SECOND_MODIFIED_AT,
        modified_at: SECOND_MODIFIED_AT,
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
      beforeAll: (fn: () => Promise<void>) => beforeAllHooks.push(fn),
      afterAll: (fn: () => Promise<void>) => afterAllHooks.push(fn),
    },
    "jest",
  );

  const registerSuite = (question: string) => {
    ls.describe(
      "shared-dataset",
      () => {
        ls.test(
          `${question}-test`,
          {
            inputs: { question },
            referenceOutputs: { answer: question },
          },
          () => ({ answer: question }),
        );
      },
      { client, enableTestTracking: true },
    );
  };

  registerSuite("first");
  registerSuite("second");

  for (const hook of beforeAllHooks) await hook();
  for (const fn of testFunctions) await fn();
  for (const hook of afterAllHooks) await hook();

  expect(updateProject).toHaveBeenCalledWith(
    "22222222-2222-4222-8222-222222222222",
    expect.objectContaining({
      metadata: expect.objectContaining({
        dataset_version: FIRST_MODIFIED_AT,
      }),
    }),
  );
  expect(updateProject).toHaveBeenCalledWith(
    "44444444-4444-4444-8444-444444444444",
    expect.objectContaining({
      metadata: expect.objectContaining({
        dataset_version: SECOND_MODIFIED_AT,
      }),
    }),
  );

  evaluatorLogFeedbackPromises.clear();
});
