export interface TracerSession {
  tenant_id: string;
  id: string;
  start_time: number;
  name?: string;
}

// Fully loaded information about a Tracer Session (also known
// as a Project)
export interface TracerSessionResult extends TracerSession {
  // The number of runs in the session.
  run_count?: number;
  // The median (50th percentile) latency for the session.
  latency_p50?: number;
  // The 99th percentile latency for the session.
  latency_p99?: number;
  // The total number of tokens consumed in the session.
  total_tokens?: number;
  // The total number of prompt tokens consumed in the session.
  prompt_tokens?: number;
  // The total number of completion tokens consumed in the session.
  completion_tokens?: number;
  // The start time of the last run in the session.
  last_run_start_time?: number;
  // Feedback stats for the session.
  feedback_stats?: Record<string, unknown>;
  // The reference dataset IDs this session's runs were generated on.
  reference_dataset_ids?: string[];
  // Facets for the runs in the session.
  run_facets?: KVMap[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type KVMap = Record<string, any>;
// DEPRECATED: Use a raw string instead.
export type RunType =
  | "llm"
  | "chain"
  | "tool"
  | "retriever"
  | "embedding"
  | "prompt"
  | "parser";
export type ScoreType = number | boolean | null;
export type ValueType = number | boolean | string | object | null;
export type DataType = "kv" | "llm" | "chat";

export interface BaseExample {
  dataset_id: string;
  inputs: KVMap;
  outputs?: KVMap;
}

export interface BaseRun {
  id: string;
  name: string;
  serialized?: object;
  inputs: KVMap;
  run_type: string;
  start_time?: number;
  end_time?: number;
  extra?: KVMap;
  error?: string;
  execution_order?: number;
  outputs?: KVMap;
  reference_example_id?: string; // uuid
  parent_run_id?: string; // uuid
  events?: KVMap[];
  tags?: string[];
}

export interface Run extends BaseRun {
  id: string;
  session_id?: string;
  execution_order: number;
  start_time: number;
  child_run_ids?: string[]; // uuid[]
  feedback_stats?: KVMap;
  child_runs?: Run[];
  app_path?: string;
}

export interface RunCreate extends BaseRun {
  child_runs?: this[];
  session_name?: string;
}

export interface RunUpdate {
  end_time?: number;
  extra?: KVMap;
  error?: string;
  inputs?: KVMap;
  outputs?: KVMap;
  parent_run_id?: string;
  reference_example_id?: string;
  events?: KVMap[];
  session_id?: string;
}

export interface ExampleCreate extends BaseExample {
  id?: string;
  created_at: string;
}

export interface Example extends BaseExample {
  id: string;
  created_at: string;
  modified_at: string;
  runs: Run[];
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
  data_type?: DataType;
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
