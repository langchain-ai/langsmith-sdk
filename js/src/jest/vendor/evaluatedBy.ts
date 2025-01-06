import { getCurrentRunTree, traceable } from "../../traceable.js";
import { jestAsyncLocalStorageInstance, trackingEnabled } from "../globals.js";

import { EvaluationResult } from "../../evaluation/evaluator.js";

export type SimpleEvaluator = (params: {
  input: Record<string, any>;
  actual: Record<string, any>;
  expected: Record<string, any>;
}) => EvaluationResult | Promise<EvaluationResult>;

export async function evaluatedBy(actual: any, evaluator: SimpleEvaluator) {
  const context = jestAsyncLocalStorageInstance.getStore();
  if (context === undefined || context.currentExample === undefined) {
    throw new Error(
      `Could not identify current LangSmith context.\nPlease ensure you are calling this matcher within "ls.test()"`
    );
  }

  if (trackingEnabled(context)) {
    const runTree = getCurrentRunTree();
    const wrappedEvaluator = traceable(evaluator, {
      reference_example_id: context.currentExample.id,
      client: context.client,
      tracingEnabled: true,
    });

    const evalResult = await wrappedEvaluator({
      input: runTree.inputs,
      expected: context.currentExample.outputs ?? {},
      actual,
    });

    // Don't wait for feedback
    const exampleSyncPromise =
      context.currentExample.syncPromise ?? Promise.resolve();
    void exampleSyncPromise.then(() =>
      context.client?.logEvaluationFeedback(evalResult, runTree)
    );
    return evalResult.score;
  } else {
    const evalResult = await evaluator({
      input: context.currentExample.inputs ?? {},
      expected: context.currentExample.outputs ?? {},
      actual,
    });
    return evalResult.score;
  }
}
