import { Client } from "../index.js";
import { Example, KVMap, Run, TracerSession } from "../schemas.js";
import { getGitInfo } from "../utils/_git.js";
import { getLangChainEnvVarsMetadata } from "../utils/env.js";
import { randomName } from "./_random_name.js";
import {
  EvaluationResult,
  EvaluationResults,
  RunEvaluator,
} from "./evaluator.js";
import { v4 as uuidv4 } from "uuid";

type TargetT = (input: Record<string, any>) => Record<string, any>;
// Data format: dataset-name, dataset_id, or examples
type DataT = string | Array<Example>;
// Summary evaluator runs over the whole dataset
// and reports aggregate metric(s)
type SummaryEvaluatorT = (
  runs: Array<Run>,
  examples: Array<Example>
) => EvaluationResult | EvaluationResults;
// Row-level evaluator
type EvaluatorT =
  | RunEvaluator
  | ((run: Run, example?: Example) => EvaluationResult);

export function evaluate(
  /**
   * The target system or function to evaluate.
   */
  target: TargetT,
  /**
   * The dataset to evaluate on. Can be a dataset name, a list of
   * examples, or a generator of examples.
   */
  data: DataT,
  options?: {
    /**
     * A list of evaluators to run on each example.
     * @default undefined
     */
    evaluators?: Array<EvaluatorT>;
    /**
     * A list of summary evaluators to run on the entire dataset.
     * @default undefined
     */
    summaryEvaluator?: Array<SummaryEvaluatorT>;
    /**
     * Metadata to attach to the experiment.
     * @default undefined
     */
    metadata?: Record<string, any>;
    /**
     * A prefix to provide for your experiment name.
     * @default undefined
     */
    experimentPrefix?: string;
    /**
     * The maximum number of concurrent evaluations to run.
     * @default undefined
     */
    maxConcurrency?: number;
    /**
     * The LangSmith client to use.
     * @default undefined
     */
    client?: Client;
    /**
     * Whether to block until the evaluation is complete.
     * @default true
     */
    blocking?: boolean;
  }
): Promise<ExperimentResults>;

interface ExperimentResultRow {
  run: Run;
  example: Example;
  evaluationResults: EvaluationResults;
}

/**
 * Represents the results of an evaluate() call.
 * This class provides an iterator interface to iterate over the experiment results
 * as they become available. It also provides methods to access the experiment name,
 * the number of results, and to wait for the results to be processed.
 */
class ExperimentResults {
  experimentManager: _ExperimentManager;

  constructor(experimentManager: _ExperimentManager) {}
}

const _isCallable = (target: TargetT | Array<Run>): boolean =>
  Boolean(
    typeof target === "function" ||
      ("invoke" in target && typeof target.invoke === "function")
  );

class _ExperimentManagerMixin {
  client: Client;

  _experiment?: TracerSession;

  _experimentName: string;

  _metadata: Record<string, any>;

  get experimentName(): string {
    if (this._experimentName) {
      return this._experimentName;
    } else {
      throw new Error(
        "Experiment name not provided, and experiment not yet started."
      );
    }
  }

  constructor(
    experiment?: TracerSession | string,
    options?: {
      metadata?: Record<string, any>;
      client?: Client;
    }
  ) {
    this.client = options?.client ?? new Client();
    if (!experiment) {
      this._experimentName = randomName();
    } else if (typeof experiment === "string") {
      this._experimentName = `${experiment}-${uuidv4().slice(0, 8)}`;
    } else {
      if (!experiment.name) {
        throw new Error("Experiment must have a name");
      }
      this._experimentName = experiment.name;
      this._experiment = experiment;
    }

    let metadata = options?.metadata || {};
    if (!("revision_id" in metadata)) {
      metadata = {
        revision_id: getLangChainEnvVarsMetadata().revision_id,
        ...metadata,
      };
    }
    this._metadata = metadata;
  }

  _getExperiment(): TracerSession {
    if (!this._experiment) {
      throw new Error("Experiment not yet started.");
    }
    return this._experiment;
  }

  async _getExperimentMetadata(): Promise<Record<string, any>> {
    let projectMetadata = this._metadata ?? {};
    const gitInfo = await getGitInfo();
    if (gitInfo) {
      projectMetadata = {
        ...projectMetadata,
        git: gitInfo,
      };
    }
    if (this._experiment) {
      const experimentMetadata: KVMap =
        this._experiment.extra && "metadata" in this._experiment.extra
          ? this._experiment.extra.metadata
          : {};
      projectMetadata = {
        ...experimentMetadata,
        ...projectMetadata,
      };
    }
    return projectMetadata;
  }

  async _getProject(firstExample: Example): Promise<TracerSession> {
    let project: TracerSession;
    if (!this._experiment) {
      try {
        const projectMetadata = await this._getExperimentMetadata();
        project = await this.client.createProject({
          projectName: this.experimentName,
          referenceDatasetId: firstExample.dataset_id,
          metadata: projectMetadata,
        });
      } catch (e: any) {
        if (String(e).includes("already exists")) {
          throw e;
        }
        throw new Error(
          `Experiment ${this._experimentName} already exists. Please use a different name.`
        );
      }
    } else {
      project = this._experiment;
    }
    return project;
  }

  _printExperimentStart(): void {
    // @TODO log with experiment URL
    console.log(`Starting evaluation of experiment: ${this.experimentName}`);
  }
}

class _ExperimentManager extends _ExperimentManagerMixin {}
