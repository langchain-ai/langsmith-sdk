import { expect, test, describe, beforeAll } from "@jest/globals";
import crypto from "crypto";
import { v4 } from "uuid";

import { traceable } from "../traceable.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { TracerSession } from "../schemas.js";
import { randomName } from "../evaluation/_random_name.js";
import { Client } from "../client.js";
import { LangSmithConflictError } from "../utils/error.js";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
} from "./matchers.js";
import { jestAsyncLocalStorageInstance, trackingEnabled } from "./globals.js";
import expectWithGradedBy from "./vendor/chain.js";
import type { SimpleEvaluator } from "./vendor/gradedBy.js";

declare global {
  namespace jest {
    interface AsymmetricMatchers {
      toBeRelativeCloseTo(expected: string, options: any): void;
      toBeAbsoluteCloseTo(expected: string, options: any): void;
      toBeSemanticCloseTo(expected: string, options: any): Promise<void>;
    }
    interface Matchers<R> {
      toBeRelativeCloseTo(expected: string, options: any): R;
      toBeAbsoluteCloseTo(expected: string, options: any): R;
      toBeSemanticCloseTo(expected: string, options: any): Promise<R>;
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

function wrapDescribeMethod(
  method: (name: string, fn: () => void | Promise<void>) => void
): LangSmithJestDescribeWrapper {
  return function (
    datasetName: string,
    fn: () => void | Promise<void>,
    config?: Partial<RunTreeConfig>
  ) {
    const testClient = config?.client ?? RunTree.getSharedClient();
    return method(datasetName, () => {
      beforeAll(async () => {
        if (!trackingEnabled()) {
          jestAsyncLocalStorageInstance.enterWith({
            createdAt: new Date().toISOString(),
          });
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
            const inputHash = crypto
              .createHash("sha256")
              .update(JSON.stringify(example.inputs))
              .digest("hex");
            examples.push({ ...example, inputHash });
          }
          const project = await _createProject(testClient, dataset.id);
          jestAsyncLocalStorageInstance.enterWith({
            dataset,
            examples,
            createdAt: new Date().toISOString(),
            project,
            client: testClient,
          });
        }
      });
      fn();
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

function wrapTestMethod(method: (...args: any[]) => void) {
  return function <
    I extends Record<string, any> = Record<string, any>,
    O extends Record<string, any> = Record<string, any>
  >(
    params: { inputs: I; outputs: O } | string,
    config?: Partial<RunTreeConfig>
  ): LangSmithJestTestWrapper<I, O> {
    return async function (...args) {
      return method(
        args[0],
        async () => {
          const testInput: I =
            typeof params === "string" ? ({} as I) : params.inputs;
          const testOutput: O =
            typeof params === "string" ? ({} as O) : params.outputs;
          const inputHash = crypto
            .createHash("sha256")
            .update(JSON.stringify(testInput))
            .digest("hex");
          const context = jestAsyncLocalStorageInstance.getStore();
          if (context === undefined) {
            throw new Error(
              `Could not retrieve test context.\nPlease make sure you have tracing enabled and you are wrapping all of your test cases in an "ls.describe()" function.`
            );
          }
          const { examples, dataset, createdAt, project, client } = context;
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
            let example = (examples ?? []).find((example) => {
              return example.inputHash === inputHash;
            });
            if (example === undefined) {
              const newExample = await testClient.createExample(
                testInput,
                testOutput,
                {
                  datasetId: dataset?.id,
                  createdAt: new Date(createdAt ?? new Date()),
                }
              );
              example = { ...newExample, inputHash };
            }
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
    };
  };
}

const lsTest = Object.assign(wrapTestMethod(test), {
  only: wrapTestMethod(test.only),
  skip: wrapTestMethod(test.skip),
});

export default {
  test: lsTest,
  it: lsTest,
  describe: lsDescribe,
  expect: expectWithGradedBy,
};

export { type SimpleEvaluator };
