import { Example, Run, ScoreType, ValueType } from "../schemas.js";

export interface EvaluationResult {
  key: string;
  score?: ScoreType;
  value?: ValueType;
  comment?: string;
  correction?: string | object;
}

export interface RunEvaluator {
  evaluateRun(run: Run, example?: Example): Promise<EvaluationResult>;
}
