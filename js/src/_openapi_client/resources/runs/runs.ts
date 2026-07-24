// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ShareAPI from './share.js';
import { Share, ShareCreateParams, ShareCreateResponse, ShareDeleteParams } from './share.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  ItemsCursorPostPagination,
  type ItemsCursorPostPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Runs extends APIResource {
  share: ShareAPI.Share = new ShareAPI.Share(this._client);

  /**
   * Returns the URL to view a specific run in the LangSmith UI. The caller must
   * supply the run's project_id and trace_id as query parameters; start_time is
   * optional.
   *
   * @example
   * ```ts
   * const response = await client.runs.getURL(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   *   { project_id: 'project_id', trace_id: 'trace_id' },
   * );
   * ```
   */
  getURL(runID: string, query: RunGetURLParams, options?: RequestOptions): APIPromise<RunGetURLResponse> {
    return this._client.get(path`/v2/runs/${runID}/url`, { query, ...options });
  }

  /**
   * **Alpha:** The request and response contract may change; Returns a paginated
   * list of runs for the given projects within min/max start_time. Supports filters,
   * cursor pagination, and `selects` to select fields to return.
   *
   * @example
   * ```ts
   * // Automatically fetches more pages as needed.
   * for await (const run of client.runs.queryV2()) {
   *   // ...
   * }
   * ```
   */
  queryV2(
    params: RunQueryV2Params,
    options?: RequestOptions,
  ): PagePromise<RunsItemsCursorPostPagination, Run> {
    const { Accept, ...body } = params;
    return this._client.getAPIList('/v2/runs/query', ItemsCursorPostPagination<Run>, {
      body,
      method: 'post',
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }

  /**
   * **Alpha:** The request and response contract may change; Returns one run by ID
   * for the given session. Use the `selects` query parameter (repeatable) to select
   * fields to return.
   *
   * @example
   * ```ts
   * const run = await client.runs.retrieveV2(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   *   { project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e' },
   * );
   * ```
   */
  retrieveV2(runID: string, params: RunRetrieveV2Params, options?: RequestOptions): APIPromise<Run> {
    const { Accept, ...query } = params;
    return this._client.get(path`/v2/runs/${runID}`, {
      query,
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }

  retrieve = this.retrieveV2;

  query = this.queryV2;
}

export type RunsItemsCursorPostPagination = ItemsCursorPostPagination<Run>;

export interface ResponseBodyForRunsGenerateQuery {
  feedback_urls: { [key: string]: string };

  filter: string;
}

export interface Run {
  /**
   * `id` is this run's UUID.
   */
  id?: string;

  /**
   * `app_path` identifies the application code location that produced this run, if
   * recorded.
   */
  app_path?: string;

  /**
   * `attachments` maps each attachment file name to a pre-signed HTTPS download URL.
   */
  attachments?: { [key: string]: string };

  /**
   * `completion_cost` is estimated USD cost for the completion.
   */
  completion_cost?: number;

  /**
   * `completion_cost_details` is the per-category USD breakdown of
   * `completion_cost`. Categories mirror `completion_token_details`. Returned only
   * when the `COMPLETION_COST_DETAILS` field is requested.
   */
  completion_cost_details?: Run.CompletionCostDetails;

  /**
   * `completion_token_details` is the per-category breakdown of `completion_tokens`.
   * Category names are model-specific (for example `reasoning`, `audio`). Returned
   * only when the `COMPLETION_TOKEN_DETAILS` field is requested.
   */
  completion_token_details?: Run.CompletionTokenDetails;

  /**
   * `completion_tokens` is the completion-side token count.
   */
  completion_tokens?: number;

  /**
   * `dotted_order` is the hierarchical ordering key for trace trees.
   */
  dotted_order?: string;

  /**
   * `end_time` is when the run ended (RFC3339 date-time). JSON null if the run has
   * not finished yet.
   */
  end_time?: string;

  /**
   * `error` is the error message when `status` indicates failure.
   */
  error?: string;

  /**
   * `error_preview` is a truncated plain-text error snippet.
   */
  error_preview?: string;

  /**
   * `events` is the ordered list of run events (for example streaming tokens).
   */
  events?: Array<Run.Event>;

  /**
   * `extra` is additional runtime JSON attached to the run.
   */
  extra?: { [key: string]: unknown };

  /**
   * `feedback_stats` aggregates feedback scores keyed by feedback key.
   */
  feedback_stats?: { [key: string]: Run.FeedbackStats };

  /**
   * `first_token_time` is when the first output token was produced (RFC3339
   * date-time), when recorded for streamed runs.
   */
  first_token_time?: string;

  /**
   * `inputs` is the run input payload (arbitrary JSON object).
   */
  inputs?: { [key: string]: unknown };

  /**
   * `inputs_preview` is a truncated plain-text preview of inputs.
   */
  inputs_preview?: string;

  /**
   * `is_in_dataset` is true when this run is linked to a dataset example.
   */
  is_in_dataset?: boolean;

  /**
   * `is_root` is true when this run has no parent (it is the trace root).
   */
  is_root?: boolean;

  /**
   * `last_queued_at` is the most recent time this run was added to an annotation
   * queue.
   */
  last_queued_at?: string;

  /**
   * `latency_seconds` is wall-clock duration from start to end in seconds.
   */
  latency_seconds?: number;

  /**
   * `manifest` is the serialized configuration of the traced component (for example
   * the model parameters, prompt template, or pipeline definition), when recorded.
   */
  manifest?: { [key: string]: unknown };

  /**
   * `metadata` is arbitrary user-defined JSON metadata.
   */
  metadata?: { [key: string]: unknown };

  /**
   * `name` is a human-readable label for the run (for example the model name,
   * function name, or step name chosen when the run was traced).
   */
  name?: string;

  /**
   * `outputs` is the run output payload (arbitrary JSON object).
   */
  outputs?: { [key: string]: unknown };

  /**
   * `outputs_preview` is a truncated plain-text preview of outputs.
   */
  outputs_preview?: string;

  /**
   * `parent_run_ids` lists ancestor run UUIDs from the trace root down to the direct
   * parent.
   */
  parent_run_ids?: Array<string>;

  /**
   * `price_model_id` identifies the pricing model UUID used for cost estimates, when
   * recorded.
   */
  price_model_id?: string;

  /**
   * `project_id` is the tracing project UUID this run was logged to.
   */
  project_id?: string;

  /**
   * `prompt_cost` is estimated USD cost for the prompt.
   */
  prompt_cost?: number;

  /**
   * `prompt_cost_details` is the per-category USD breakdown of `prompt_cost`.
   * Categories mirror `prompt_token_details`. Returned only when the
   * `PROMPT_COST_DETAILS` field is requested.
   */
  prompt_cost_details?: Run.PromptCostDetails;

  /**
   * `prompt_token_details` is the per-category breakdown of `prompt_tokens`.
   * Category names are model-specific (for example `cache_read`, `cache_write`).
   * Returned only when the `PROMPT_TOKEN_DETAILS` field is requested.
   */
  prompt_token_details?: Run.PromptTokenDetails;

  /**
   * `prompt_tokens` is the prompt-side token count.
   */
  prompt_tokens?: number;

  /**
   * `reference_dataset_id` is the dataset UUID for the reference example, if any.
   */
  reference_dataset_id?: string;

  /**
   * `reference_example_id` is the dataset example UUID this run was compared
   * against, if any.
   */
  reference_example_id?: string;

  /**
   * `run_type` identifies what kind of operation this run represents (for example an
   * LLM call, a tool invocation, or a chain step). See the `RunType` enum for
   * allowed values.
   */
  run_type?: RunType;

  /**
   * `share_url` is the fully-qualified URL of this run's public view, rooted at the
   * deployment's LangSmith app origin (for example
   * `https://smith.langchain.com/public/4f7a1b2c-8d9e-4a0b-9c1d-2e3f4a5b6c7d/r`). It
   * is returned only when `SHARE_URL` is included in `selects`, and only when the
   * run has been explicitly shared; the URL remains stable until the run is
   * unshared. Anyone with this URL can view the run anonymously, so treat it as a
   * secret and do not log it.
   */
  share_url?: string;

  /**
   * `start_time` is when the run started (RFC3339 date-time).
   */
  start_time?: string;

  /**
   * `status` is the completion status of the run.
   */
  status?: 'SUCCESS' | 'ERROR' | 'PENDING';

  /**
   * `tags` lists user-defined tags on this run.
   */
  tags?: Array<string>;

  /**
   * `thread_evaluation_time` is thread-level evaluation timing (RFC3339 date-time),
   * when recorded.
   */
  thread_evaluation_time?: string;

  /**
   * `thread_id` is the conversation thread UUID this run belongs to, if any.
   */
  thread_id?: string;

  /**
   * `total_cost` is total estimated USD cost (prompt plus completion).
   */
  total_cost?: number;

  /**
   * `total_tokens` is prompt plus completion tokens.
   */
  total_tokens?: number;

  /**
   * `trace_id` is the root trace UUID; for a root run it matches `id`.
   */
  trace_id?: string;
}

export namespace Run {
  /**
   * `completion_cost_details` is the per-category USD breakdown of
   * `completion_cost`. Categories mirror `completion_token_details`. Returned only
   * when the `COMPLETION_COST_DETAILS` field is requested.
   */
  export interface CompletionCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `completion_token_details` is the per-category breakdown of `completion_tokens`.
   * Category names are model-specific (for example `reasoning`, `audio`). Returned
   * only when the `COMPLETION_TOKEN_DETAILS` field is requested.
   */
  export interface CompletionTokenDetails {
    /**
     * `raw` maps each category name to its completion-token count.
     */
    raw?: { [key: string]: number };
  }

  export interface Event {
    /**
     * `kwargs` is the event payload — an opaque JSON object whose shape depends on
     * `name` and on the emitting SDK. For example LangChain emits `{"token": {...}}`
     * for `new_token` events, tool-call start/end details for tool events, and
     * arbitrary user-defined payloads for custom events. Clients should treat `kwargs`
     * as untyped JSON: do not assume specific keys exist for a given `name`, and
     * tolerate additional unknown keys appearing over time.
     */
    kwargs?: unknown;

    /**
     * `name` is the event kind. Common values emitted by the LangChain/LangSmith
     * tracer SDKs include `"start"`, `"end"`, and `"new_token"`, but applications may
     * emit arbitrary strings for their own instrumentation.
     */
    name?: string;

    /**
     * `time` is when the event occurred (RFC3339 date-time with millisecond
     * precision).
     */
    time?: string;
  }

  export interface FeedbackStats {
    /**
     * `avg` is the arithmetic mean of numeric feedback scores for this key on the run,
     * or `null` when no numeric score has been recorded (for example purely
     * categorical feedback).
     */
    avg?: number;

    /**
     * `comments` is a sample of human-readable comments attached to feedback points
     * for this key, in no particular order. May be empty; is not exhaustive when many
     * comments exist.
     */
    comments?: Array<string>;

    /**
     * `contains_thread_feedback` is true when at least one feedback point for this key
     * was submitted at the thread level (rather than at an individual run). Always
     * false on responses that already describe a single run in isolation.
     */
    contains_thread_feedback?: boolean;

    /**
     * `errors` is the number of feedback points recorded as errors rather than
     * successful scores (for example an automated evaluator that raised an exception).
     * Defaults to 0 when no errors occurred.
     */
    errors?: number;

    /**
     * `max` is the largest numeric feedback score recorded for this key on the run, or
     * `null` when no numeric score has been recorded.
     */
    max?: number;

    /**
     * `min` is the smallest numeric feedback score recorded for this key on the run,
     * or `null` when no numeric score has been recorded.
     */
    min?: number;

    /**
     * `n` is the number of feedback points recorded for this key on the run. For
     * numeric feedback this is the sample size behind `avg`, `min`, `max`, and
     * `stdev`; for categorical feedback it is the sum of the `values` counts.
     */
    n?: number;

    /**
     * `sources` is a sample of feedback sources for this key. Each entry is either a
     * plain string identifier (for example `"api"`, `"app"`, `"model"`) or a JSON
     * object describing a synthetic source (for example
     * `{"type": "__ls_composite_feedback"}` for a computed aggregate). Clients must
     * tolerate both shapes.
     */
    sources?: Array<unknown>;

    /**
     * `stdev` is the sample standard deviation of numeric feedback scores for this key
     * on the run, or `null` when it cannot be computed (for example fewer than two
     * numeric scores, or purely categorical feedback).
     */
    stdev?: number;

    /**
     * `values` is the distribution of categorical feedback labels for this key,
     * mapping each label to its occurrence count. Empty (`{}`) for purely numeric
     * feedback.
     */
    values?: { [key: string]: number };
  }

  /**
   * `prompt_cost_details` is the per-category USD breakdown of `prompt_cost`.
   * Categories mirror `prompt_token_details`. Returned only when the
   * `PROMPT_COST_DETAILS` field is requested.
   */
  export interface PromptCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `prompt_token_details` is the per-category breakdown of `prompt_tokens`.
   * Category names are model-specific (for example `cache_read`, `cache_write`).
   * Returned only when the `PROMPT_TOKEN_DETAILS` field is requested.
   */
  export interface PromptTokenDetails {
    /**
     * `raw` maps each category name to its prompt-token count.
     */
    raw?: { [key: string]: number };
  }
}

export interface RunIngest {
  id?: string;

  dotted_order?: string;

  end_time?: string;

  error?: string;

  events?: Array<{ [key: string]: unknown }>;

  extra?: { [key: string]: unknown };

  input_attachments?: { [key: string]: unknown };

  inputs?: { [key: string]: unknown };

  name?: string;

  output_attachments?: { [key: string]: unknown };

  outputs?: { [key: string]: unknown };

  parent_run_id?: string;

  reference_example_id?: string;

  run_type?: 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

  serialized?: { [key: string]: unknown };

  session_id?: string;

  session_name?: string;

  start_time?: string;

  status?: string;

  tags?: Array<string>;

  trace_id?: string;
}

/**
 * Run schema.
 */
export interface RunSchema {
  id: string;

  app_path: string;

  dotted_order: string;

  name: string;

  /**
   * Enum for run types.
   */
  run_type: RunTypeEnum;

  session_id: string;

  status: string;

  trace_id: string;

  child_run_ids?: Array<string> | null;

  completion_cost?: string | null;

  completion_cost_details?: { [key: string]: string } | null;

  completion_token_details?: { [key: string]: number } | null;

  completion_tokens?: number;

  direct_child_run_ids?: Array<string> | null;

  end_time?: string | null;

  error?: string | null;

  events?: Array<{ [key: string]: unknown }> | null;

  execution_order?: number;

  extra?: { [key: string]: unknown } | null;

  feedback_stats?: { [key: string]: { [key: string]: unknown } } | null;

  first_token_time?: string | null;

  in_dataset?: boolean | null;

  inputs?: { [key: string]: unknown } | null;

  inputs_preview?: string | null;

  inputs_s3_urls?: { [key: string]: unknown } | null;

  last_queued_at?: string | null;

  manifest_id?: string | null;

  manifest_s3_id?: string | null;

  messages?: Array<{ [key: string]: unknown }> | null;

  outputs?: { [key: string]: unknown } | null;

  outputs_preview?: string | null;

  outputs_s3_urls?: { [key: string]: unknown } | null;

  parent_run_id?: string | null;

  parent_run_ids?: Array<string> | null;

  price_model_id?: string | null;

  prompt_cost?: string | null;

  prompt_cost_details?: { [key: string]: string } | null;

  prompt_token_details?: { [key: string]: number } | null;

  prompt_tokens?: number;

  reference_dataset_id?: string | null;

  reference_example_id?: string | null;

  s3_urls?: { [key: string]: unknown } | null;

  serialized?: { [key: string]: unknown } | null;

  share_token?: string | null;

  start_time?: string;

  tags?: Array<string> | null;

  thread_id?: string | null;

  total_cost?: string | null;

  total_tokens?: number;

  trace_first_received_at?: string | null;

  trace_max_start_time?: string | null;

  trace_min_start_time?: string | null;

  trace_tier?: 'longlived' | 'shortlived' | null;

  trace_upgrade?: boolean;

  ttl_seconds?: number | null;
}

export type RunSelectField =
  | 'ID'
  | 'NAME'
  | 'RUN_TYPE'
  | 'STATUS'
  | 'START_TIME'
  | 'END_TIME'
  | 'LATENCY_SECONDS'
  | 'FIRST_TOKEN_TIME'
  | 'ERROR'
  | 'ERROR_PREVIEW'
  | 'EXTRA'
  | 'METADATA'
  | 'EVENTS'
  | 'INPUTS'
  | 'INPUTS_PREVIEW'
  | 'OUTPUTS'
  | 'OUTPUTS_PREVIEW'
  | 'MANIFEST'
  | 'PARENT_RUN_IDS'
  | 'PROJECT_ID'
  | 'TRACE_ID'
  | 'THREAD_ID'
  | 'DOTTED_ORDER'
  | 'IS_ROOT'
  | 'REFERENCE_EXAMPLE_ID'
  | 'REFERENCE_DATASET_ID'
  | 'TOTAL_TOKENS'
  | 'PROMPT_TOKENS'
  | 'COMPLETION_TOKENS'
  | 'TOTAL_COST'
  | 'PROMPT_COST'
  | 'COMPLETION_COST'
  | 'PROMPT_TOKEN_DETAILS'
  | 'COMPLETION_TOKEN_DETAILS'
  | 'PROMPT_COST_DETAILS'
  | 'COMPLETION_COST_DETAILS'
  | 'PRICE_MODEL_ID'
  | 'TAGS'
  | 'APP_PATH'
  | 'ATTACHMENTS'
  | 'THREAD_EVALUATION_TIME'
  | 'IS_IN_DATASET'
  | 'LAST_QUEUED_AT'
  | 'SHARE_URL'
  | 'FEEDBACK_STATS';

/**
 * Query params for run stats.
 */
export interface RunStatsQueryParams {
  id?: Array<string> | null;

  /**
   * Enum for run data source types.
   */
  data_source_type?: RunsFilterDataSourceTypeEnum | null;

  end_time?: string | null;

  error?: boolean | null;

  execution_order?: number | null;

  filter?: string | null;

  /**
   * Group by param for run stats.
   */
  group_by?: RunStatsQueryParams.GroupBy | null;

  groups?: Array<string | null> | null;

  include_details?: boolean;

  is_root?: boolean | null;

  parent_run?: string | null;

  query?: string | null;

  reference_dataset_id?: string | null;

  reference_example?: Array<string> | null;

  /**
   * Enum for run types.
   */
  run_type?: RunTypeEnum | null;

  search_filter?: string | null;

  select?: Array<
    | 'run_count'
    | 'latency_p50'
    | 'latency_p99'
    | 'latency_avg'
    | 'first_token_p50'
    | 'first_token_p99'
    | 'total_tokens'
    | 'prompt_tokens'
    | 'completion_tokens'
    | 'median_tokens'
    | 'completion_tokens_p50'
    | 'prompt_tokens_p50'
    | 'tokens_p99'
    | 'completion_tokens_p99'
    | 'prompt_tokens_p99'
    | 'last_run_start_time'
    | 'feedback_stats'
    | 'thread_feedback_stats'
    | 'run_facets'
    | 'error_rate'
    | 'streaming_rate'
    | 'total_cost'
    | 'prompt_cost'
    | 'completion_cost'
    | 'cost_p50'
    | 'cost_p99'
    | 'session_feedback_stats'
    | 'all_run_stats'
    | 'all_token_stats'
    | 'group_count'
    | 'prompt_token_details'
    | 'completion_token_details'
    | 'prompt_cost_details'
    | 'completion_cost_details'
  > | null;

  session?: Array<string> | null;

  skip_pagination?: boolean | null;

  start_time?: string | null;

  /**
   * Filter runs by trace ID. When set, limit and cursor-based pagination are not
   * applied — all runs in the trace are returned in a single response.
   */
  trace?: string | null;

  trace_filter?: string | null;

  tree_filter?: string | null;

  use_experimental_search?: boolean;
}

export namespace RunStatsQueryParams {
  /**
   * Group by param for run stats.
   */
  export interface GroupBy {
    attribute: 'name' | 'run_type' | 'tag' | 'metadata';

    max_groups?: number;

    path?: string | null;
  }
}

export type RunType = 'TOOL' | 'CHAIN' | 'LLM' | 'RETRIEVER' | 'EMBEDDING' | 'PROMPT' | 'PARSER';

/**
 * Enum for run types.
 */
export type RunTypeEnum = 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

/**
 * Enum for run data source types.
 */
export type RunsFilterDataSourceTypeEnum =
  | 'current'
  | 'historical'
  | 'lite'
  | 'root_lite'
  | 'runs_feedbacks_rmt_wide';

export interface RunGetURLResponse {
  url?: string;
}

export interface RunGetURLParams {
  /**
   * Project (session) UUID
   */
  project_id: string;

  /**
   * Trace UUID
   */
  trace_id: string;

  /**
   * Run start time in RFC3339 format; omit if unknown
   */
  start_time?: string;
}

export interface RunQueryV2Params extends ItemsCursorPostPaginationParams {
  /**
   * Body param: `filter` narrows results to runs matching this LangSmith filter
   * expression, evaluated against each individual run. For example: and(eq(run_type,
   * "llm"), gt(latency, 5)) or eq(status, "error"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * Body param: `has_error` filters to runs that errored (true) or completed without
   * error (false).
   */
  has_error?: boolean;

  /**
   * Body param: `ids` optionally limits the request to these run UUIDs.
   */
  ids?: Array<string>;

  /**
   * Body param: `is_root` returns only root runs (true) or only non-root runs
   * (false).
   */
  is_root?: boolean;

  /**
   * Body param: `max_start_time` is the upper bound for run `start_time` (RFC3339).
   * Defaults to now.
   */
  max_start_time?: string;

  /**
   * Body param: `min_start_time` is the lower bound for run `start_time` (RFC3339).
   * Defaults to 1 day ago.
   */
  min_start_time?: string;

  /**
   * Body param: `project_ids` lists tracing project UUIDs to query. Required unless
   * `reference_dataset_id` is set. Mutually exclusive with `reference_dataset_id` —
   * set exactly one of them.
   */
  project_ids?: Array<string>;

  /**
   * Body param: `reference_dataset_id` resolves session IDs server-side from the
   * dataset. Required unless `project_ids` is set. Mutually exclusive with
   * `project_ids` — set exactly one of them. When provided and `min_start_time` is
   * omitted, the server derives it from the earliest session creation date.
   */
  reference_dataset_id?: string;

  /**
   * Body param: `reference_examples` optionally limits to runs linked to these
   * dataset example UUIDs.
   */
  reference_examples?: Array<string>;

  /**
   * Body param: `run_type`, when set, restricts results to runs whose `run_type`
   * equals this value.
   */
  run_type?: RunType;

  /**
   * Body param: `selects` lists which properties to include on each returned run. If
   * omitted, only `id` is returned. Properties not listed are omitted from each run
   * object.
   */
  selects?: Array<RunSelectField>;

  /**
   * Body param: `trace_filter` narrows results to runs whose root trace matches this
   * LangSmith filter expression. Use this to filter by properties of the trace's
   * root run — for example eq(status, "success") to include only traces that
   * completed without error. See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  trace_filter?: string;

  /**
   * Body param: `trace_id` optionally limits results to runs belonging to this trace
   * UUID.
   */
  trace_id?: string;

  /**
   * Body param: `tree_filter` narrows results to runs that belong to a trace
   * containing at least one run matching this LangSmith filter expression anywhere
   * in the run tree (not just the root). Use this to find runs inside traces that
   * involved a specific tool, tag, or model — for example has(tags, "production") or
   * eq(name, "my_tool"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  tree_filter?: string;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export interface RunRetrieveV2Params {
  /**
   * Query param: `project_id` is the UUID of the tracing project that owns the run.
   */
  project_id: string;

  /**
   * Query param: `selects` lists which properties to include on the returned run
   * (repeatable query parameter). Accepts any value of the `RunSelectField` enum. If
   * omitted, only `id` is returned.
   */
  selects?: Array<
    | 'ID'
    | 'NAME'
    | 'RUN_TYPE'
    | 'STATUS'
    | 'START_TIME'
    | 'END_TIME'
    | 'LATENCY_SECONDS'
    | 'FIRST_TOKEN_TIME'
    | 'ERROR'
    | 'ERROR_PREVIEW'
    | 'EXTRA'
    | 'METADATA'
    | 'EVENTS'
    | 'INPUTS'
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS'
    | 'OUTPUTS_PREVIEW'
    | 'MANIFEST'
    | 'PARENT_RUN_IDS'
    | 'PROJECT_ID'
    | 'TRACE_ID'
    | 'THREAD_ID'
    | 'DOTTED_ORDER'
    | 'IS_ROOT'
    | 'REFERENCE_EXAMPLE_ID'
    | 'REFERENCE_DATASET_ID'
    | 'TOTAL_TOKENS'
    | 'PROMPT_TOKENS'
    | 'COMPLETION_TOKENS'
    | 'TOTAL_COST'
    | 'PROMPT_COST'
    | 'COMPLETION_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'PRICE_MODEL_ID'
    | 'TAGS'
    | 'APP_PATH'
    | 'ATTACHMENTS'
    | 'THREAD_EVALUATION_TIME'
    | 'IS_IN_DATASET'
    | 'LAST_QUEUED_AT'
    | 'SHARE_URL'
    | 'FEEDBACK_STATS'
  >;

  /**
   * Query param: `start_time` is the run's `start_time` (RFC3339 date-time).
   * Providing it speeds up retrieval.
   */
  start_time?: string;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export interface RunRetrieveParams {
  /**
   * Query param: `project_id` is the UUID of the tracing project that owns the run.
   */
  project_id: string;

  /**
   * Query param: `selects` lists which properties to include on the returned run
   * (repeatable query parameter). Accepts any value of the `RunSelectField` enum. If
   * omitted, only `id` is returned.
   */
  selects?: Array<
    | 'ID'
    | 'NAME'
    | 'RUN_TYPE'
    | 'STATUS'
    | 'START_TIME'
    | 'END_TIME'
    | 'LATENCY_SECONDS'
    | 'FIRST_TOKEN_TIME'
    | 'ERROR'
    | 'ERROR_PREVIEW'
    | 'EXTRA'
    | 'METADATA'
    | 'EVENTS'
    | 'INPUTS'
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS'
    | 'OUTPUTS_PREVIEW'
    | 'MANIFEST'
    | 'PARENT_RUN_IDS'
    | 'PROJECT_ID'
    | 'TRACE_ID'
    | 'THREAD_ID'
    | 'DOTTED_ORDER'
    | 'IS_ROOT'
    | 'REFERENCE_EXAMPLE_ID'
    | 'REFERENCE_DATASET_ID'
    | 'TOTAL_TOKENS'
    | 'PROMPT_TOKENS'
    | 'COMPLETION_TOKENS'
    | 'TOTAL_COST'
    | 'PROMPT_COST'
    | 'COMPLETION_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'PRICE_MODEL_ID'
    | 'TAGS'
    | 'APP_PATH'
    | 'ATTACHMENTS'
    | 'THREAD_EVALUATION_TIME'
    | 'IS_IN_DATASET'
    | 'LAST_QUEUED_AT'
    | 'SHARE_URL'
    | 'FEEDBACK_STATS'
  >;

  /**
   * Query param: `start_time` is the run's `start_time` (RFC3339 date-time).
   * Providing it speeds up retrieval.
   */
  start_time?: string;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export interface RunQueryParams extends ItemsCursorPostPaginationParams {
  /**
   * Body param: `filter` narrows results to runs matching this LangSmith filter
   * expression, evaluated against each individual run. For example: and(eq(run_type,
   * "llm"), gt(latency, 5)) or eq(status, "error"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * Body param: `has_error` filters to runs that errored (true) or completed without
   * error (false).
   */
  has_error?: boolean;

  /**
   * Body param: `ids` optionally limits the request to these run UUIDs.
   */
  ids?: Array<string>;

  /**
   * Body param: `is_root` returns only root runs (true) or only non-root runs
   * (false).
   */
  is_root?: boolean;

  /**
   * Body param: `max_start_time` is the upper bound for run `start_time` (RFC3339).
   * Defaults to now.
   */
  max_start_time?: string;

  /**
   * Body param: `min_start_time` is the lower bound for run `start_time` (RFC3339).
   * Defaults to 1 day ago.
   */
  min_start_time?: string;

  /**
   * Body param: `project_ids` lists tracing project UUIDs to query. Required unless
   * `reference_dataset_id` is set. Mutually exclusive with `reference_dataset_id` —
   * set exactly one of them.
   */
  project_ids?: Array<string>;

  /**
   * Body param: `reference_dataset_id` resolves session IDs server-side from the
   * dataset. Required unless `project_ids` is set. Mutually exclusive with
   * `project_ids` — set exactly one of them. When provided and `min_start_time` is
   * omitted, the server derives it from the earliest session creation date.
   */
  reference_dataset_id?: string;

  /**
   * Body param: `reference_examples` optionally limits to runs linked to these
   * dataset example UUIDs.
   */
  reference_examples?: Array<string>;

  /**
   * Body param: `run_type`, when set, restricts results to runs whose `run_type`
   * equals this value.
   */
  run_type?: RunType;

  /**
   * Body param: `selects` lists which properties to include on each returned run. If
   * omitted, only `id` is returned. Properties not listed are omitted from each run
   * object.
   */
  selects?: Array<RunSelectField>;

  /**
   * Body param: `trace_filter` narrows results to runs whose root trace matches this
   * LangSmith filter expression. Use this to filter by properties of the trace's
   * root run — for example eq(status, "success") to include only traces that
   * completed without error. See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  trace_filter?: string;

  /**
   * Body param: `trace_id` optionally limits results to runs belonging to this trace
   * UUID.
   */
  trace_id?: string;

  /**
   * Body param: `tree_filter` narrows results to runs that belong to a trace
   * containing at least one run matching this LangSmith filter expression anywhere
   * in the run tree (not just the root). Use this to find runs inside traces that
   * involved a specific tool, tag, or model — for example has(tags, "production") or
   * eq(name, "my_tool"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  tree_filter?: string;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

Runs.Share = Share;

export declare namespace Runs {
  export {
    type ResponseBodyForRunsGenerateQuery as ResponseBodyForRunsGenerateQuery,
    type Run as Run,
    type RunIngest as RunIngest,
    type RunSchema as RunSchema,
    type RunSelectField as RunSelectField,
    type RunStatsQueryParams as RunStatsQueryParams,
    type RunType as RunType,
    type RunTypeEnum as RunTypeEnum,
    type RunsFilterDataSourceTypeEnum as RunsFilterDataSourceTypeEnum,
    type RunGetURLResponse as RunGetURLResponse,
    type RunsItemsCursorPostPagination as RunsItemsCursorPostPagination,
    type RunGetURLParams as RunGetURLParams,
    type RunQueryV2Params as RunQueryV2Params,
    type RunRetrieveV2Params as RunRetrieveV2Params,
    type RunRetrieveParams as RunRetrieveParams,
    type RunQueryParams as RunQueryParams,
  };

  export {
    Share as Share,
    type ShareCreateResponse as ShareCreateResponse,
    type ShareCreateParams as ShareCreateParams,
    type ShareDeleteParams as ShareDeleteParams,
  };
}
