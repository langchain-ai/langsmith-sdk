/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import { expect, test, describe } from "@jest/globals";
import crypto from "crypto";
import { v4 } from "uuid";

import { traceable } from "../traceable.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { Example, KVMap, TracerSession } from "../schemas.js";
import { randomName } from "../evaluation/_random_name.js";
import { Client } from "../client.js";
import { LangSmithConflictError } from "../utils/error.js";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
} from "./matchers.js";
import { jestAsyncLocalStorageInstance, trackingEnabled } from "./globals.js";
import { wrapExpect } from "./vendor/chain.js";
import type { SimpleEvaluator } from "./vendor/gradedBy.js";

declare global {
  namespace jest {
    interface AsymmetricMatchers {
      toBeRelativeCloseTo(expected: string, options?: any): void;
      toBeAbsoluteCloseTo(expected: string, options?: any): void;
      toBeSemanticCloseTo(expected: string, options?: any): Promise<void>;
    }
    interface Matchers<R> {
      toBeRelativeCloseTo(expected: string, options?: any): R;
      toBeAbsoluteCloseTo(expected: string, options?: any): R;
      toBeSemanticCloseTo(expected: string, options?: any): Promise<R>;
      gradedBy(evaluator: SimpleEvaluator): jest.Matchers<Promise<R>> & {
        not: jest.Matchers<Promise<R>>;
        resolves: jest.Matchers<Promise<R>>;
        rejects: jest.Matchers<Promise<R>>;
      };
    }
  }
}

expect.extend({
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
});

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

async function _createProject(client: Client, datasetId: string) {
  // Create the project, updating the experimentName until we find a unique one.
  let project: TracerSession;
  let experimentName = randomName();
  for (let i = 0; i < 10; i++) {
    try {
      project = await client.createProject({
        projectName: experimentName,
        referenceDatasetId: datasetId,
        // description: this._description,
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

const setupPromises = new Map();

async function runDatasetSetup(testClient: Client, datasetName: string) {
  let storageValue;
  if (!trackingEnabled()) {
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
    const examplesList = testClient.listExamples({
      datasetName,
    });
    const examples = [];
    for await (const example of examplesList) {
      const inputHash = objectHash(example.inputs);
      const outputHash = objectHash(example.outputs ?? {});
      examples.push({ ...example, inputHash, outputHash });
    }
    const project = await _createProject(testClient, dataset.id);
    storageValue = {
      dataset,
      examples,
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
    config?: Partial<RunTreeConfig>
  ) {
    return method(datasetName, () => {
      const suiteUuid = v4();
      /**
       * We cannot rely on setting AsyncLocalStorage in beforeAll or beforeEach,
       * due to https://github.com/jestjs/jest/issues/13653 and needing to use
       * the janky .enterWith.
       *
       * We also cannot do async setup in describe due to Jest restrictions.
       * However, .run without asynchronous logic works.
       */
      void jestAsyncLocalStorageInstance.run(
        {
          suiteUuid,
          suiteName: datasetName,
          client: config?.client ?? RunTree.getSharedClient(),
          createdAt: new Date().toISOString(),
        },
        fn
      );
    });
  };
}

const lsDescribe = Object.assign(wrapDescribeMethod(describe), {
  only: wrapDescribeMethod(describe.only),
  skip: wrapDescribeMethod(describe.skip),
});

export type LangSmithJestTestWrapper<I, O> = (
  name: string,
  fn: (params: { inputs: I; outputs: O }) => unknown | Promise<unknown>,
  timeout?: number
) => void;

function wrapTestMethod(method: (...args: any[]) => void | Promise<void>) {
  return function <
    I extends Record<string, any> = Record<string, any>,
    O extends Record<string, any> = Record<string, any>
  >(
    params: { inputs: I; outputs: O },
    config?: Partial<RunTreeConfig> & { n?: number }
  ): LangSmithJestTestWrapper<I, O> {
    // Due to https://github.com/jestjs/jest/issues/13653,
    // we must access the local store value here before
    // entering an async context
    const context = jestAsyncLocalStorageInstance.getStore();
    // This typing is wrong, but necessary to avoid lint errors
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return async function (...args: any[]) {
      let createExamplePromise: Promise<Example> | undefined;
      const totalRuns = config?.n ?? 1;
      for (let i = 0; i < totalRuns; i += 1) {
        // Jest will not group under the same "describe" group if you await the test and
        // total runs is greater than 1
        void method(
          `${args[0]} ${i}`,
          async () => {
            if (context === undefined) {
              throw new Error(
                `Could not retrieve test context.\nPlease make sure you have tracing enabled and you are wrapping all of your test cases in an "ls.describe()" function.`
              );
            }
            // Because of https://github.com/jestjs/jest/issues/13653, we have to do asynchronous setup
            // within the test itself
            if (!setupPromises.get(context.suiteUuid)) {
              setupPromises.set(
                context.suiteUuid,
                runDatasetSetup(context.client, context.suiteName)
              );
            }
            const { examples, dataset, createdAt, project, client } =
              await setupPromises.get(context.suiteUuid);
            const testInput: I = params.inputs;
            const testOutput: O = params.outputs;
            const inputHash = objectHash(testInput);
            const outputHash = objectHash(testOutput ?? {});
            if (trackingEnabled()) {
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
                if (createExamplePromise === undefined) {
                  createExamplePromise = testClient.createExample(
                    testInput,
                    testOutput,
                    {
                      datasetId: dataset?.id,
                      createdAt: new Date(createdAt ?? new Date()),
                    }
                  );
                }
                const newExample = await createExamplePromise;
                example = { ...newExample, inputHash, outputHash };
              }

              // What do I do here?
              // examples.push(example);

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
                  return args[1]({
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
              await args[1]({
                inputs: testInput,
                outputs: testOutput,
              });
            }
          },
          ...args.slice(2)
        );
      }
    };
  };
}

function eachMethod<I extends KVMap, O extends KVMap>(
  table: { inputs: I; outputs: O }[]
) {
  return function (
    name: string,
    fn: (params: { inputs: I; outputs: O }) => unknown | Promise<unknown>,
    timeout?: number
  ) {
    for (let i = 0; i < table.length; i += 1) {
      const example = table[i];
      wrapTestMethod(test)<I, O>(example)(`${name} ${i}`, fn, timeout);
    }
  };
}

const lsTest = Object.assign(wrapTestMethod(test), {
  only: wrapTestMethod(test.only),
  skip: wrapTestMethod(test.skip),
  each: eachMethod,
});

const wrappedExpect = wrapExpect(expect);

export {
  lsTest as test,
  lsTest as it,
  lsDescribe as describe,
  wrappedExpect as expect,
};

export { type SimpleEvaluator };
