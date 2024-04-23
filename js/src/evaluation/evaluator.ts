import {
  Example,
  FeedbackConfig,
  Run,
  ScoreType,
  ValueType,
} from "../schemas.js";

/**
 * Represents a categorical class.
 */
export type Category = {
  /**
   * The value of the category.
   */
  value?: number;
  /**
   * The label of the category.
   */
  label: string;
};

/**
 * Represents the result of an evaluation.
 */
export type EvaluationResult = {
  /**
   * The key associated with the evaluation result.
   */
  key: string;
  /**
   * The score of the evaluation result.
   */
  score?: ScoreType;
  /**
   * The value of the evaluation result.
   */
  value?: ValueType;
  /**
   * A comment associated with the evaluation result.
   */
  comment?: string;
  /**
   * A correction record associated with the evaluation result.
   */
  correction?: Record<string, unknown>;
  /**
   * Information about the evaluator.
   */
  evaluatorInfo?: Record<string, unknown>;
  /**
   * The source run ID of the evaluation result.
   * If set, a link to the source run will be available in the UI.
   */
  sourceRunId?: string;
  /**
   * The target run ID of the evaluation result.
   * If this is not set, the target run ID is assumed to be
   * the root of the trace.
   */
  targetRunId?: string;

  /**
   * The feedback config associated with the evaluation result.
   * If set, this will be used to define how a feedback key
   * should be interpreted.
   */
  feedbackConfig?: FeedbackConfig;
};

/**
 * Batch evaluation results, if your evaluator wishes
 * to return multiple scores.
 */
export type EvaluationResults = {
  /**
   * The evaluation results.
   */
  results: Array<EvaluationResult>;
};

export interface RunEvaluator {
  evaluateRun(run: Run, example?: Example): Promise<EvaluationResult>;
}
