import {
  EvaluationResult,
  EvaluationResults,
  Example,
  Run,
} from "../schemas.js";
import { v4 as uuidv4 } from "uuid";
import { TraceableFunction, traceable } from "../traceable.js";
import { RunTreeConfig } from "../run_trees.js";

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
    ) => Promise<EvaluationResult | EvaluationResults>)
  | ((run: Run, example?: Example) => EvaluationResult | EvaluationResults)
  | ((
      run: Run,
      example: Example
    ) => Promise<EvaluationResult | EvaluationResults>)
  | ((run: Run, example: Example) => EvaluationResult | EvaluationResults)
  | ((args: {
      run: Run;
      example: Example;
      inputs: Record<string, any>;
      outputs: Record<string, any>;
      referenceOutputs?: Record<string, any>;
    }) => EvaluationResult | EvaluationResults)
  | ((args: {
      run: Run;
      example: Example;
      inputs: Record<string, any>;
      outputs: Record<string, any>;
      referenceOutputs?: Record<string, any>;
    }) => Promise<EvaluationResult | EvaluationResults>);

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
    const sourceRunId = uuidv4();
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
        id: sourceRunId,
        ...options,
      }
    );

    const result = (await wrappedTraceableFunc(
      // Pass data via `langSmithRunAndExample` key to avoid conflicts with other
      // inputs. This key is extracted in the wrapped function, with `run` and
      // `example` passed to evaluator function as arguments.
      { langSmithRunAndExample: { run, example } },
      { metadata }
    )) as EvaluationResults | Record<string, any>;

    // Check the one required property of EvaluationResult since 'instanceof' is not possible
    if ("key" in result) {
      if (!result.sourceRunId) {
        result.sourceRunId = sourceRunId;
      }
      return result as EvaluationResult;
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
