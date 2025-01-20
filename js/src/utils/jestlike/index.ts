/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable @typescript-eslint/no-namespace */

import crypto from "crypto";
import { v4, v5 } from "uuid";
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs/promises";
import { execSync } from "child_process";

import { getCurrentRunTree, traceable } from "../../traceable.js";
import { KVMap, TracerSession } from "../../schemas.js";
import { randomName } from "../../evaluation/_random_name.js";
import { Client, CreateProjectParams } from "../../client.js";
import { LangSmithConflictError } from "../../utils/error.js";
import {
  toBeRelativeCloseTo,
  toBeAbsoluteCloseTo,
  toBeSemanticCloseTo,
} from "./matchers.js";
import {
  evaluatorLogFeedbackPromises,
  TestWrapperAsyncLocalStorageData,
  testWrapperAsyncLocalStorageInstance,
  _logTestFeedback,
  syncExamplePromises,
  trackingEnabled,
  DEFAULT_TEST_CLIENT,
} from "./globals.js";
import { wrapExpect } from "./vendor/chain.js";
import { EvaluationResult } from "../../evaluation/evaluator.js";
import type {
  LangSmithJestlikeWrapperConfig,
  LangSmithJestlikeWrapperParams,
  LangSmithJestDescribeWrapper,
} from "./types.js";

const DEFAULT_TEST_TIMEOUT = 30_000;

const UUID5_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";
// From https://stackoverflow.com/a/29497680
export const STRIP_ANSI_REGEX =
  // eslint-disable-next-line no-control-regex
  /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g;
export const TEST_ID_DELIMITER = ", test_id=";

export function logFeedback(
  feedback: EvaluationResult,
  config?: { sourceRunId?: string }
) {
  const context = testWrapperAsyncLocalStorageInstance.getStore();
  if (context === undefined) {
    throw new Error(
      [
        `Could not retrieve test context. Make sure your logFeedback call is nested within a "ls.describe()" block.`,
        `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
      ].join("\n")
    );
  }
  if (context.currentExample === undefined) {
    throw new Error(
      [
        `Could not retrieve current example. Make sure your logFeedback call is nested within a "ls.test()" block.`,
        `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
      ].join("\n")
    );
  }
  _logTestFeedback({
    ...config,
    exampleId: context.currentExample.id,
    feedback: feedback,
    context,
    runTree: trackingEnabled(context) ? getCurrentRunTree() : undefined,
    client: context.client,
  });
}

