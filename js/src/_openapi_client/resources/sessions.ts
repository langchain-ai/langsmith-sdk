// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { RequestOptions } from '../internal/request-options.js';

export class Sessions extends APIResource {
  /**
   * **Beta:** This endpoint is in active development and may change without notice.
   * Returns the tracing project (session) an address names. An address is an AGENT
   * (`id` and `environment`), an EXPERIMENT (`id`), or an EVALUATOR (no `id`:
   * evaluator traces share one project per workspace). Send `kind` and `environment`
   * in upper case, as listed; they are matched case-insensitively, while the Agent
   * `id` is case-sensitive. An address that does not exist, or whose project you
   * cannot read, is a 404. Pass the returned `session_id` to any endpoint that takes
   * a project (session) ID. This is not supported on a BYOC data plane yet, and is a
   * 501 there.
   */
  resolve(query: SessionResolveParams, options?: RequestOptions): APIPromise<SessionResolveResponse> {
    return this._client.get('/api/v1/sessions/resolutions', { query, ...options });
  }
}

export interface CustomChartsSection {
  id: string;

  charts: Array<
    CustomChartsSection.SingleCustomChartResponseSerialized | CustomChartsSection.CustomTextBlock
  >;

  title: string;

  description?: string | null;

  index?: number | null;

  layout?: CustomChartsSection.Layout | null;

  session_id?: string | null;

  sub_sections?: Array<CustomChartsSection.SubSection> | null;
}

export namespace CustomChartsSection {
  export interface SingleCustomChartResponseSerialized {
    id: string;

    chart_type: 'line' | 'bar' | 'table' | 'kpi' | 'top-k' | 'pie';

    data: Array<SingleCustomChartResponseSerialized.Data>;

    index: number;

    series: Array<SingleCustomChartResponseSerialized.Series>;

    title: string;

    common_filters?: SingleCustomChartResponseSerialized.CommonFilters | null;

    description?: string | null;

    metadata?: { [key: string]: unknown } | null;
  }

  export namespace SingleCustomChartResponseSerialized {
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

      metadata?: { [key: string]: unknown } | null;

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
        | Series.CustomChartFeedbackCountMetric
        | Series.CustomChartMetricCount
        | Series.CustomChartFeedbackScoreMetricScalar
        | Series.CustomChartMetricScalar
        | Series.CustomChartFeedbackScoreMetricPercentile
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
        | 'run_queue_wait_time'
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

      export interface CustomChartFeedbackCountMetric {
        entity: 'feedback';

        params: CustomChartFeedbackCountMetric.Params;

        filter?: string | null;

        type?: 'count';
      }

      export namespace CustomChartFeedbackCountMetric {
        export interface Params {
          feedback_key: string;
        }
      }

      export interface CustomChartMetricCount {
        filter?: string | null;

        type?: 'count';
      }

      export interface CustomChartFeedbackScoreMetricScalar {
        field: 'feedback_score';

        params: CustomChartFeedbackScoreMetricScalar.Params;

        type: 'sum' | 'max' | 'min' | 'avg';

        filter?: string | null;
      }

      export namespace CustomChartFeedbackScoreMetricScalar {
        export interface Params {
          feedback_key: string;
        }
      }

      export interface CustomChartMetricScalar {
        field:
          | 'latency_seconds'
          | 'first_token_seconds'
          | 'total_tokens'
          | 'prompt_tokens'
          | 'completion_tokens'
          | 'prompt_token_details.cache_creation'
          | 'prompt_token_details.cache_read'
          | 'prompt_token_details.ephemeral_1h_input_tokens'
          | 'prompt_token_details.ephemeral_5m_input_tokens'
          | 'prompt_token_details.audio'
          | 'prompt_token_details.image'
          | 'prompt_token_details.video'
          | 'completion_token_details.reasoning'
          | 'completion_token_details.audio'
          | 'completion_token_details.image'
          | 'completion_token_details.video'
          | 'total_cost'
          | 'prompt_cost'
          | 'completion_cost'
          | 'feedback_score';

        type: 'sum' | 'max' | 'min' | 'avg';

        filter?: string | null;
      }

      export interface CustomChartFeedbackScoreMetricPercentile {
        field: 'feedback_score';

        params: CustomChartFeedbackScoreMetricPercentile.Params;

        type: 'percentile';

