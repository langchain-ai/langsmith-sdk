// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as InsightsAPI from './insights';
import {
  CreateRunClusteringJobRequest,
  InsightCreateParams,
  InsightCreateResponse,
  InsightDeleteParams,
  InsightDeleteResponse,
  InsightListParams,
  InsightListResponse,
  InsightListResponsesOffsetPaginationInsightsClusteringJobs,
  InsightRetrieveJobParams,
  InsightRetrieveJobResponse,
  InsightRetrieveRunsParams,
  InsightRetrieveRunsResponse,
  InsightUpdateParams,
  InsightUpdateResponse,
  Insights,
} from './insights';
import { APIPromise } from '../../core/api-promise';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Sessions extends APIResource {
  insights: InsightsAPI.Insights = new InsightsAPI.Insights(this._client);

  /**
   * Create a new session.
   */
  create(
    params: SessionCreateParams,
    options?: RequestOptions,
  ): APIPromise<TracerSessionWithoutVirtualFields> {
    const { upsert, ...body } = params;
    return this._client.post('/api/v1/sessions', { query: { upsert }, body, ...options });
  }

  /**
   * Get a specific session.
   */
  retrieve(
    sessionID: string,
    params: SessionRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<TracerSession> {
    const { accept, ...query } = params ?? {};
    return this._client.get(path`/api/v1/sessions/${sessionID}`, {
      query,
      ...options,
      headers: buildHeaders([{ ...(accept != null ? { accept: accept } : undefined) }, options?.headers]),
    });
  }

  /**
   * Update a session.
   */
  update(
    sessionID: string,
    body: SessionUpdateParams,
    options?: RequestOptions,
  ): APIPromise<TracerSessionWithoutVirtualFields> {
    return this._client.patch(path`/api/v1/sessions/${sessionID}`, { body, ...options });
  }

  /**
   * Get all sessions.
   */
  list(
    params: SessionListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<TracerSessionsOffsetPaginationTopLevelArray, TracerSession> {
    const { accept, ...query } = params ?? {};
    return this._client.getAPIList('/api/v1/sessions', OffsetPaginationTopLevelArray<TracerSession>, {
      query,
      ...options,
      headers: buildHeaders([{ ...(accept != null ? { accept: accept } : undefined) }, options?.headers]),
    });
  }

  /**
   * Delete a specific session.
   */
  delete(sessionID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/sessions/${sessionID}`, options);
  }

  /**
   * Get a prebuilt dashboard for a tracing project.
   */
  dashboard(
    sessionID: string,
    params: SessionDashboardParams,
    options?: RequestOptions,
  ): APIPromise<CustomChartsSection> {
    const { accept, ...body } = params;
    return this._client.post(path`/api/v1/sessions/${sessionID}/dashboard`, {
      body,
      ...options,
      headers: buildHeaders([{ ...(accept != null ? { accept: accept } : undefined) }, options?.headers]),
    });
  }
}

export type TracerSessionsOffsetPaginationTopLevelArray = OffsetPaginationTopLevelArray<TracerSession>;

export interface CustomChartsSection {
  id: string;

  charts: Array<CustomChartsSection.Chart>;

  title: string;

  description?: string | null;

  index?: number | null;

  session_id?: string | null;

  sub_sections?: Array<CustomChartsSection.SubSection> | null;
}

export namespace CustomChartsSection {
  export interface Chart {
    id: string;

    /**
     * Enum for custom chart types.
     */
    chart_type: 'line' | 'bar' | 'table' | 'kpi' | 'top-k' | 'pie';

    data: Array<Chart.Data>;

    index: number;

    series: Array<Chart.Series>;

    title: string;

    common_filters?: Chart.CommonFilters | null;

    description?: string | null;

    metadata?: { [key: string]: unknown } | null;
  }

  export namespace Chart {
    export interface Data {
      series_id: string;

      timestamp: string;

      value: number | { [key: string]: unknown } | null;

      group?: string | null;
    }

    export interface Series {
      id: string;

      name: string;

      feedback_key?: string | null;

      filter_definition?: Series.CustomChartFilterByTracingProject | Series.CustomChartFilterByDataset | null;

      filters?: Series.Filters | null;

      /**
       * Include additional information about where the group_by param was set.
       */
      group_by?: Series.GroupBy | null;

      group_by_definitions?: Array<Series.CustomChartGroupByPlain | Series.CustomChartGroupByComplex> | null;

      /**
       * Metrics you can chart. Feedback metrics are not available for
       * organization-scoped charts.
       */
      metric?:
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
        | 'feedback'
        | 'feedback_score_avg'
        | 'feedback_values'
        | 'total_cost'
        | 'prompt_cost'
        | 'completion_cost'
        | 'error_rate'
        | 'streaming_rate'
        | 'cost_p50'
        | 'cost_p99'
        | null;

      metric_definition?:
        | Series.CustomChartMetricCount
        | Series.CustomChartMetricScalar
        | Series.CustomChartMetricPercentile
        | Series.CustomChartMetricRatioOutput
        | null;

      /**
       * LGP Metrics you can chart.
       */
      project_metric?:
        | 'memory_usage'
        | 'cpu_usage'
        | 'disk_usage'
        | 'restart_count'
        | 'replica_count'
        | 'worker_count'
        | 'lg_run_count'
        | 'responses_per_second'
        | 'error_responses_per_second'
        | 'p95_latency'
        | null;

      workspace_id?: string | null;
    }

    export namespace Series {
      export interface CustomChartFilterByTracingProject {
        project_ids: Array<string>;

        source_type: 'tracing_project';

        run_filter?: string | null;

        trace_filter?: string | null;

        tree_filter?: string | null;
      }

      export interface CustomChartFilterByDataset {
        dataset_ids: Array<string>;

        source_type: 'dataset';
      }

      export interface Filters {
        filter?: string | null;

        session?: Array<string> | null;

        trace_filter?: string | null;

        tree_filter?: string | null;
      }

      /**
       * Include additional information about where the group_by param was set.
       */
      export interface GroupBy {
        attribute: 'name' | 'run_type' | 'tag' | 'metadata';

        max_groups?: number;

        path?: string | null;

        set_by?: 'section' | 'series' | null;
      }

      export interface CustomChartGroupByPlain {
        attribute: 'name' | 'run_type' | 'tag' | 'project' | 'status';
      }

      export interface CustomChartGroupByComplex {
        attribute: 'metadata' | 'feedback_label';

        path: string;
      }

      export interface CustomChartMetricCount {
        filter?: string | null;

        type?: 'count';
      }

      export interface CustomChartMetricScalar {
        field:
          | 'latency_seconds'
          | 'first_token_seconds'
          | 'total_tokens'
          | 'prompt_tokens'
          | 'completion_tokens'
          | 'total_cost'
          | 'prompt_cost'
          | 'completion_cost';

        type: 'sum' | 'max' | 'min' | 'avg';

        filter?: string | null;
      }

      export interface CustomChartMetricPercentile {
        field:
          | 'latency_seconds'
          | 'first_token_seconds'
          | 'total_tokens'
          | 'prompt_tokens'
          | 'completion_tokens'
          | 'total_cost'
          | 'prompt_cost'
          | 'completion_cost';

        params: CustomChartMetricPercentile.Params;

        type: 'percentile';

        filter?: string | null;
      }

      export namespace CustomChartMetricPercentile {
        export interface Params {
          p: number;
        }
      }

      export interface CustomChartMetricRatioOutput {
        denominator:
          | CustomChartMetricRatioOutput.CustomChartMetricCount
          | CustomChartMetricRatioOutput.CustomChartMetricScalar
          | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

        numerator:
          | CustomChartMetricRatioOutput.CustomChartMetricCount
          | CustomChartMetricRatioOutput.CustomChartMetricScalar
          | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

        type: 'ratio';
      }

      export namespace CustomChartMetricRatioOutput {
        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          params: CustomChartMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartMetricPercentile {
          export interface Params {
            p: number;
          }
        }

        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          params: CustomChartMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartMetricPercentile {
          export interface Params {
            p: number;
          }
        }
      }
    }

    export interface CommonFilters {
      filter?: string | null;

      session?: Array<string> | null;

      trace_filter?: string | null;

      tree_filter?: string | null;
    }
  }

  export interface SubSection {
    id: string;

    charts: Array<SubSection.Chart>;

    index: number;

    title: string;

    description?: string | null;
  }

  export namespace SubSection {
    export interface Chart {
      id: string;

      /**
       * Enum for custom chart types.
       */
      chart_type: 'line' | 'bar' | 'table' | 'kpi' | 'top-k' | 'pie';

      data: Array<Chart.Data>;

      index: number;

      series: Array<Chart.Series>;

      title: string;

      common_filters?: Chart.CommonFilters | null;

      description?: string | null;

      metadata?: { [key: string]: unknown } | null;
    }

    export namespace Chart {
      export interface Data {
        series_id: string;

        timestamp: string;

        value: number | { [key: string]: unknown } | null;

        group?: string | null;
      }

      export interface Series {
        id: string;

        name: string;

        feedback_key?: string | null;

        filter_definition?:
          | Series.CustomChartFilterByTracingProject
          | Series.CustomChartFilterByDataset
          | null;

        filters?: Series.Filters | null;

        /**
         * Include additional information about where the group_by param was set.
         */
        group_by?: Series.GroupBy | null;

        group_by_definitions?: Array<
          Series.CustomChartGroupByPlain | Series.CustomChartGroupByComplex
        > | null;

        /**
         * Metrics you can chart. Feedback metrics are not available for
         * organization-scoped charts.
         */
        metric?:
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
          | 'feedback'
          | 'feedback_score_avg'
          | 'feedback_values'
          | 'total_cost'
          | 'prompt_cost'
          | 'completion_cost'
          | 'error_rate'
          | 'streaming_rate'
          | 'cost_p50'
          | 'cost_p99'
          | null;

        metric_definition?:
          | Series.CustomChartMetricCount
          | Series.CustomChartMetricScalar
          | Series.CustomChartMetricPercentile
          | Series.CustomChartMetricRatioOutput
          | null;

        /**
         * LGP Metrics you can chart.
         */
        project_metric?:
          | 'memory_usage'
          | 'cpu_usage'
          | 'disk_usage'
          | 'restart_count'
          | 'replica_count'
          | 'worker_count'
          | 'lg_run_count'
          | 'responses_per_second'
          | 'error_responses_per_second'
          | 'p95_latency'
          | null;

        workspace_id?: string | null;
      }

      export namespace Series {
        export interface CustomChartFilterByTracingProject {
          project_ids: Array<string>;

          source_type: 'tracing_project';

          run_filter?: string | null;

          trace_filter?: string | null;

          tree_filter?: string | null;
        }

        export interface CustomChartFilterByDataset {
          dataset_ids: Array<string>;

          source_type: 'dataset';
        }

        export interface Filters {
          filter?: string | null;

          session?: Array<string> | null;

          trace_filter?: string | null;

          tree_filter?: string | null;
        }

        /**
         * Include additional information about where the group_by param was set.
         */
        export interface GroupBy {
          attribute: 'name' | 'run_type' | 'tag' | 'metadata';

          max_groups?: number;

          path?: string | null;

          set_by?: 'section' | 'series' | null;
        }

        export interface CustomChartGroupByPlain {
          attribute: 'name' | 'run_type' | 'tag' | 'project' | 'status';
        }

        export interface CustomChartGroupByComplex {
          attribute: 'metadata' | 'feedback_label';

          path: string;
        }

        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost';

          params: CustomChartMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartMetricPercentile {
          export interface Params {
            p: number;
          }
        }

        export interface CustomChartMetricRatioOutput {
          denominator:
            | CustomChartMetricRatioOutput.CustomChartMetricCount
            | CustomChartMetricRatioOutput.CustomChartMetricScalar
            | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

          numerator:
            | CustomChartMetricRatioOutput.CustomChartMetricCount
            | CustomChartMetricRatioOutput.CustomChartMetricScalar
            | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

          type: 'ratio';
        }

        export namespace CustomChartMetricRatioOutput {
          export interface CustomChartMetricCount {
            filter?: string | null;

            type?: 'count';
          }

          export interface CustomChartMetricScalar {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost';

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export interface CustomChartMetricPercentile {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost';

            params: CustomChartMetricPercentile.Params;

            type: 'percentile';

            filter?: string | null;
          }

          export namespace CustomChartMetricPercentile {
            export interface Params {
              p: number;
            }
          }

          export interface CustomChartMetricCount {
            filter?: string | null;

            type?: 'count';
          }

          export interface CustomChartMetricScalar {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost';

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export interface CustomChartMetricPercentile {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost';

            params: CustomChartMetricPercentile.Params;

            type: 'percentile';

            filter?: string | null;
          }

          export namespace CustomChartMetricPercentile {
            export interface Params {
              p: number;
            }
          }
        }
      }

      export interface CommonFilters {
        filter?: string | null;

        session?: Array<string> | null;

        trace_filter?: string | null;

        tree_filter?: string | null;
      }
    }
  }
}

export interface CustomChartsSectionRequest {
  end_time?: string | null;

  /**
   * Group by param for run stats.
   */
  group_by?: RunStatsGroupBy | null;

  omit_data?: boolean;

  start_time?: string | null;

  /**
   * Timedelta input.
   */
  stride?: TimedeltaInput;

  timezone?: string;
}

/**
 * Group by param for run stats.
 */
export interface RunStatsGroupBy {
  attribute: 'name' | 'run_type' | 'tag' | 'metadata';

  max_groups?: number;

  path?: string | null;
}

export type SessionSortableColumns =
  | 'name'
  | 'start_time'
  | 'last_run_start_time'
  | 'latency_p50'
  | 'latency_p99'
  | 'error_rate'
  | 'feedback'
  | 'runs_count';

/**
 * Timedelta input.
 */
export interface TimedeltaInput {
  days?: number;

  hours?: number;

  minutes?: number;
}

/**
 * TracerSession schema.
 */
export interface TracerSession {
  id: string;

  tenant_id: string;

  completion_cost?: string | null;

  completion_tokens?: number | null;

  default_dataset_id?: string | null;

  description?: string | null;

  end_time?: string | null;

  error_rate?: number | null;

  experiment_progress?: TracerSession.ExperimentProgress | null;

  extra?: { [key: string]: unknown } | null;

  feedback_stats?: { [key: string]: unknown } | null;

  first_token_p50?: number | null;

  first_token_p99?: number | null;

  last_run_start_time?: string | null;

  last_run_start_time_live?: string | null;

  latency_p50?: number | null;

  latency_p99?: number | null;

  name?: string;

  prompt_cost?: string | null;

  prompt_tokens?: number | null;

  reference_dataset_id?: string | null;

  run_count?: number | null;

  run_facets?: Array<{ [key: string]: unknown }> | null;

  session_feedback_stats?: { [key: string]: unknown } | null;

  start_time?: string;

  streaming_rate?: number | null;

  test_run_number?: number | null;

  total_cost?: string | null;

  total_tokens?: number | null;

  trace_tier?: 'longlived' | 'shortlived' | null;
}

export namespace TracerSession {
  export interface ExperimentProgress {
    evaluator_progress: { [key: string]: number };

    expected_run_count: number;

    run_progress: number;
  }
}

/**
 * TracerSession schema.
 */
export interface TracerSessionWithoutVirtualFields {
  id: string;

  tenant_id: string;

  default_dataset_id?: string | null;

  description?: string | null;

  end_time?: string | null;

  extra?: { [key: string]: unknown } | null;

  last_run_start_time_live?: string | null;

  name?: string;

  reference_dataset_id?: string | null;

  start_time?: string;

  trace_tier?: 'longlived' | 'shortlived' | null;
}

export type SessionDeleteResponse = unknown;

export interface SessionCreateParams {
  /**
   * Query param
   */
  upsert?: boolean;

  /**
   * Body param
   */
  id?: string | null;

  /**
   * Body param
   */
  default_dataset_id?: string | null;

  /**
   * Body param
   */
  description?: string | null;

  /**
   * Body param
   */
  end_time?: string | null;

  /**
   * Body param
   */
  evaluator_keys?: Array<string> | null;

  /**
   * Body param
   */
  extra?: { [key: string]: unknown } | null;

  /**
   * Body param
   */
  kicked_off_by?: string | null;

  /**
   * Body param
   */
  name?: string;

  /**
   * Body param
   */
  num_examples?: number | null;

  /**
   * Body param
   */
  num_repetitions?: number | null;

  /**
   * Body param
   */
  reference_dataset_id?: string | null;

  /**
   * Body param
   */
  start_time?: string;

  /**
   * Body param
   */
  tag_value_ids?: Array<string> | null;

  /**
   * Body param
   */
  trace_tier?: 'longlived' | 'shortlived' | null;
}

export interface SessionRetrieveParams {
  /**
   * Query param
   */
  include_stats?: boolean;

  /**
   * Query param
   */
  stats_start_time?: string | null;

  /**
   * Header param
   */
  accept?: string;
}

export interface SessionUpdateParams {
  default_dataset_id?: string | null;

  description?: string | null;

  end_time?: string | null;

  extra?: { [key: string]: unknown } | null;

  name?: string | null;

  trace_tier?: 'longlived' | 'shortlived' | null;
}

export interface SessionListParams extends OffsetPaginationTopLevelArrayParams {
  /**
   * Query param
   */
  id?: Array<string> | null;

  /**
   * Query param
   */
  dataset_version?: string | null;

  /**
   * Query param
   */
  facets?: boolean;

  /**
   * Query param
   */
  filter?: string | null;

  /**
   * Query param
   */
  include_stats?: boolean;

  /**
   * Query param
   */
  metadata?: string | null;

  /**
   * Query param
   */
  name?: string | null;

  /**
   * Query param
   */
  name_contains?: string | null;

  /**
   * Query param
   */
  reference_dataset?: Array<string> | null;

  /**
   * Query param
   */
  reference_free?: boolean | null;

  /**
   * Query param
   */
  sort_by?: SessionSortableColumns;

  /**
   * Query param
   */
  sort_by_desc?: boolean;

  /**
   * Query param
   */
  sort_by_feedback_key?: string | null;

  /**
   * Query param
   */
  sort_by_feedback_source?: 'session' | 'run' | null;

  /**
   * Query param
   */
  stats_filter?: string | null;

  /**
   * Query param
   */
  stats_select?: Array<string> | null;

  /**
   * Query param
   */
  stats_start_time?: string | null;

  /**
   * Query param
   */
  tag_value_id?: Array<string> | null;

  /**
   * Query param
   */
  use_approx_stats?: boolean;

  /**
   * Header param
   */
  accept?: string;
}

export interface SessionDashboardParams {
  /**
   * Body param
   */
  end_time?: string | null;

  /**
   * Body param: Group by param for run stats.
   */
  group_by?: RunStatsGroupBy | null;

  /**
   * Body param
   */
  omit_data?: boolean;

  /**
   * Body param
   */
  start_time?: string | null;

  /**
   * Body param: Timedelta input.
   */
  stride?: TimedeltaInput;

  /**
   * Body param
   */
  timezone?: string;

  /**
   * Header param
   */
  accept?: string;
}

Sessions.Insights = Insights;

export declare namespace Sessions {
  export {
    type CustomChartsSection as CustomChartsSection,
    type CustomChartsSectionRequest as CustomChartsSectionRequest,
    type RunStatsGroupBy as RunStatsGroupBy,
    type SessionSortableColumns as SessionSortableColumns,
    type TimedeltaInput as TimedeltaInput,
    type TracerSession as TracerSession,
    type TracerSessionWithoutVirtualFields as TracerSessionWithoutVirtualFields,
    type SessionDeleteResponse as SessionDeleteResponse,
    type TracerSessionsOffsetPaginationTopLevelArray as TracerSessionsOffsetPaginationTopLevelArray,
    type SessionCreateParams as SessionCreateParams,
    type SessionRetrieveParams as SessionRetrieveParams,
    type SessionUpdateParams as SessionUpdateParams,
    type SessionListParams as SessionListParams,
    type SessionDashboardParams as SessionDashboardParams,
  };

  export {
    Insights as Insights,
    type CreateRunClusteringJobRequest as CreateRunClusteringJobRequest,
    type InsightCreateResponse as InsightCreateResponse,
    type InsightUpdateResponse as InsightUpdateResponse,
    type InsightListResponse as InsightListResponse,
    type InsightDeleteResponse as InsightDeleteResponse,
    type InsightRetrieveJobResponse as InsightRetrieveJobResponse,
    type InsightRetrieveRunsResponse as InsightRetrieveRunsResponse,
    type InsightListResponsesOffsetPaginationInsightsClusteringJobs as InsightListResponsesOffsetPaginationInsightsClusteringJobs,
    type InsightCreateParams as InsightCreateParams,
    type InsightUpdateParams as InsightUpdateParams,
    type InsightListParams as InsightListParams,
    type InsightDeleteParams as InsightDeleteParams,
    type InsightRetrieveJobParams as InsightRetrieveJobParams,
    type InsightRetrieveRunsParams as InsightRetrieveRunsParams,
  };
}
