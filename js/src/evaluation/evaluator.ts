import { Example, Run, ScoreType, ValueType } from "../schemas.js";

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
 * Configuration for feedback.
 */
export type FeedbackConfig = {
  /**
   * The type of feedback.
   * - "continuous": Feedback with a continuous numeric.
   * - "categorical": Feedback with a categorical value (classes)
   * - "freeform": Feedback with a freeform text value (notes).
   */
  type: "continuous" | "categorical" | "freeform";

  /**
   * The minimum value for continuous feedback.
   */
  min?: number;

  /**
   * The maximum value for continuous feedback.
   */
  max?: number;

  /**
   * The categories for categorical feedback.
   * Each category can be a string or an object with additional properties.
   */
  categories?: (Category | Record<string, unknown>)[];
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

export interface RunEvaluator {
  evaluateRun(run: Run, example?: Example): Promise<EvaluationResult>;
}
