/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import { expect, test, describe, beforeAll, afterAll } from "@jest/globals";
import crypto from "crypto";
import { v4, v5 } from "uuid";

import { traceable } from "../traceable.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { KVMap, TracerSession } from "../schemas.js";
import { randomName } from "../evaluation/_random_name.js";
import { Client, CreateProjectParams } from "../client.js";
import { LangSmithConflictError } from "../utils/error.js";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
  type AbsoluteCloseToMatcherOptions,
  type SemanticCloseToMatcherOptions,
  type RelativeCloseToMatcherOptions,
} from "./matchers.js";
import {
  JestAsyncLocalStorageData,
  jestAsyncLocalStorageInstance,
  trackingEnabled,
} from "./globals.js";
import { wrapExpect } from "./vendor/chain.js";
import type { SimpleEvaluator } from "./vendor/evaluatedBy.js";

const UUID5_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

expect.extend({
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

const objectHash = (obj: KVMap, depth = 0): string => {
  // Prevent infinite recursion
  if (depth > 50) {
    throw new Error(
      "Object is too deep to check equality for serialization. Please use a simpler example."
    );
  }

  if (Array.isArray(obj)) {
    const arrayHash = obj.map((item) => objectHash(item, depth + 1)).join(",");
    return crypto.createHash("sha256").update(arrayHash).digest("hex");
  }

  if (obj && typeof obj === "object") {
    const sortedHash = Object.keys(obj)
      .sort()
      .map((key) => `${key}:${objectHash(obj[key], depth + 1)}`)
      .join(",");
    return crypto.createHash("sha256").update(sortedHash).digest("hex");
  }

  return crypto.createHash("sha256").update(JSON.stringify(obj)).digest("hex");
};

async function _createProject(
  client: Client,
  datasetId: string,
  projectConfig?: Partial<CreateProjectParams>
) {
  // Create the project, updating the experimentName until we find a unique one.
  let project: TracerSession;
  let experimentName = randomName();
  for (let i = 0; i < 10; i++) {
    try {
      project = await client.createProject({
        projectName: experimentName,
        ...projectConfig,
        referenceDatasetId: datasetId,
      });
      return project;
    } catch (e) {
      // Naming collision
      if ((e as LangSmithConflictError)?.name === "LangSmithConflictError") {
        const ent = v4().slice(0, 6);
        experimentName = `${experimentName}-${ent}`;
      } else {
        throw e;
      }
    }
  }
  throw new Error(
    "Could not generate a unique experiment name within 10 attempts." +
      " Please try again."
  );
}

export type LangSmithJestDescribeWrapper = (
  name: string,
  fn: () => void | Promise<void>,
  config?: Partial<RunTreeConfig>
) => void;

const datasetSetupInfo = new Map();
const syncExamplePromises = new Map();

function getExampleId(
  datasetName: string,
  inputs: Record<string, unknown>,
  outputs?: Record<string, unknown>
) {
  const identifier = JSON.stringify({
    datasetName,
    inputsHash: objectHash(inputs),
    outputsHash: objectHash(outputs ?? {}),
  });
  return v5(identifier, UUID5_NAMESPACE);
}

async function syncExample(params: {
  client: Client;
  exampleId: string;
  datasetId: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdAt: string;
}) {
  const { client, exampleId, inputs, outputs, metadata, createdAt, datasetId } =
    params;
  let example;
  try {
    example = await client.readExample(exampleId);
    if (
      objectHash(example.inputs) !== objectHash(inputs) ||
      objectHash(example.outputs ?? {}) !== objectHash(outputs ?? {}) ||
      example.dataset_id !== datasetId
    ) {
      await client.updateExample(exampleId, {
        inputs,
        outputs,
        metadata,
        dataset_id: datasetId,
      });
    }
  } catch (e: any) {
    if (e.message.includes("not found")) {
      example = await client.createExample(inputs, outputs, {
        exampleId,
        datasetId,
        createdAt: new Date(createdAt ?? new Date()),
        metadata,
      });
    } else {
      throw e;
    }
  }
  return example;
}

async function runDatasetSetup(context: JestAsyncLocalStorageData) {
  const { client: testClient, suiteName: datasetName, projectConfig } = context;
  let storageValue;
  if (!trackingEnabled(context)) {
    storageValue = {
      createdAt: new Date().toISOString(),
    };
  } else {
    let dataset;
    try {
      dataset = await testClient.readDataset({
        datasetName,
      });
    } catch (e: any) {
      if (e.message.includes("not found")) {
        dataset = await testClient.createDataset(datasetName, {
          description: `Dataset for unit tests created on ${new Date().toISOString()}`,
        });
      } else {
        throw e;
      }
    }
    const project = await _createProject(testClient, dataset.id, projectConfig);
    storageValue = {
      dataset,
      project,
      client: testClient,
    };
  }
  return storageValue;
}

function wrapDescribeMethod(
  method: (name: string, fn: () => void | Promise<void>) => void
): LangSmithJestDescribeWrapper {
  return function (
    datasetName: string,
    fn: () => void | Promise<void>,
    experimentConfig?: {
      client?: Client;
      enableTestTracking?: boolean;
    } & Partial<Omit<CreateProjectParams, "referenceDatasetId">>
  ) {
    const client = experimentConfig?.client ?? RunTree.getSharedClient();
    return method(datasetName, () => {
      const suiteUuid = v4();
      const context = {
        suiteUuid,
        suiteName: datasetName,
        client,
        createdAt: new Date().toISOString(),
        projectConfig: experimentConfig,
        enableTestTracking: experimentConfig?.enableTestTracking,
      };

      beforeAll(async () => {
        datasetSetupInfo.set(suiteUuid, await runDatasetSetup(context));
      });

      afterAll(async () => {
        await Promise.all([...syncExamplePromises.values()]);
        await client.awaitPendingTraceBatches();
      });

      /**
       * We cannot rely on setting AsyncLocalStorage in beforeAll or beforeEach,
       * due to https://github.com/jestjs/jest/issues/13653 and needing to use
       * the janky .enterWith.
       *
       * We also cannot do async setup in describe due to Jest restrictions.
       * However, .run without asynchronous logic works.
       *
       * We really just need a way to pass suiteUuid as global state to inner tests
       * that can handle concurrently running test suites. If we drop the
       * concurrency requirement, we can remoce this hack.
       */
      void jestAsyncLocalStorageInstance.run(context, fn);
    });
  };
}

const lsDescribe = Object.assign(wrapDescribeMethod(describe), {
  only: wrapDescribeMethod(describe.only),
  skip: wrapDescribeMethod(describe.skip),
});

export type LangSmithJestWrapperConfig = Partial<
  Omit<RunTreeConfig, "client">
> & {
  n?: number;
  iterations?: number;
};

export type LangSmithJestWrapperParams<I, O> = {
  inputs: I;
  outputs: O;
  config?: LangSmithJestWrapperConfig;
};

export type LangSmithJestTestWrapper<I, O> = (
  name: string,
  fn: (params: { inputs: I; outputs: O }) => unknown | Promise<unknown>,
  params: LangSmithJestWrapperParams<I, O>,
  timeout?: number
) => void;

function wrapTestMethod(method: (...args: any[]) => void) {
  return function <
    I extends Record<string, any> = Record<string, any>,
    O extends Record<string, any> = Record<string, any>
  >(
    name: string,
    lsParams: LangSmithJestWrapperParams<I, O>,
    testFn: (data: { inputs: I; outputs: O }) => unknown | Promise<unknown>,
    timeout?: number
  ) {
    // Due to https://github.com/jestjs/jest/issues/13653,
    // we must access the local store value here before
    // doing anything async.
    const context = jestAsyncLocalStorageInstance.getStore();
    const { config, inputs, outputs } = lsParams;
    const totalRuns = config?.n ?? 1;
    for (let i = 0; i < totalRuns; i += 1) {
      // Jest will not group tests under the same "describe" group if you await the test and
      // total runs is greater than 1.
      void method(
        `${name}, iteration ${i}`,
        async () => {
          if (context === undefined) {
            throw new Error(
              `Could not retrieve test context.\nPlease make sure you have tracing enabled and you are wrapping all of your test cases in an "ls.describe()" function.`
            );
          }
          if (!datasetSetupInfo.get(context.suiteUuid)) {
            throw new Error(
              "Dataset failed to initialize. Please check your LangSmith environment variables."
            );
          }
          const { dataset, createdAt, project, client } = datasetSetupInfo.get(
            context.suiteUuid
          );
          const testInput: I = inputs;
          const testOutput: O = outputs;
          if (trackingEnabled(context)) {
            const missingFields = [];
            if (dataset === undefined) {
              missingFields.push("dataset");
            }
            if (project === undefined) {
              missingFields.push("project");
            }
            if (client === undefined) {
              missingFields.push("client");
            }
            if (missingFields.length > 0) {
              throw new Error(
                `Failed to initialize test tracking: Could not identify ${missingFields
                  .map((field) => `"${field}"`)
                  .join(
                    ", "
                  )} while syncing to LangSmith. Please contact us for help.`
              );
            }
            const testClient = client;
            const exampleId = getExampleId(dataset.name, inputs, outputs);

            // Create or update the example in the background
            if (syncExamplePromises.get(exampleId) === undefined) {
              syncExamplePromises.set(
                exampleId,
                syncExample({
                  client,
                  exampleId,
                  datasetId: dataset.id,
                  inputs,
                  outputs,
                  metadata: {},
                  createdAt,
                })
              );
            }

            // .enterWith is OK here
            jestAsyncLocalStorageInstance.enterWith({
              ...context,
              currentExample: {
                inputs,
                outputs,
                id: exampleId,
                syncPromise: syncExamplePromises.get(exampleId),
              },
              client: testClient,
            });

            const traceableOptions = {
              reference_example_id: exampleId,
              project_name: project!.name,
              metadata: {
                ...config?.metadata,
              },
              client: testClient,
              tracingEnabled: true,
              name: "Unit test",
            };

            // Pass inputs into traceable so tracing works correctly but
            // provide both to the user-defined test function
            const tracedFunction = traceable(
              async (_: I) => {
                return testFn({
                  inputs: testInput,
                  outputs: testOutput,
                });
              },
              { ...traceableOptions, ...config }
            );
            await (tracedFunction as any)(testInput);
          } else {
            // .enterWith is OK here
            jestAsyncLocalStorageInstance.enterWith({
              ...context,
              currentExample: { inputs: testInput, outputs: testOutput },
            });
            await testFn({
              inputs: testInput,
              outputs: testOutput,
            });
          }
        },
        timeout
      );
    }
  };
}

function createEachMethod(method: (...args: any[]) => void) {
  function eachMethod<I extends KVMap, O extends KVMap>(
    table: { inputs: I; outputs: O }[],
    config?: LangSmithJestWrapperConfig
  ) {
    const context = jestAsyncLocalStorageInstance.getStore();
    if (context === undefined) {
      throw new Error(
        "Could not retrieve test context. Make sure your test is nested within a ls.describe() block."
      );
    }
    return function (
      name: string,
      fn: (params: { inputs: I; outputs: O }) => unknown | Promise<unknown>,
      timeout?: number
    ) {
      for (let i = 0; i < table.length; i += 1) {
        const example = table[i];
        wrapTestMethod(method)<I, O>(
          `${name}, item ${i}`,
          { inputs: example.inputs, outputs: example.outputs, config },
          fn,
          timeout
        );
      }
    };
  }
  return eachMethod;
}

const lsTest = Object.assign(wrapTestMethod(test), {
  only: Object.assign(wrapTestMethod(test.only), {
    each: createEachMethod(test.only),
  }),
  skip: Object.assign(wrapTestMethod(test.skip), {
    each: createEachMethod(test.skip),
  }),
  each: createEachMethod(test),
});

const wrappedExpect = wrapExpect(expect);

export {
  lsTest as test,
  lsTest as it,
  lsDescribe as describe,
  wrappedExpect as expect,
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
};

export { type SimpleEvaluator };