        filter?: string | null;
      }

      export namespace CustomChartFeedbackScoreMetricPercentile {
        export interface Params {
          feedback_key: string;

          p: number;
        }
      }

      export interface CustomChartMetricPercentile {
        field:
          | 'latency_seconds'
          | 'first_token_seconds'
          | 'total_tokens'
          | 'prompt_tokens'
          | 'completion_tokens'
          | 'prompt_token_details.cache_creation'
          | 'prompt_token_details.cache_read'
          | 'prompt_token_details.ephemeral_1h_input_tokens'
          | 'prompt_token_details.ephemeral_5m_input_tokens'
          | 'prompt_token_details.audio'
          | 'prompt_token_details.image'
          | 'prompt_token_details.video'
          | 'completion_token_details.reasoning'
          | 'completion_token_details.audio'
          | 'completion_token_details.image'
          | 'completion_token_details.video'
          | 'total_cost'
          | 'prompt_cost'
          | 'completion_cost'
          | 'feedback_score';

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
          | CustomChartMetricRatioOutput.CustomChartFeedbackCountMetric
          | CustomChartMetricRatioOutput.CustomChartMetricCount
          | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricScalar
          | CustomChartMetricRatioOutput.CustomChartMetricScalar
          | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricPercentile
          | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

        numerator:
          | CustomChartMetricRatioOutput.CustomChartFeedbackCountMetric
          | CustomChartMetricRatioOutput.CustomChartMetricCount
          | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricScalar
          | CustomChartMetricRatioOutput.CustomChartMetricScalar
          | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricPercentile
          | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

        type: 'ratio';
      }

      export namespace CustomChartMetricRatioOutput {
        export interface CustomChartFeedbackCountMetric {
          entity: 'feedback';

          params: CustomChartFeedbackCountMetric.Params;

          filter?: string | null;

          type?: 'count';
        }

