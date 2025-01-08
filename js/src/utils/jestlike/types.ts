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
  expected: O;
  config?: LangSmithJestlikeWrapperConfig;
};

export type LangSmithJestDescribeWrapper = (
  name: string,
  fn: () => void | Promise<void>,
  config?: Partial<RunTreeConfig>
) => void;
