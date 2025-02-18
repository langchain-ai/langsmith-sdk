import { CreateProjectParams } from "../../client.js";
import { EvaluationResult } from "../../evaluation/evaluator.js";
import { Client } from "../../index.js";
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
  referenceOutputs?: O;
  config?: LangSmithJestlikeWrapperConfig;
};

export type LangSmithJestlikeDescribeWrapperConfig = {
  client?: Client;
  enableTestTracking?: boolean;
  testSuiteName?: string;
} & Partial<Omit<CreateProjectParams, "referenceDatasetId">>;

export type LangSmithJestlikeDescribeWrapper = (
  name: string,
  fn: () => void | Promise<void>,
  config?: LangSmithJestlikeDescribeWrapperConfig
) => void;

/** @deprecated Import as `LangSmithJestlikeDescribeWrapper` instead. */
export type LangSmithJestDescribeWrapper = LangSmithJestlikeDescribeWrapper;

export type SimpleEvaluationResult = {
  key: EvaluationResult["key"];
  score: NonNullable<EvaluationResult["score"]>;
  comment?: EvaluationResult["comment"];
};
