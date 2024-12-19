import { expect, test } from "@jest/globals";
import {
  runEvaluator,
  RunEvaluator,
  RunEvaluatorLike,
} from "./evaluation/evaluator.js";
import { getCurrentRunTree, traceable } from "./traceable.js";
import { RunTree, RunTreeConfig } from "./run_trees.js";
import { KVMap } from "./schemas.js";

// Add this type declaration to extend Jest's matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toPassEvaluator(
        evaluator: RunEvaluatorLike | RunEvaluator,
        expected?: KVMap
      ): Promise<R>;
    }
  }
}

const LS_TEST_CONFIG: Record<string, any> = {};

const lsSetup = ({ datasetId }: { datasetId: string }) => {
  LS_TEST_CONFIG.datasetId = datasetId;
  return LS_TEST_CONFIG;
};

const NULL_UUID = "00000000-0000-0000-0000-000000000000";

function isRunEvaluator(x: RunEvaluatorLike | RunEvaluator): x is RunEvaluator {
  return typeof x !== "function";
}

expect.extend({
  toPassEvaluator: async function (
    actual,
    evaluator: RunEvaluatorLike | RunEvaluator,
    expected?: KVMap
  ) {
    const runTree = getCurrentRunTree();
    const mockExample = {
      id: NULL_UUID,
      inputs: runTree.inputs,
      outputs: expected,
      created_at: new Date().toISOString(),
      runs: [],
      dataset_id: NULL_UUID,
    };

    const coercedEvaluator = isRunEvaluator(evaluator)
      ? evaluator
      : runEvaluator(evaluator);
    const evalResult = await coercedEvaluator.evaluateRun(runTree, mockExample);
    if (!("results" in evalResult) && !evalResult.score) {
      return {
        pass: false,
        message: () =>
          `expected ${this.utils.printReceived(
            actual
          )} to pass evaluator. Failed wih ${JSON.stringify(
            evalResult,
            null,
            2
          )}`,
      };
    }
    return {
      pass: true,
      message: () =>
        `evaluator passed with score ${JSON.stringify(evalResult, null, 2)}`,
    };
  },
});

export type LangSmithJestWrapper<T> = (
  name: string,
  fn: (input: T) => unknown | Promise<unknown>,
  timeout?: number
) => void;

function wrapJestMethod(method: (...args: any[]) => void) {
  function langsmithJestWrapper<
    T extends Record<string, any> = Record<string, any>
  >(
    input: T | string,
    config?: Partial<RunTreeConfig>
  ): LangSmithJestWrapper<T> {
    const testClient = config?.client ?? RunTree.getSharedClient();
    return async function (...args) {
      return method(
        args[0],
        async () => {
          const testInput: T = typeof input === "string" ? ({} as T) : input;
          const tracedFunction = traceable(async (testInput: T) => {
            return args[1](testInput);
          }, config ?? { client: testClient });
          await (tracedFunction as any)(testInput);
          await testClient.awaitPendingTraceBatches();
        },
        ...args.slice(2)
      );
    };
  }
  return langsmithJestWrapper;
}

const lsTest = Object.assign(wrapJestMethod(test), {
  only: wrapJestMethod(test.skip),
  skip: wrapJestMethod(test.only),
});

export const ls = {
  test: lsTest,
  setup: lsSetup,
};
