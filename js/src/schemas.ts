export interface TracerSession {
  tenant_id: string;
  id: string;
  start_time: number;
  name?: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type KVMap = Record<string, any>;
export type RunType = "llm" | "chain" | "tool";
export type ScoreType = number | boolean | null;
export type ValueType = number | boolean | string | object | null;

export interface BaseExample {
  dataset_id: string;
  inputs: KVMap;
  outputs: KVMap;
}
export interface RunEvent {
  name: string;
  time: number;
  kwargs: KVMap;
}

export interface BaseRun {
  id: string;
  name: string;
  start_time: number;
  end_time: number;
  extra?: KVMap;
  error?: string;
  execution_order: number;
  serialized: object;
  inputs: KVMap;
  outputs?: KVMap;
  reference_example_id?: string; // uuid
  run_type: RunType;
  events: RunEvent[];
}

export interface Run extends BaseRun {
  child_runs: this[];
  child_execution_order: number;
  parent_run_id?: string; // uuid
}

export interface RunCreate extends BaseRun {
  child_runs: this[];
  session_name?: string;
  parent_run_id?: string;
}

export interface RunResult extends BaseRun {
  name: string;
  session_id: string;
  parent_run_id?: string;
}
export interface RunUpdate {
  end_time?: number;
  error?: string;
  outputs?: KVMap;
  parent_run_id?: string;
  reference_example_id?: string;
  events?: RunEvent[];
}
export interface ExampleCreate extends BaseExample {
  id?: string;
  created_at: string;
}

export interface Example extends BaseExample {
  id: string;
  created_at: string;
  modified_at: string;
  runs: RunResult[];
}

export interface ExampleUpdate {
  dataset_id?: string;
  inputs?: KVMap;
  outputs?: KVMap;
}
export interface BaseDataset {
  name: string;
  description: string;
  tenant_id: string;
}

export interface Dataset extends BaseDataset {
  id: string;
  created_at: string;
  modified_at: string;
}

export interface FeedbackSourceBase {
  type: string;
  metadata?: KVMap;
}

export interface APIFeedbackSource extends FeedbackSourceBase {
  type: "api";
}

export interface ModelFeedbackSource extends FeedbackSourceBase {
  type: "model";
}

export interface FeedbackBase {
  created_at: string;
  modified_at: string;
  run_id: string;
  key: string;
  score: ScoreType;
  value: ValueType;
  comment: string | null;
  correction: string | object | null;
  feedback_source: APIFeedbackSource | ModelFeedbackSource | KVMap | null;
}

export interface FeedbackCreate extends FeedbackBase {
  id: string;
}

export interface Feedback extends FeedbackBase {
  id: string;
}
