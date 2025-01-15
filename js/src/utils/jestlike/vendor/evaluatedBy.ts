import { getCurrentRunTree, ROOT, traceable } from "../../../traceable.js";
import {
  testWrapperAsyncLocalStorageInstance,
  _logTestFeedback,
  trackingEnabled,
} from "../globals.js";

import { EvaluationResult } from "../../../evaluation/evaluator.js";
import { RunTree } from "../../../run_trees.js";

export type SimpleEvaluatorParams = {
  inputs: Record<string, any>;
  actual: Record<string, any>;
  expected: Record<string, any>;
};

export type SimpleEvaluator = (
  params: SimpleEvaluatorParams
) => EvaluationResult | Promise<EvaluationResult>;

export async function evaluatedBy(actual: any, evaluator: SimpleEvaluator) {
  const context = testWrapperAsyncLocalStorageInstance.getStore();
  if (context === undefined || context.currentExample === undefined) {
    throw new Error(
      `Could not identify current LangSmith context.\nPlease ensure you are calling this matcher within "ls.test()"`
    );
  }

  if (trackingEnabled(context)) {
    const runTree = getCurrentRunTree();
    let evalRunId;
    const wrappedEvaluator = traceable(
      async (runTree: RunTree, params: SimpleEvaluatorParams) => {
        const res = await evaluator(params);
        evalRunId = runTree.id;
        return res;
      },
      {
        reference_example_id: context.currentExample.id,
        client: context.client,
        tracingEnabled: true,
        name: evaluator.name ?? "<evaluator>",
        project_name: "evaluators",
      }
    );

    const evalResult = await wrappedEvaluator(ROOT, {
      inputs: runTree.inputs,
      expected: context.currentExample.outputs ?? {},
      actual,
    });
    _logTestFeedback({
      exampleId: context.currentExample.id!,
      feedback: evalResult,
      context,
      runTree,
      client: context.client,
      sourceRunId: evalRunId,
    });
    return evalResult.score;
  } else {
    const evalResult = await evaluator({
      inputs: context.currentExample.inputs ?? {},
      expected: context.currentExample.outputs ?? {},
      actual,
    });
    _logTestFeedback({
      exampleId: context.currentExample.id!,
      feedback: evalResult,
      context,
      client: context.client,
    });
    return evalResult.score;
  }
}