export function logOutputs(output: Record<string, unknown>) {
  const context = testWrapperAsyncLocalStorageInstance.getStore();
  if (context === undefined) {
    throw new Error(
      `Could not retrieve test context. Make sure your logFeedback call is nested within a "ls.describe()" block.`
    );
  }
  if (
    context.currentExample === undefined ||
    context.setLoggedOutput === undefined
  ) {
    throw new Error(
      [
        `Could not retrieve current example. Make sure your logFeedback call is nested within a "ls.test()" block.`,
        `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
      ].join("\n")
    );
  }
  context.setLoggedOutput(output);
}

export function generateWrapperFromJestlikeMethods(
  methods: Record<string, any>,
  testRunnerName: string
) {
  const { expect, test, describe, beforeAll, afterAll } = methods;

  const objectHash = (obj: KVMap, depth = 0): string => {
    // Prevent infinite recursion
    if (depth > 50) {
      throw new Error(
        "Object is too deep to check equality for serialization. Please use a simpler example."
      );
    }

    if (Array.isArray(obj)) {
      const arrayHash = obj
        .map((item) => objectHash(item, depth + 1))
        .join(",");
      return crypto.createHash("sha256").update(arrayHash).digest("hex");
    }

    if (obj && typeof obj === "object") {
      const sortedHash = Object.keys(obj)
        .sort()
        .map((key) => `${key}:${objectHash(obj[key], depth + 1)}`)
        .join(",");
      return crypto.createHash("sha256").update(sortedHash).digest("hex");
    }

    return crypto
      .createHash("sha256")
      .update(JSON.stringify(obj))
      .digest("hex");
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

  const datasetSetupInfo = new Map();

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
    const {
      client,
      exampleId,
      inputs,
      outputs,
      metadata,
      createdAt,
      datasetId,
    } = params;
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

  async function runDatasetSetup(context: TestWrapperAsyncLocalStorageData) {
    const {
      client: testClient,
      suiteName: datasetName,
      projectConfig,
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
            metadata: { __ls_runner: testRunnerName },
          });
        } else {
          throw e;
        }
      }
      const project = await _createProject(
        testClient,
        dataset.id,
        projectConfig
      );
      const datasetUrl = await testClient.getDatasetUrl({
        datasetId: dataset.id,
      });
      const experimentUrl = `${datasetUrl}/compare?selectedSessions=${project.id}`;
      console.log(
        `[LANGSMITH]: Experiment starting! View results at ${experimentUrl}`
      );
      storageValue = {
        dataset,
        project,
        client: testClient,
        experimentUrl,
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
      const client = experimentConfig?.client ?? DEFAULT_TEST_CLIENT;
      return method(datasetName, () => {
        const startTime = new Date();
        const suiteUuid = v4();
        const context = {
          suiteUuid,
          suiteName: datasetName,
          client,
          createdAt: new Date().toISOString(),
          projectConfig: {
            ...experimentConfig,
            metadata: {
              ...experimentConfig?.metadata,
              __ls_runner: testRunnerName,
            },
          },
          enableTestTracking: experimentConfig?.enableTestTracking,
        };

        beforeAll(async () => {
          const storageValue = await runDatasetSetup(context);
          datasetSetupInfo.set(suiteUuid, storageValue);
        });

        afterAll(async () => {
          await Promise.all([
            client.awaitPendingTraceBatches(),
            ...syncExamplePromises.values(),
            ...evaluatorLogFeedbackPromises.values(),
          ]);
          if (!trackingEnabled(context)) {
            return;
          }
          const examples = [...syncExamplePromises.values()];
          if (examples.length === 0) {
            return;
          }
          const endTime = new Date();
          let branch;
          let commit;
          try {
            branch = execSync("git rev-parse --abbrev-ref HEAD")
              .toString()
              .trim();
            commit = execSync("git rev-parse HEAD").toString().trim();
          } catch {
            return;
          }
          if (branch === undefined || commit === undefined) {
            return;
          }
          try {
            let finalModifiedAt = examples.reduce(
              (latestModifiedAt, example) => {
                if (
                  new Date(latestModifiedAt).getTime() >
                  new Date(example.modified_at).getTime()
                ) {
                  return latestModifiedAt;
                } else {
                  return example.modified_at;
                }
              },
              examples[0].modified_at
            );
            if (new Date(finalModifiedAt).getTime() < startTime.getTime()) {
              finalModifiedAt = endTime.toISOString();
            }
            const datasetInfo = datasetSetupInfo.get(suiteUuid);
            const { as_of } = await client.readDatasetVersion({
              datasetId: datasetInfo.dataset.id,
              asOf: finalModifiedAt,
            });
            await Promise.all([
              client.updateDatasetTag({
                datasetId: datasetInfo.dataset.id,
                asOf: as_of,
                tag: `git:branch:${branch}`,
              }),
              client.updateDatasetTag({
                datasetId: datasetInfo.dataset.id,
                asOf: as_of,
                tag: `git:commit:${commit}`,
              }),
            ]);
          } catch {
            return;
          }
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
         * concurrency requirement, we can remove this hack.
         */
        void testWrapperAsyncLocalStorageInstance.run(context, fn);
      });
    };
  }

  const lsDescribe = Object.assign(wrapDescribeMethod(describe), {
    only: wrapDescribeMethod(describe.only),
    skip: wrapDescribeMethod(describe.skip),
  });

  function wrapTestMethod(method: (...args: any[]) => void) {
    return function <
      I extends Record<string, any> = Record<string, any>,
      O extends Record<string, any> = Record<string, any>
    >(
      name: string,
      lsParams: LangSmithJestlikeWrapperParams<I, O>,
      testFn: (
        data: { inputs: I; referenceOutputs?: O } & Record<string, any>
      ) => unknown | Promise<unknown>,
      timeout?: number
    ) {
      // Due to https://github.com/jestjs/jest/issues/13653,
      // we must access the local store value here before
      // doing anything async.
      const context = testWrapperAsyncLocalStorageInstance.getStore();
      if (
        context !== undefined &&
        lsParams.config?.enableTestTracking !== undefined
      ) {
        context.enableTestTracking = lsParams.config.enableTestTracking;
      }
      const { config, inputs, referenceOutputs, ...rest } = lsParams;
      const totalRuns = config?.iterations ?? 1;
      for (let i = 0; i < totalRuns; i += 1) {
        const testUuid = v4().replace(/-/g, "").slice(0, 13);
        // Jest will not group tests under the same "describe" group if you await the test and
        // total runs is greater than 1.
        const resultsPath = path.join(
          os.tmpdir(),
          "langsmith_test_results",
          `${testUuid}.json`
        );
        void method(
          `${name}${
            totalRuns > 1 ? `, run ${i}` : ""
          }${TEST_ID_DELIMITER}${testUuid}`,
          async () => {
            if (context === undefined) {
              throw new Error(
                [
                  `Could not retrieve test context.`,
                  `Please make sure you have tracing enabled and you are wrapping all of your test cases in an "ls.describe()" function.`,
                  `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
                ].join("\n")
              );
            }
            if (!datasetSetupInfo.get(context.suiteUuid)) {
              throw new Error(
                "Dataset failed to initialize. Please check your LangSmith environment variables."
              );
            }
            const { dataset, createdAt, project, client, experimentUrl } =
              datasetSetupInfo.get(context.suiteUuid);
            const testInput: I = inputs;
            const testOutput: O = referenceOutputs;
            const testFeedback: EvaluationResult[] = [];
            const onFeedbackLogged = (feedback: EvaluationResult) =>
              testFeedback.push(feedback);
            let loggedOutput: Record<string, unknown> | undefined;
            const setLoggedOutput = (value: Record<string, unknown>) => {
              if (loggedOutput !== undefined) {
                console.warn(
                  `[WARN]: New "logOutputs()" call will override output set by previous "logOutputs()" call.`
                );
              }
              loggedOutput = value;
            };
            let exampleId: string;
            const runTestFn = async () => {
              const testContext =
                testWrapperAsyncLocalStorageInstance.getStore();
              if (testContext === undefined) {
                throw new Error(
                  "Could not identify test context. Please contact us for help."
                );
              }
              try {
                const res = await testFn({
                  ...rest,
                  inputs: testInput,
                  referenceOutputs: testOutput,
                });
                _logTestFeedback({
                  exampleId,
                  feedback: { key: "pass", score: true },
                  context: testContext,
                  runTree: trackingEnabled(testContext)
                    ? getCurrentRunTree()
                    : undefined,
                  client: testContext.client,
                });
                if (res != null) {
                  if (loggedOutput !== undefined) {
                    console.warn(
                      `[WARN]: Returned value from test function will override output set by previous "logOutputs()" call.`
                    );
                  }
                  loggedOutput =
                    typeof res === "object"
                      ? (res as Record<string, unknown>)
                      : { result: res };
                }
                return loggedOutput;
              } catch (e: any) {
                _logTestFeedback({
                  exampleId,
                  feedback: { key: "pass", score: false },
                  context: testContext,
                  runTree: trackingEnabled(testContext)
                    ? getCurrentRunTree()
                    : undefined,
                  client: testContext.client,
                });
                const rawError = e;
                const strippedErrorMessage = e.message.replace(
                  STRIP_ANSI_REGEX,
                  ""
                );
                const langsmithFriendlyError = new Error(strippedErrorMessage);
                (langsmithFriendlyError as any).rawJestError = rawError;
                throw langsmithFriendlyError;
              }
            };
            try {
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
                exampleId = getExampleId(
                  dataset.name,
                  inputs,
                  referenceOutputs
                );

                // TODO: Create or update the example in the background
                // Currently run end time has to be after example modified time
                // for examples to render properly, so we must modify the example
                // first before running the test.
                if (syncExamplePromises.get(exampleId) === undefined) {
                  syncExamplePromises.set(
                    exampleId,
                    await syncExample({
                      client,
                      exampleId,
                      datasetId: dataset.id,
                      inputs,
                      outputs: referenceOutputs,
                      metadata: {},
                      createdAt,
                    })
                  );
                }

                const traceableOptions = {
                  reference_example_id: exampleId,
                  project_name: project!.name,
                  metadata: {
                    ...config?.metadata,
                  },
                  client,
                  tracingEnabled: true,
                  name,
                };

                // Pass inputs into traceable so tracing works correctly but
                // provide both to the user-defined test function
                const tracedFunction = traceable(
                  async () => {
                    return testWrapperAsyncLocalStorageInstance.run(
                      {
                        ...context,
                        currentExample: {
                          inputs,
                          outputs: referenceOutputs,
                          id: exampleId,
                        },
                        setLoggedOutput,
                        onFeedbackLogged,
                      },
                      runTestFn
                    );
                  },
                  {
                    ...traceableOptions,
                    ...config,
                  }
                );
                try {
                  await tracedFunction(testInput);
                } catch (e: any) {
                  // Extract raw Jest error from LangSmith formatted one and throw
                  if (e.rawJestError !== undefined) {
                    throw e.rawJestError;
                  }
                  throw e;
                }
              } else {
                try {
                  await testWrapperAsyncLocalStorageInstance.run(
                    {
                      ...context,
                      currentExample: {
                        inputs: testInput,
                        outputs: testOutput,
                      },
                      setLoggedOutput,
                      onFeedbackLogged,
                    },
                    runTestFn
                  );
                } catch (e: any) {
                  // Extract raw Jest error from LangSmith formatted one and throw
                  if (e.rawJestError !== undefined) {
                    throw e.rawJestError;
                  }
                  throw e;
                }
              }
            } finally {
              await fs.mkdir(path.dirname(resultsPath), { recursive: true });
              await fs.writeFile(
                resultsPath,
                JSON.stringify({
                  inputs,
                  referenceOutputs,
                  outputs: loggedOutput,
                  feedback: testFeedback,
                  experimentUrl,
                })
              );
            }
          },
          timeout ?? DEFAULT_TEST_TIMEOUT
        );
      }
    };
  }

  function createEachMethod(method: (...args: any[]) => void) {
    function eachMethod<I extends KVMap, O extends KVMap>(
      table: ({ inputs: I; referenceOutputs: O } & Record<string, any>)[],
      config?: LangSmithJestlikeWrapperConfig
    ) {
      const context = testWrapperAsyncLocalStorageInstance.getStore();
      if (context === undefined) {
        throw new Error(
          [
            `Could not retrieve test context. Make sure your test is nested within a "ls.describe()" block.`,
            `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
          ].join("\n")
        );
      }
      return function (
        name: string,
        fn: (
          params: { inputs: I; referenceOutputs?: O } & Record<string, any>
        ) => unknown | Promise<unknown>,
        timeout?: number
      ) {
        for (let i = 0; i < table.length; i += 1) {
          const example = table[i];
          wrapTestMethod(method)<I, O>(
            `${name}, item ${i}`,
            {
              ...example,
              inputs: example.inputs,
              referenceOutputs: example.referenceOutputs,
              config,
            },
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

  return {
    test: lsTest,
    it: lsTest,
    describe: lsDescribe,
    expect: wrappedExpect,
    toBeRelativeCloseTo,
    toBeAbsoluteCloseTo,
    toBeSemanticCloseTo,
  };
}
