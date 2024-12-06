import { Example, Run, ScoreType, ValueType } from "../schemas.js";
import { EvaluationResult, RunEvaluator } from "./evaluator.js";

export interface GradingFunctionResult {
  key?: string;
  score?: ScoreType;
  value?: ValueType;
  comment?: string;
  correction?: Record<string, unknown>;
}

export interface GradingFunctionParams {
  input: string;
  prediction: string;
  answer?: string;
}

export interface StringEvaluatorParams {
  evaluationName?: string;
  inputKey?: string;
  predictionKey?: string;
  answerKey?: string;
  gradingFunction: (
    params: GradingFunctionParams
  ) => Promise<GradingFunctionResult>;
}

export class StringEvaluator implements RunEvaluator {
  protected evaluationName?: string;
  protected inputKey: string;
  protected predictionKey: string;
  protected answerKey?: string;
  protected gradingFunction: (
    params: GradingFunctionParams
  ) => Promise<GradingFunctionResult>;

  constructor(params: StringEvaluatorParams) {
    this.evaluationName = params.evaluationName;
    this.inputKey = params.inputKey ?? "input";
    this.predictionKey = params.predictionKey ?? "output";
    this.answerKey =
      params.answerKey !== undefined ? params.answerKey : "output";
    this.gradingFunction = params.gradingFunction;
  }

  async evaluateRun(run: Run, example?: Example): Promise<EvaluationResult> {
    if (!run.outputs) {
      throw new Error("Run outputs cannot be undefined.");
    }
    const functionInputs = {
      input: run.inputs[this.inputKey],
      prediction: run.outputs[this.predictionKey],
      answer: this.answerKey ? example?.outputs?.[this.answerKey] : null,
    };

    const gradingResults = await this.gradingFunction(functionInputs);
    const key = gradingResults.key || this.evaluationName;
    if (!key) {
      throw new Error("Evaluation name cannot be undefined.");
    }
    return {
      key,
      score: gradingResults.score,
      value: gradingResults.value,
      comment: gradingResults.comment,
      correction: gradingResults.correction,
    };
  }
}
