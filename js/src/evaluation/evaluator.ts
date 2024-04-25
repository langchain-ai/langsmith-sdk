import {
  Example,
  FeedbackConfig,
  Run,
  ScoreType,
  ValueType,
} from "../schemas.js";
import { v4 as uuidv4 } from "uuid";
import { wrapFunctionAndEnsureTraceable } from "../traceable.js";
import { RunTreeConfig } from "../run_trees.js";

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
  evaluateRun(
    run: Run,
    example?: Example,
    options?: Partial<RunTreeConfig>
  ): Promise<EvaluationResult>;
}

export type DynamicRunEvaluatorParams = {
  input: Record<string, unknown>;
  prediction?: Record<string, unknown>;
  reference?: Record<string, unknown>;
  run: Run;
  example?: Example;
};

export type RunEvaluatorLike =
  | ((
      run: Run,
      example?: Example
    ) => Promise<EvaluationResult | EvaluationResults>)
  | ((run: Run, example?: Example) => EvaluationResult | EvaluationResults);

/**
 * Wraps an evaluator function + implements the RunEvaluator interface.
 */
export class DynamicRunEvaluator<Func extends (...args: any[]) => any>
  implements RunEvaluator
{
  // func: ReturnType<typeof wrapFunctionAndEnsureTraceable<Func>>;

  func: Func;

  constructor(evaluator: Func) {
    const wrappedFunc = (input: Record<string, any>) => {
      const newInputs = {
        run: input.run,
        example: input.example,
      };
      return evaluator(...Object.values(newInputs));
    };
    this.func = wrappedFunc as Func;
  }

  private coerceEvaluationResults(
    results: Record<string, any> | EvaluationResults,
    sourceRunId: string
  ): EvaluationResult {
    if ("results" in results) {
      throw new Error("EvaluationResults not supported yet.");
      // const cp = { ...results };
      // cp.results = results.results.map((r: any) =>
      //   this.coerceEvaluationResult(r, sourceRunId)
      // );
      // return cp as EvaluationResults;
    }

    return this.coerceEvaluationResult(
      results as Record<string, any>,
      sourceRunId,
      true
    );
  }

  private coerceEvaluationResult(
    result: EvaluationResult | Record<string, any>,
    sourceRunId: string,
    allowNoKey: boolean = false
  ): EvaluationResult {
    if ("key" in result) {
      if (!result.sourceRunId) {
        result.sourceRunId = sourceRunId;
      }
      return result as EvaluationResult;
    }

    if (!("key" in result)) {
      if (allowNoKey) {
        result["key"] = this.func.name;
      }
    }
    return {
      sourceRunId,
      ...result,
    } as EvaluationResult;
  }

  /**
   * Evaluates a run with an optional example and returns the evaluation result.
   * @param run The run to evaluate.
   * @param example The optional example to use for evaluation.
   * @returns A promise that extracts to the evaluation result.
   */
  async evaluateRun(
    run: Run,
    example?: Example,
    options?: Partial<RunTreeConfig>
  ): Promise<EvaluationResult> {
    const sourceRunId = uuidv4();
    const metadata: Record<string, any> = {
      targetRunId: run.id,
    };
    if ("session_id" in run) {
      metadata["experiment"] = run.session_id;
    }
    const wrappedTraceableFunc = wrapFunctionAndEnsureTraceable<Func>(
      this.func,
      options || {},
      "evaluator"
    );
    const result = await wrappedTraceableFunc(
      { run, example },
      {
        metadata,
      }
    );

    // Check the one required property of EvaluationResult since 'instanceof' is not possible
    if ("key" in result) {
      if (!result.sourceRunId) {
        result.sourceRunId = sourceRunId;
      }
      return result;
    }
    if (typeof result !== "object") {
      throw new Error("Evaluator function must return an object.");
    }

    return this.coerceEvaluationResults(result, sourceRunId);
  }
}

export function runEvaluator(func: RunEvaluatorLike): RunEvaluator {
  return new DynamicRunEvaluator(func);
}
