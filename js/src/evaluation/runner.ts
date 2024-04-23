import { Client } from "../index.js";
import { Example, KVMap, Run, TracerSession } from "../schemas.js";
import { traceable } from "../traceable.js";
import { getGitInfo } from "../utils/_git.js";
import { isUUIDv4 } from "../utils/_uuid.js";
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
type DataT = string | AsyncIterable<Example>;
// Summary evaluator runs over the whole dataset
// and reports aggregate metric(s)
type SummaryEvaluatorT = (
  runs: Array<Run>,
  examples: Array<Example>
) => Promise<EvaluationResult | EvaluationResults>;
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

  constructor(args: {
    experiment?: TracerSession | string;
    metadata?: Record<string, any>;
    client?: Client;
  }) {
    this.client = args.client ?? new Client();
    if (!args.experiment) {
      this._experimentName = randomName();
    } else if (typeof args.experiment === "string") {
      this._experimentName = `${args.experiment}-${uuidv4().slice(0, 8)}`;
    } else {
      if (!args.experiment.name) {
        throw new Error("Experiment must have a name");
      }
      this._experimentName = args.experiment.name;
      this._experiment = args.experiment;
    }

    let metadata = args.metadata || {};
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

interface _ForwardResults {
  run: Run;
  example: Example;
}

interface _ExperimentManagerArgs {
  data: DataT;
  experiment?: TracerSession | string;
  metadata?: Record<string, any>;
  client?: Client;
  runs?: AsyncIterable<Run>;
  evaluationResults?: AsyncIterable<EvaluationResults>;
  summaryResults?: AsyncIterable<EvaluationResults>;
}

/**
 * Manage the execution of experiments.
 *
 * Supports lazily running predictions and evaluations in parallel to facilitate
 * result streaming and early debugging.
 */
class _ExperimentManager extends _ExperimentManagerMixin {
  _data: DataT;

  _examples?: AsyncIterable<Example>;

  _runs?: AsyncIterable<Run>;

  _evaluationResults?: AsyncIterable<EvaluationResults>;

  _summaryResults?: AsyncIterable<EvaluationResults>;

  constructor(args: _ExperimentManagerArgs) {
    super({
      experiment: args.experiment,
      metadata: args.metadata,
      client: args.client,
    });
    this._data = args.data;
    this._runs = args.runs;
    this._evaluationResults = args.evaluationResults;
    this._summaryResults = args.summaryResults;
  }

  get examples(): AsyncIterable<Example> {
    if (this._examples === undefined) {
      this._examples = _resolveData(this._data, { client: this.client });
    }
    return async function* (this: _ExperimentManager) {
      for await (const example of this._examples!) {
        yield example;
      }
    }.call(this);
  }

  get datasetId(): Promise<string> {
    if (!this._experiment || !this._experiment.reference_dataset_id) {
      const examplesIterator = this.examples[Symbol.asyncIterator]();
      return examplesIterator.next().then((result) => {
        if (result.done) {
          throw new Error("No examples found in the dataset.");
        }
        return result.value.dataset_id;
      });
    }
    return Promise.resolve(this._experiment.reference_dataset_id);
  }

  get evaluationResults(): AsyncIterable<EvaluationResults> {
    if (this._evaluationResults === undefined) {
      return async function* (this: _ExperimentManager) {
        for await (const _ of this.examples) {
          yield { results: [] };
        }
      }.call(this);
    }
    return this._evaluationResults;
  }

  get runs(): AsyncIterable<Run> {
    if (this._runs === undefined) {
      throw new Error(
        "Runs not provided in this experiment. Please predict first."
      );
    }
    return async function* (this: _ExperimentManager) {
      for await (const run of this._runs!) {
        yield run;
      }
    }.call(this);
  }

  async start(): Promise<_ExperimentManager> {
    const examplesIterator = this.examples[Symbol.asyncIterator]();
    const firstExample = (await examplesIterator.next()).value;
    const project = await this._getProject(firstExample);
    this._printExperimentStart();
    return new _ExperimentManager({
      data: this.examples,
      experiment: project,
      metadata: this._metadata,
      client: this.client,
      runs: this._runs,
      evaluationResults: this._evaluationResults,
      summaryResults: this._summaryResults,
    });
  }

  async withPredictions(
    target: TargetT,
    maxConcurrency?: number
  ): Promise<_ExperimentManager> {
    const context = copyContext();
    const experimentResults = context.run(
      this._predict,
      target,
      maxConcurrency
    );

    const results: AsyncIterable<any>[] = [];
    for await (const item of asyncTee(experimentResults, 2)) {
      results.push(item);
    }
    const [r1, r2] = results;

    return new _ExperimentManager({
      data: (async function* (): AsyncIterable<Example> {
        for await (const pred of r1) {
          yield pred.example;
        }
      })(),
      experiment: this._experiment,
      metadata: this._metadata,
      client: this.client,
      runs: (async function* (): AsyncIterable<Run> {
        for await (const pred of r2) {
          yield pred.run;
        }
      })(),
    });
  }

  async withEvaluators(
    evaluators: Array<EvaluatorT | RunEvaluator>,
    maxConcurrency?: number
  ): Promise<_ExperimentManager> {
    evaluators = resolveEvaluators(evaluators);
    const context = copyContext();
    const experimentResults = context.run(
      this._score,
      evaluators,
      maxConcurrency
    );

    const results: AsyncIterable<any>[] = [];
    for await (const item of asyncTee(experimentResults, 3)) {
      results.push(item);
    }
    const [r1, r2, r3] = results;

    return new _ExperimentManager({
      data: (async function* (): AsyncIterable<Example> {
        for await (const result of r1) {
          yield result.example;
        }
      })(),
      experiment: this._experiment,
      metadata: this._metadata,
      client: this.client,
      runs: (async function* (): AsyncIterable<Run> {
        for await (const result of r2) {
          yield result.run;
        }
      })(),
      evaluationResults: (async function* (): AsyncIterable<EvaluationResults> {
        for await (const result of r3) {
          yield result.evaluationResults;
        }
      })(),
      summaryResults: this._summaryResults,
    });
  }

  async withSummaryEvaluators(
    summaryEvaluators: Array<SummaryEvaluatorT>
  ): Promise<_ExperimentManager> {
    const wrappedEvaluators = await wrapSummaryEvaluators(summaryEvaluators);
    const context = copyContext();
    const aggregateFeedbackGen = context.run(
      this._applySummaryEvaluators,
      wrappedEvaluators
    );
    return new _ExperimentManager({
      data: this.examples,
      experiment: this._experiment,
      metadata: this._metadata,
      client: this.client,
      runs: this.runs,
      evaluationResults: this._evaluationResults,
      summaryResults: aggregateFeedbackGen,
    });
  }

  async *getResults(): AsyncIterable<ExperimentResultRow> {
    const runsIter = this.runs[Symbol.asyncIterator]();
    const examplesIter = this.examples[Symbol.asyncIterator]();
    const evaluationResultsIter =
      this.evaluationResults[Symbol.asyncIterator]();

    while (true) {
      const runResult = await runsIter.next();
      const exampleResult = await examplesIter.next();
      const evaluationResult = await evaluationResultsIter.next();

      if (runResult.done || exampleResult.done || evaluationResult.done) {
        break;
      }

      yield {
        run: runResult.value,
        example: exampleResult.value,
        evaluationResults: evaluationResult.value,
      };
    }
  }

  // Private methods

  _predict(
    target: TargetT,
    options?: {
      maxConcurrency?: number;
    }
  ): AsyncGenerator<_ForwardResults> {
    throw new Error("Not implemented");
  }

  _runEvaluators(
    evaluators: Array<RunEvaluator>,
    currentResults: ExperimentResultRow
  ): ExperimentResultRow {
    throw new Error("Not implemented");
  }

  _score(
    evaluators: Array<RunEvaluator>,
    maxConcurrency?: number
  ): AsyncIterable<ExperimentResultRow> {
    throw new Error("Not implemented");
  }

  _applySummaryEvaluators(
    summaryEvaluators: Array<SummaryEvaluatorT>
  ): AsyncGenerator<EvaluationResults> {
    throw new Error("Not implemented");
  }

  async _getDatasetVersion(): Promise<string | undefined> {
    const examples: Example[] = [];
    for await (const example of this.examples) {
      examples.push(example);
    }

    const modifiedAt = examples.map((ex) => ex.modified_at);

    const maxModifiedAt =
      modifiedAt.length > 0
        ? new Date(
            Math.max(...modifiedAt.map((date) => new Date(date).getTime()))
          )
        : undefined;

    return maxModifiedAt?.toISOString();
  }

  async _end(): Promise<void> {
    const experiment = this._experiment;
    if (!experiment) {
      throw new Error("Experiment not yet started.");
    }
    const projectMetadata = await this._getExperimentMetadata();
    projectMetadata["dataset_version"] = this._getDatasetVersion();
    this.client.updateProject(experiment.id, {
      endTime: new Date().toISOString(),
      metadata: projectMetadata,
    });
  }
}

function _resolveData(
  data: DataT,
  options: {
    client: Client;
  }
): AsyncIterable<Example> {
  if (typeof data === "string" && isUUIDv4(data)) {
    return options.client.listExamples({ datasetId: data });
  }
  if (typeof data === "string") {
    return options.client.listExamples({ datasetName: data });
  }
  return data;
}

async function wrapSummaryEvaluators(
  evaluators: SummaryEvaluatorT[]
): Promise<SummaryEvaluatorT[]> {
  async function wrap(
    evaluator: SummaryEvaluatorT
  ): Promise<SummaryEvaluatorT> {
    const evalName = evaluator.name || "BatchEvaluator";

    const wrapperInner = (
      runs: Run[],
      examples: Example[]
    ): Promise<EvaluationResult | EvaluationResults> => {
      const wrapperSuperInner = traceable(
        (
          _runs_: string,
          _examples_: string
        ): Promise<EvaluationResult | EvaluationResults> => {
          return evaluator(runs, examples);
        },
        { name: evalName }
      );

      return Promise.resolve(
        wrapperSuperInner(
          `Runs[] (Length=${runs.length})`,
          `Examples[] (Length=${examples.length})`
        )
      );
    };

    return wrapperInner;
  }

  const results: SummaryEvaluatorT[] = [];
  for (const evaluator of evaluators) {
    results.push(await wrap(evaluator));
  }
  return results;
}

async function* asyncTee<T>(
  iterable: AsyncIterable<T>,
  n: number = 2
): AsyncGenerator<AsyncIterable<T>, void, undefined> {
  const iterators: Array<AsyncIterable<T>> = [];
  const cache: T[][] = Array.from({ length: n }, () => []);

  const iterator = iterable[Symbol.asyncIterator]();

  async function* createIterator(
    index: number
  ): AsyncGenerator<T, void, unknown> {
    let item: IteratorResult<T>;
    let i = 0;

    while (i < cache[index].length) {
      yield cache[index][i];
      i++;
    }

    while (!(item = await iterator.next()).done) {
      cache.forEach((arr) => arr.push(item.value));
      yield item.value;
    }
  }

  for (let i = 0; i < n; i++) {
    iterators.push(createIterator(i));
  }

  yield* iterators;
}
