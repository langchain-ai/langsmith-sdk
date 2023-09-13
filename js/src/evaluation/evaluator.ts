import { Example, KVMap, Run, ScoreType, ValueType } from "../schemas.js";

export interface EvaluationResult {
  key: string;
  score?: ScoreType;
  value?: ValueType;
  comment?: string;
  correction?: object;
  evaluatorInfo?: KVMap;
}

export interface RunEvaluator {
  evaluateRun(run: Run, example?: Example): Promise<EvaluationResult>;
}
