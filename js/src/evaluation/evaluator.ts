import {
  Example,
  FeedbackConfig,
  Run,
  ScoreType,
  ValueType,
} from "../schemas.js";
import { v4 as uuidv4 } from "uuid";
import { TraceableFunction, traceable } from "../traceable.js";
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
  ): Promise<EvaluationResult | EvaluationResults>;
}

export type RunEvaluatorLike =
  | ((
      run: Run,
      example?: Example
    ) => Promise<EvaluationResult | EvaluationResult[] | EvaluationResults>)
  | ((
      run: Run,
      example?: Example
    ) => EvaluationResult | EvaluationResult[] | EvaluationResults)
  | ((
      run: Run,
      example: Example
    ) => Promise<EvaluationResult | EvaluationResult[] | EvaluationResults>)
  | ((
      run: Run,
      example: Example
    ) => EvaluationResult | EvaluationResult[] | EvaluationResults)
  | ((args: {
      run: Run;
      example: Example;
      inputs: Record<string, any>;
      outputs: Record<string, any>;
      referenceOutputs?: Record<string, any>;
    }) => EvaluationResult | EvaluationResult[] | EvaluationResults)
  | ((args: {
      run: Run;
      example: Example;
      inputs: Record<string, any>;
      outputs: Record<string, any>;
      referenceOutputs?: Record<string, any>;
    }) => Promise<EvaluationResult | EvaluationResult[] | EvaluationResults>);

/**
 * Wraps an evaluator function + implements the RunEvaluator interface.
 */
export class DynamicRunEvaluator<Func extends (...args: any[]) => any>
  implements RunEvaluator
{
  func: Func;

  constructor(evaluator: Func) {
    this.func = ((input: {
      langSmithRunAndExample: { run: Run; example: Example };
    }) => {
      const { run, example } = input.langSmithRunAndExample;

      return evaluator(
        {
          ...run,
          run,
          example,
          inputs: example?.inputs,
          outputs: run?.outputs,
          referenceOutputs: example?.outputs,
          attachments: example?.attachments,
        },
        example
      );
    }) as Func;
  }

  private isEvaluationResults(x: unknown): x is EvaluationResults {
    return (
      typeof x === "object" &&
      x != null &&
      "results" in x &&
      Array.isArray(x.results) &&
      x.results.length > 0
    );
  }

  private coerceEvaluationResults(
    results: Record<string, any> | EvaluationResults,
    sourceRunId: string
  ): EvaluationResult | EvaluationResults {
    if (this.isEvaluationResults(results)) {
      return {
        results: results.results.map((r) =>
          this.coerceEvaluationResult(r, sourceRunId, false)
        ),
      };
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
    allowNoKey = false
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
  ): Promise<EvaluationResult | EvaluationResults> {
    let sourceRunId = uuidv4();
    const metadata: Record<string, any> = {
      targetRunId: run.id,
    };
    if ("session_id" in run) {
      metadata["experiment"] = run.session_id;
    }

    if (typeof this.func !== "function") {
      throw new Error("Target must be runnable function");
    }

    const wrappedTraceableFunc: TraceableFunction<Func> = traceable<Func>(
      this.func,
      {
        project_name: "evaluators",
        name: "evaluator",
        on_end: (runTree) => {
          // If tracing with OTEL, setting run id manually does not work.
          // Instead get it at the end of the run.
          sourceRunId = runTree.id;
        },
        ...options,
      }
    );

    const result = await wrappedTraceableFunc(
      // Pass data via `langSmithRunAndExample` key to avoid conflicts with other
      // inputs. This key is extracted in the wrapped function, with `run` and
      // `example` passed to evaluator function as arguments.
      { langSmithRunAndExample: { run, example } },
      { metadata }
    );

    // Check the one required property of EvaluationResult since 'instanceof' is not possible
    if ("key" in result) {
      if (!result.sourceRunId) {
        result.sourceRunId = sourceRunId;
      }
      return result as EvaluationResult;
    }
    if (Array.isArray(result)) {
      return {
        results: result.map((r) =>
          this.coerceEvaluationResult(r, sourceRunId, false)
        ),
      };
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
