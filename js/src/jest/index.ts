/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import { expect, test, describe } from "@jest/globals";
import crypto from "crypto";
import { v4 } from "uuid";

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
const fetchExamplesPromises = new Map();
const createExamplePromises = new Map();

async function runDatasetSetup(context: JestAsyncLocalStorageData) {
  const {
    client: testClient,
    suiteName: datasetName,
    projectConfig,
    suiteUuid,
  } = context;
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
    if (fetchExamplesPromises.get(suiteUuid) === undefined) {
      fetchExamplesPromises.set(
        suiteUuid,
        fetchExamples(testClient, datasetName)
      );
    }
    const examples = await fetchExamplesPromises.get(suiteUuid);
    const project = await _createProject(testClient, dataset.id, projectConfig);
    storageValue = {
      dataset,
      examples,
      project,
      client: testClient,
    };
  }
  return storageValue;
}

async function fetchExamples(testClient: Client, datasetName: string) {
  const examplesList = testClient.listExamples({
    datasetName,
  });
  const examples = [];
  for await (const example of examplesList) {
    const inputHash = objectHash(example.inputs);
    const outputHash = objectHash(example.outputs ?? {});
    examples.push({ ...example, inputHash, outputHash });
  }
  return examples;
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
    return method(datasetName, () => {
      const suiteUuid = v4();
      const context = {
        suiteUuid,
        suiteName: datasetName,
        client: experimentConfig?.client ?? RunTree.getSharedClient(),
        createdAt: new Date().toISOString(),
        projectConfig: experimentConfig,
        enableTestTracking: experimentConfig?.enableTestTracking,
      };

      beforeAll(async () => {
        datasetSetupInfo.set(suiteUuid, await runDatasetSetup(context));
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

export type LangSmithJestWrapperConfig = Partial<RunTreeConfig> & {
  n?: number;
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
          const { examples, dataset, createdAt, project, client } =
            datasetSetupInfo.get(context.suiteUuid);
          const testInput: I = inputs;
          const testOutput: O = outputs;
          const inputHash = objectHash(testInput);
          const outputHash = objectHash(testOutput ?? {});
          if (trackingEnabled(context)) {
            const missingFields = [];
            if (examples === undefined) {
              missingFields.push("examples");
            }
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
            const testClient = config?.client ?? client!;
            let example = (examples ?? []).find((example: any) => {
              return (
                example.inputHash === inputHash &&
                example.outputHash === outputHash
              );
            });
            if (example === undefined) {
              // Avoid creating multiple of the same example
              // when running the same test case multiple times
              // Jest runs other tests serially
              const exampleKey = [
                context.suiteUuid,
                inputHash,
                outputHash,
              ].join(":");
              if (createExamplePromises.get(exampleKey) === undefined) {
                createExamplePromises.set(
                  exampleKey,
                  testClient.createExample(testInput, testOutput, {
                    datasetId: dataset?.id,
                    createdAt: new Date(createdAt ?? new Date()),
                  })
                );
              }
              const newExample = await createExamplePromises.get(exampleKey);
              example = { ...newExample, inputHash, outputHash };
            }

            // .enterWith is OK here
            jestAsyncLocalStorageInstance.enterWith({
              ...context,
              currentExample: example,
              client: testClient,
            });
            const traceableOptions = {
              reference_example_id: example.id,
              project_name: project!.name,
              metadata: {
                ...config?.metadata,
                example_version: example.modified_at
                  ? new Date(example.modified_at).toISOString()
                  : new Date(example.created_at).toISOString(),
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
            await testClient.awaitPendingTraceBatches();
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
    table: { inputs: I; outputs: O }[] | "*",
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
      if (table === "*") {
        /*
         * Jest doesn't allow async setup before declaring tests, so we can't
         * fetch dataset examples before running the test.
         * beforeAll() does not run before test declarations.
         * datasetSetupInfo will not be populated until inside a test.
         */
        method(
          `${name} (pulling from LangSmith dataset "${context.suiteName}")`,
          async () => {
            if (fetchExamplesPromises.get(context.suiteUuid) === undefined) {
              fetchExamplesPromises.set(
                context.suiteUuid,
                fetchExamples(context.client, context.suiteName)
              );
            }
            const examples = await fetchExamplesPromises.get(context.suiteUuid);
            const testMethodPromises: Promise<void>[] = [];
            for (let i = 0; i < examples.length; i += 1) {
              const example = examples[i];
              // Context gets overwritten by Jest, so reset it here.
              jestAsyncLocalStorageInstance.enterWith(context);
              // Use wrapTestMethod to get the traceable spans to properly appear.
              // The test method gets executed without being awaited internally,
              // but we want to await it to catch errors properly so we store the
              // promises and await them at the end of the overarching test to
              // properly catch errors.
              wrapTestMethod(async (_, fn, timeout) => {
                const testPromise = Promise.race([
                  fn(),
                  timeout > 0
                    ? new Promise((_, reject) =>
                        setTimeout(
                          () =>
                            reject(
                              new Error(
                                `Test run #${i} over LangSmith dataset timed out.`
                              )
                            ),
                          timeout
                        )
                      )
                    : Promise.resolve(),
                ]);
                testMethodPromises.push(testPromise);
              })<I, O>(
                `${name}, item ${i}`,
                { inputs: example.inputs, outputs: example.outputs, config },
                fn,
                timeout
              );
            }

            await Promise.all(testMethodPromises);
            // TODO: Fix pending test issue caused by traces being sent after the
            // test promises resolve.
          },
          // Handle timeouts individually within the test
          0
        );
      } else {
        for (let i = 0; i < table.length; i += 1) {
          const example = table[i];
          wrapTestMethod(method)<I, O>(
            `${name}, item ${i}`,
            { inputs: example.inputs, outputs: example.outputs, config },
            fn,
            timeout
          );
        }
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