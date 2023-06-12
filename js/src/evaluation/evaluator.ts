import { Example, KVMap, RunResult, ScoreType, ValueType } from "../schemas.js";

export interface EvaluationResult {
  key: string;
  score?: ScoreType;
  value?: ValueType;
  comment?: string;
  correction?: string | object;
  evaluatorInfo?: KVMap;
}

export interface RunEvaluator {
  evaluateRun(run: RunResult, example?: Example): Promise<EvaluationResult>;
}
