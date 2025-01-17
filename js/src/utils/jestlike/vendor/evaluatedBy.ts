import { getCurrentRunTree, ROOT, traceable } from "../../../traceable.js";
import {
  testWrapperAsyncLocalStorageInstance,
  _logTestFeedback,
  trackingEnabled,
} from "../globals.js";

import { EvaluationResult } from "../../../evaluation/evaluator.js";
import { RunTree, RunTreeConfig } from "../../../run_trees.js";
import { v4 } from "uuid";

export type SimpleEvaluatorParams = {
  inputs: Record<string, any>;
  referenceOutputs: Record<string, any>;
  outputs: Record<string, any>;
};

export type SimpleEvaluator = (
  params: SimpleEvaluatorParams
) => EvaluationResult | Promise<EvaluationResult>;

function isEvaluationResult(x: unknown): x is EvaluationResult {
  return (
    x != null &&
    typeof x === "object" &&
    "key" in x &&
    typeof x.key === "string" &&
    "score" in x
  );
}

export function wrapEvaluator<I, O>(evaluator: (input: I) => O | Promise<O>) {
  return async (
    input: I,
    config?: Partial<RunTreeConfig> & { runId?: string }
  ): Promise<O> => {
    const context = testWrapperAsyncLocalStorageInstance.getStore();
    if (context === undefined || context.currentExample === undefined) {
      throw new Error(
        [
          `Could not identify current LangSmith context.`,
          `Please ensure you are calling this matcher within "ls.test()"`,
          `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
        ].join("\n")
      );
    }
    const evalRunId = config?.runId ?? config?.id ?? v4();
    let evalResult;
    let currentRunTree;
    if (trackingEnabled(context)) {
      currentRunTree = getCurrentRunTree();
      const wrappedEvaluator = traceable(
        async (_runTree: RunTree, params: I) => {
          return evaluator(params);
        },
        {
          ...config,
          id: evalRunId,
          trace_id: evalRunId,
          reference_example_id: context.currentExample.id,
          client: context.client,
          tracingEnabled: true,
          name: evaluator.name ?? "<evaluator>",
          project_name: "evaluators",
        }
      );

      evalResult = await wrappedEvaluator(ROOT, input);
    } else {
      evalResult = await evaluator(input);
    }
    if (isEvaluationResult(evalResult)) {
      _logTestFeedback({
        exampleId: context?.currentExample?.id!,
        feedback: evalResult,
        context,
        runTree: currentRunTree,
        client: context.client,
        sourceRunId: evalRunId,
      });
    }
    return evalResult;
  };
}

export async function evaluatedBy(outputs: any, evaluator: SimpleEvaluator) {
  const context = testWrapperAsyncLocalStorageInstance.getStore();
  if (context === undefined || context.currentExample === undefined) {
    throw new Error(
      [
        `Could not identify current LangSmith context.`,
        `Please ensure you are calling this matcher within "ls.test()"`,
        `See this page for more information: https://docs.smith.langchain.com/evaluation/how_to_guides/vitest_jest`,
      ].join("\n")
    );
  }
  const runTree = getCurrentRunTree();
  const wrappedEvaluator = wrapEvaluator(evaluator);
  const evalRunId = v4();
  const evalResult = await wrappedEvaluator(
    {
      inputs: runTree.inputs,
      referenceOutputs: context?.currentExample?.outputs ?? {},
      outputs,
    },
    { runId: evalRunId }
  );
  return evalResult.score;
}
