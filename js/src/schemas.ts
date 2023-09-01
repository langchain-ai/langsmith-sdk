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

/**
 * A run can represent either a trace (root run)
 * or a child run (~span).
 */
export interface BaseRun {
  /** Optionally, a unique identifier for the run. */
  id?: string;

  /** A human-readable name for the run. */
  name: string;

  /** The epoch time at which the run started, if available. */
  start_time?: number;

  /** Specifies the type of run (tool, chain, llm, etc.). */
  run_type: string;

  /** The epoch time at which the run ended, if applicable. */
  end_time?: number;

  /** Any additional metadata or settings for the run. */
  extra?: KVMap;

  /** Error message, captured if the run faces any issues. */
  error?: string;

  /** Serialized state of the run for potential future use. */
  serialized?: object;

  /** Events like 'start', 'end' linked to the run. */
  events?: KVMap[];

  /** Inputs that were used to initiate the run. */
  inputs: KVMap;

  /** Outputs produced by the run, if any. */
  outputs?: KVMap;

  /** ID of an example that might be related to this run. */
  reference_example_id?: string;

  /** ID of a parent run, if this run is part of a larger operation. */
  parent_run_id?: string;

  /** Tags for further categorizing or annotating the run. */
  tags?: string[];
}

/**
 * Describes properties of a run when loaded from the database.
 * Extends the BaseRun interface.
 */
export interface Run extends BaseRun {
  /** A unique identifier for the run, mandatory when loaded from DB. */
  id: string;

  /** Defines the sequence in which the run was executed. */
  execution_order: number;

  /** The ID of the project that owns this run. */
  session_id?: string;

  /** IDs of any child runs spawned by this run. */
  child_run_ids?: string[];

  /** Child runs, loaded explicitly via a heavier query. */
  child_runs?: Run[];

  /** Stats capturing feedback for this run. */
  feedback_stats?: KVMap;

  /** The URL path where this run is accessible within the app. */
  app_path?: string;

  /** The manifest ID that correlates with this run. */
  manifest_id?: string;

  /** The current status of the run, such as 'success'. */
  status?: string;

  /** Number of tokens used in the prompt. */
  prompt_tokens?: number;

  /** Number of tokens generated in the completion. */
  completion_tokens?: number;

  /** Total token count, combining prompt and completion. */
  total_tokens?: number;

  /** Time when the first token was processed. */
  first_token_time?: number;

  /** IDs of parent runs, if multiple exist. */
  parent_run_ids?: string[];
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
