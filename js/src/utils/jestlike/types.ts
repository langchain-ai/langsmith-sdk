import { EvaluationResult } from "../../evaluation/evaluator.js";
import type { RunTreeConfig } from "../../run_trees.js";
import type { SimpleEvaluator } from "./vendor/evaluatedBy.js";

export { type SimpleEvaluator };

export type LangSmithJestlikeWrapperConfig = Partial<
  Omit<RunTreeConfig, "client">
> & {
  iterations?: number;
  enableTestTracking?: boolean;
};

export type LangSmithJestlikeWrapperParams<I, O> = {
  inputs: I;
  referenceOutputs: O;
  config?: LangSmithJestlikeWrapperConfig;
};

export type LangSmithJestDescribeWrapper = (
  name: string,
  fn: () => void | Promise<void>,
  config?: Partial<RunTreeConfig>
) => void;

export type SimpleEvaluationResult = {
  key: EvaluationResult["key"];
  score: NonNullable<EvaluationResult["score"]>;
  comment?: EvaluationResult["comment"];
};
