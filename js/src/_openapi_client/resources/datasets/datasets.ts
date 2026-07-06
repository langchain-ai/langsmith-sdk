// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ExperimentRunsAPI from './experiment-runs.js';
import {
  ExperimentRunQueryParams,
  ExperimentRunQueryResponse,
  ExperimentRunQueryResponsesItemsCursorPostPagination,
  ExperimentRuns,
} from './experiment-runs.js';

export class Datasets extends APIResource {
  experimentRuns: ExperimentRunsAPI.ExperimentRuns = new ExperimentRunsAPI.ExperimentRuns(this._client);
}

/**
 * Enum for dataset data types.
 */
export type DataType = 'kv' | 'llm' | 'chat';

/**
 * Dataset schema.
 */
export interface Dataset {
  id: string;

  modified_at: string;

  name: string;

  session_count: number;

  tenant_id: string;

  baseline_experiment_id?: string | null;

  created_at?: string;

  /**
   * Enum for dataset data types.
   */
  data_type?: DataType | null;

  description?: string | null;

  example_count?: number | null;

  externally_managed?: boolean | null;

  inputs_schema_definition?: { [key: string]: unknown } | null;

  last_session_start_time?: string | null;

  metadata?: { [key: string]: unknown } | null;

  outputs_schema_definition?: { [key: string]: unknown } | null;

  transformations?: Array<DatasetTransformation> | null;
}

export interface DatasetTransformation {
  path: Array<string>;

  /**
   * Enum for dataset transformation types. Ordering determines the order in which
   * transformations are applied if there are multiple transformations on the same
   * path.
   */
  transformation_type:
    | 'convert_to_openai_message'
    | 'convert_to_openai_tool'
    | 'remove_system_messages'
    | 'remove_extra_fields'
    | 'extract_tools_from_run';
}

/**
 * Dataset version schema.
 */
export interface DatasetVersion {
  as_of: string;

  tags?: Array<string> | null;
}

/**
 * Schema used for creating feedback without run id or session id.
 */
export interface FeedbackCreateCoreSchema {
  key: string;

  id?: string;

  comment?: string | null;

  comparative_experiment_id?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  created_at?: string;

  extra?: { [key: string]: unknown } | null;

  feedback_config?: FeedbackCreateCoreSchema.FeedbackConfig | null;

  feedback_group_id?: string | null;

  /**
   * Feedback from the LangChainPlus App.
   */
  feedback_source?:
    | FeedbackCreateCoreSchema.AppFeedbackSource
    | FeedbackCreateCoreSchema.APIFeedbackSource
    | FeedbackCreateCoreSchema.ModelFeedbackSource
    | FeedbackCreateCoreSchema.AutoEvalFeedbackSource
    | null;

  modified_at?: string;

  score?: number | boolean | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackCreateCoreSchema {
  export interface FeedbackConfig {
    /**
     * Enum for feedback types.
     */
    type: 'continuous' | 'categorical' | 'freeform';

    categories?: Array<FeedbackConfig.Category> | null;

    max?: number | null;

    min?: number | null;
  }

  export namespace FeedbackConfig {
    /**
     * Specific value and label pair for feedback
     */
    export interface Category {
      value: number;

      label?: string | null;
    }
  }

  /**
   * Feedback from the LangChainPlus App.
   */
  export interface AppFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'app';
  }

  /**
   * API feedback source.
   */
  export interface APIFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'api';
  }

  /**
   * Model feedback source.
   */
  export interface ModelFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'model';
  }

  /**
   * Auto eval feedback source.
   */
  export interface AutoEvalFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'auto_eval';
  }
}

export interface Missing {
  __missing__: '__missing__';
}

/**
 * Enum for available dataset columns to sort by.
 */
export type SortByDatasetColumn =
  | 'name'
  | 'created_at'
  | 'last_session_start_time'
  | 'example_count'
  | 'session_count'
  | 'modified_at';

Datasets.ExperimentRuns = ExperimentRuns;

export declare namespace Datasets {
  export {
    type DataType as DataType,
    type Dataset as Dataset,
    type DatasetTransformation as DatasetTransformation,
    type DatasetVersion as DatasetVersion,
    type FeedbackCreateCoreSchema as FeedbackCreateCoreSchema,
    type Missing as Missing,
    type SortByDatasetColumn as SortByDatasetColumn,
  };

  export {
    ExperimentRuns as ExperimentRuns,
    type ExperimentRunQueryResponse as ExperimentRunQueryResponse,
    type ExperimentRunQueryResponsesItemsCursorPostPagination as ExperimentRunQueryResponsesItemsCursorPostPagination,
    type ExperimentRunQueryParams as ExperimentRunQueryParams,
  };
}