        export namespace CustomChartFeedbackCountMetric {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartFeedbackScoreMetricScalar {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricScalar.Params;

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricScalar {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartFeedbackScoreMetricPercentile {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricPercentile {
          export interface Params {
            feedback_key: string;

            p: number;
          }
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

          params: CustomChartMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartMetricPercentile {
          export interface Params {
            p: number;
          }
        }

        export interface CustomChartFeedbackCountMetric {
          entity: 'feedback';

          params: CustomChartFeedbackCountMetric.Params;

          filter?: string | null;

          type?: 'count';
        }

        export namespace CustomChartFeedbackCountMetric {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartFeedbackScoreMetricScalar {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricScalar.Params;

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricScalar {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartFeedbackScoreMetricPercentile {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricPercentile {
          export interface Params {
            feedback_key: string;

            p: number;
          }
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

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

  export interface CustomTextBlock {
    id: string;

    chart_type: 'text';

    index: number;

    markdown: string;

    metadata?: { [key: string]: unknown } | null;
  }

  export interface Layout {
    breakpoints: Layout.Breakpoints;

    version: 1;
  }

  export namespace Layout {
    export interface Breakpoints {
      md: Breakpoints.Md;

      sm: Breakpoints.Sm;
    }

    export namespace Breakpoints {
      export interface Md {
        rows: Array<Md.Row>;
      }

      export namespace Md {
        export interface Row {
          height_units: number;

          items: Array<Row.Item>;
        }

        export namespace Row {
          export interface Item {
            chart_id: string;

            width_units: number;
          }
        }
      }

      export interface Sm {
        rows: Array<Sm.Row>;
      }

      export namespace Sm {
        export interface Row {
          height_units: number;

          items: Array<Row.Item>;
        }

        export namespace Row {
          export interface Item {
            chart_id: string;

            width_units: number;
          }
        }
      }
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

        metadata?: { [key: string]: unknown } | null;

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
          | Series.CustomChartFeedbackCountMetric
          | Series.CustomChartMetricCount
          | Series.CustomChartFeedbackScoreMetricScalar
          | Series.CustomChartMetricScalar
          | Series.CustomChartFeedbackScoreMetricPercentile
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
          | 'run_queue_wait_time'
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

        export interface CustomChartFeedbackCountMetric {
          entity: 'feedback';

          params: CustomChartFeedbackCountMetric.Params;

          filter?: string | null;

          type?: 'count';
        }

        export namespace CustomChartFeedbackCountMetric {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricCount {
          filter?: string | null;

          type?: 'count';
        }

        export interface CustomChartFeedbackScoreMetricScalar {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricScalar.Params;

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricScalar {
          export interface Params {
            feedback_key: string;
          }
        }

        export interface CustomChartMetricScalar {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

          type: 'sum' | 'max' | 'min' | 'avg';

          filter?: string | null;
        }

        export interface CustomChartFeedbackScoreMetricPercentile {
          field: 'feedback_score';

          params: CustomChartFeedbackScoreMetricPercentile.Params;

          type: 'percentile';

          filter?: string | null;
        }

        export namespace CustomChartFeedbackScoreMetricPercentile {
          export interface Params {
            feedback_key: string;

            p: number;
          }
        }

        export interface CustomChartMetricPercentile {
          field:
            | 'latency_seconds'
            | 'first_token_seconds'
            | 'total_tokens'
            | 'prompt_tokens'
            | 'completion_tokens'
            | 'prompt_token_details.cache_creation'
            | 'prompt_token_details.cache_read'
            | 'prompt_token_details.ephemeral_1h_input_tokens'
            | 'prompt_token_details.ephemeral_5m_input_tokens'
            | 'prompt_token_details.audio'
            | 'prompt_token_details.image'
            | 'prompt_token_details.video'
            | 'completion_token_details.reasoning'
            | 'completion_token_details.audio'
            | 'completion_token_details.image'
            | 'completion_token_details.video'
            | 'total_cost'
            | 'prompt_cost'
            | 'completion_cost'
            | 'feedback_score';

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
            | CustomChartMetricRatioOutput.CustomChartFeedbackCountMetric
            | CustomChartMetricRatioOutput.CustomChartMetricCount
            | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricScalar
            | CustomChartMetricRatioOutput.CustomChartMetricScalar
            | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricPercentile
            | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

          numerator:
            | CustomChartMetricRatioOutput.CustomChartFeedbackCountMetric
            | CustomChartMetricRatioOutput.CustomChartMetricCount
            | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricScalar
            | CustomChartMetricRatioOutput.CustomChartMetricScalar
            | CustomChartMetricRatioOutput.CustomChartFeedbackScoreMetricPercentile
            | CustomChartMetricRatioOutput.CustomChartMetricPercentile;

          type: 'ratio';
        }

        export namespace CustomChartMetricRatioOutput {
          export interface CustomChartFeedbackCountMetric {
            entity: 'feedback';

            params: CustomChartFeedbackCountMetric.Params;

            filter?: string | null;

            type?: 'count';
          }

          export namespace CustomChartFeedbackCountMetric {
            export interface Params {
              feedback_key: string;
            }
          }

          export interface CustomChartMetricCount {
            filter?: string | null;

            type?: 'count';
          }

          export interface CustomChartFeedbackScoreMetricScalar {
            field: 'feedback_score';

            params: CustomChartFeedbackScoreMetricScalar.Params;

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export namespace CustomChartFeedbackScoreMetricScalar {
            export interface Params {
              feedback_key: string;
            }
          }

          export interface CustomChartMetricScalar {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'prompt_token_details.cache_creation'
              | 'prompt_token_details.cache_read'
              | 'prompt_token_details.ephemeral_1h_input_tokens'
              | 'prompt_token_details.ephemeral_5m_input_tokens'
              | 'prompt_token_details.audio'
              | 'prompt_token_details.image'
              | 'prompt_token_details.video'
              | 'completion_token_details.reasoning'
              | 'completion_token_details.audio'
              | 'completion_token_details.image'
              | 'completion_token_details.video'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost'
              | 'feedback_score';

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export interface CustomChartFeedbackScoreMetricPercentile {
            field: 'feedback_score';

            params: CustomChartFeedbackScoreMetricPercentile.Params;

            type: 'percentile';

            filter?: string | null;
          }

          export namespace CustomChartFeedbackScoreMetricPercentile {
            export interface Params {
              feedback_key: string;

              p: number;
            }
          }

          export interface CustomChartMetricPercentile {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'prompt_token_details.cache_creation'
              | 'prompt_token_details.cache_read'
              | 'prompt_token_details.ephemeral_1h_input_tokens'
              | 'prompt_token_details.ephemeral_5m_input_tokens'
              | 'prompt_token_details.audio'
              | 'prompt_token_details.image'
              | 'prompt_token_details.video'
              | 'completion_token_details.reasoning'
              | 'completion_token_details.audio'
              | 'completion_token_details.image'
              | 'completion_token_details.video'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost'
              | 'feedback_score';

            params: CustomChartMetricPercentile.Params;

            type: 'percentile';

            filter?: string | null;
          }

          export namespace CustomChartMetricPercentile {
            export interface Params {
              p: number;
            }
          }

          export interface CustomChartFeedbackCountMetric {
            entity: 'feedback';

            params: CustomChartFeedbackCountMetric.Params;

            filter?: string | null;

            type?: 'count';
          }

          export namespace CustomChartFeedbackCountMetric {
            export interface Params {
              feedback_key: string;
            }
          }

          export interface CustomChartMetricCount {
            filter?: string | null;

            type?: 'count';
          }

          export interface CustomChartFeedbackScoreMetricScalar {
            field: 'feedback_score';

            params: CustomChartFeedbackScoreMetricScalar.Params;

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export namespace CustomChartFeedbackScoreMetricScalar {
            export interface Params {
              feedback_key: string;
            }
          }

          export interface CustomChartMetricScalar {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'prompt_token_details.cache_creation'
              | 'prompt_token_details.cache_read'
              | 'prompt_token_details.ephemeral_1h_input_tokens'
              | 'prompt_token_details.ephemeral_5m_input_tokens'
              | 'prompt_token_details.audio'
              | 'prompt_token_details.image'
              | 'prompt_token_details.video'
              | 'completion_token_details.reasoning'
              | 'completion_token_details.audio'
              | 'completion_token_details.image'
              | 'completion_token_details.video'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost'
              | 'feedback_score';

            type: 'sum' | 'max' | 'min' | 'avg';

            filter?: string | null;
          }

          export interface CustomChartFeedbackScoreMetricPercentile {
            field: 'feedback_score';

            params: CustomChartFeedbackScoreMetricPercentile.Params;

            type: 'percentile';

            filter?: string | null;
          }

          export namespace CustomChartFeedbackScoreMetricPercentile {
            export interface Params {
              feedback_key: string;

              p: number;
            }
          }

          export interface CustomChartMetricPercentile {
            field:
              | 'latency_seconds'
              | 'first_token_seconds'
              | 'total_tokens'
              | 'prompt_tokens'
              | 'completion_tokens'
              | 'prompt_token_details.cache_creation'
              | 'prompt_token_details.cache_read'
              | 'prompt_token_details.ephemeral_1h_input_tokens'
              | 'prompt_token_details.ephemeral_5m_input_tokens'
              | 'prompt_token_details.audio'
              | 'prompt_token_details.image'
              | 'prompt_token_details.video'
              | 'completion_token_details.reasoning'
              | 'completion_token_details.audio'
              | 'completion_token_details.image'
              | 'completion_token_details.video'
              | 'total_cost'
              | 'prompt_cost'
              | 'completion_cost'
              | 'feedback_score';

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
  | 'feedback';

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

export interface SessionResolveResponse {
  /**
   * `session_id` is the tracing project (session) the address names.
   */
  session_id: string;
}

export interface SessionResolveParams {
  /**
   * The kind of address.
   */
  kind: 'AGENT' | 'EXPERIMENT' | 'EVALUATOR';

  /**
   * The Agent's user-assigned id for AGENT, or the experiment's id for EXPERIMENT.
   * Not set for EVALUATOR.
   */
  id?: string;

  /**
   * The Agent environment. Only set for AGENT.
   */
  environment?: 'LOCAL' | 'DEVELOPMENT' | 'STAGING' | 'PRODUCTION';
}

export declare namespace Sessions {
  export {
    type CustomChartsSection as CustomChartsSection,
    type CustomChartsSectionRequest as CustomChartsSectionRequest,
    type RunStatsGroupBy as RunStatsGroupBy,
    type SessionSortableColumns as SessionSortableColumns,
    type TimedeltaInput as TimedeltaInput,
    type TracerSession as TracerSession,
    type TracerSessionWithoutVirtualFields as TracerSessionWithoutVirtualFields,
    type SessionResolveResponse as SessionResolveResponse,
    type SessionResolveParams as SessionResolveParams,
  };
}
