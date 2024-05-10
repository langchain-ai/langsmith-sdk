import { v4 as uuid4, validate } from "uuid";
import { Client } from "../index.js";
import {
  ComparisonEvaluationResult as ComparisonEvaluationResultRow,
  Example,
  Run,
} from "../schemas.js";
import { shuffle } from "../utils/shuffle.js";
import { AsyncCaller } from "../utils/async_caller.js";

function loadExperiment(client: Client, experiment: string) {
  return client.readProject(
    validate(experiment)
      ? { projectId: experiment }
      : { projectName: experiment }
  );
}

async function loadTraces(
  client: Client,
  experiment: string,
  options: { loadNested: boolean }
) {
  const executionOrder = options.loadNested ? undefined : 1;
  const runs = await client.listRuns(
    validate(experiment)
      ? { projectId: experiment, executionOrder }
      : { projectName: experiment, executionOrder }
  );

  const treeMap: Record<string, Run[]> = {};
  const runIdMap: Record<string, Run> = {};
  const results: Run[] = [];

  for await (const run of runs) {
    if (run.parent_run_id != null) {
      treeMap[run.parent_run_id] ??= [];
      treeMap[run.parent_run_id].push(run);
    } else {
      results.push(run);
    }

    runIdMap[run.id] = run;
  }

  for (const [parentRunId, childRuns] of Object.entries(treeMap)) {
    const parentRun = runIdMap[parentRunId];
    parentRun.child_runs = childRuns.sort((a, b) => {
      if (a.dotted_order == null || b.dotted_order == null) return 0;
      return a.dotted_order.localeCompare(b.dotted_order);
    });
  }

  return results;
}

export interface EvaluateComparativeOptions {
  /**
   * A list of evaluators to use for comparative evaluation.
   */
  evaluators: Array<
    (
      runs: Run[],
      example: Example
    ) => ComparisonEvaluationResultRow | Promise<ComparisonEvaluationResultRow>
  >;
  /**
   * Randomize the order of outputs for each evaluation
   * @default false
   */
  randomizeOrder?: boolean;
  /**
   * The LangSmith client to use.
   * @default undefined
   */
  client?: Client;
  /**
   * Metadata to attach to the experiment.
   * @default undefined
   */
  metadata?: Record<string, unknown>;
  /**
   * A prefix to use for your experiment name.
   * @default undefined
   */
  experimentPrefix?: string;
  /**
   * A free-form description of the experiment.
   * @default undefined
   */
  description?: string;
  /**
   * Whether to load all child runs for the experiment.
   * @default false
   */
  loadNested?: boolean;
  /**
   * The maximum number of concurrent evaluators to run.
   * @default undefined
   */
  maxConcurrency?: number;
}

export interface ComparisonEvaluationResults {
  experimentName: string;
  results: ComparisonEvaluationResultRow[];
}

export async function evaluateComparative(
  experiments: Array<string>,
  options: EvaluateComparativeOptions
): Promise<ComparisonEvaluationResults> {
  if (experiments.length < 2) {
    throw new Error("Comparative evaluation requires at least 2 experiments.");
  }

  if (!options.evaluators.length) {
    throw new Error(
      "At least one evaluator is required for comparative evaluation."
    );
  }

  if (options.maxConcurrency && options.maxConcurrency < 0) {
    throw new Error("maxConcurrency must be a positive number.");
  }

  const client = options.client ?? new Client();

  const projects = await Promise.all(
    experiments.map((experiment) => loadExperiment(client, experiment))
  );

  if (new Set(projects.map((p) => p.reference_dataset_id)).size > 1) {
    throw new Error("All experiments must have the same reference dataset.");
  }

  const referenceDatasetId = projects.at(0)?.reference_dataset_id;
  if (!referenceDatasetId) {
    throw new Error(
      "Reference dataset is required for comparative evaluation."
    );
  }

  if (
    new Set(projects.map((p) => p.extra?.metadata?.dataset_version)).size > 1
  ) {
    console.warn(
      "Detected multiple dataset versions used by experiments, which may lead to inaccurate results."
    );
  }

  const datasetVersion = projects.at(0)?.extra?.metadata?.dataset_version;

  const id = uuid4();
  const experimentName = (() => {
    if (!options.experimentPrefix) {
      const names = projects
        .map((p) => p.name)
        .filter(Boolean)
        .join(" vs. ");
      return `${names}-${uuid4().slice(0, 4)}`;
    }

    return `${options.experimentPrefix}-${uuid4().slice(0, 4)}`;
  })();

  // TODO: add URL to the comparative experiment
  console.log(`Starting pairwise evaluation of: ${experimentName}`);

  const comparativeExperiment = await client.createComparativeExperiment({
    id,
    name: experimentName,
    experimentIds: projects.map((p) => p.id),
    description: options.description,
    metadata: options.metadata,
    referenceDatasetId: projects.at(0)?.reference_dataset_id,
  });

  const viewUrl = await (async () => {
    const projectId = projects.at(0)?.id ?? projects.at(1)?.id;
    const datasetId = comparativeExperiment?.reference_dataset_id;

    if (projectId && datasetId) {
      const hostUrl = (await client.getProjectUrl({ projectId }))
        .split("/projects/p/")
        .at(0);

      const result = new URL(`${hostUrl}/datasets/${datasetId}/compare`);
      result.searchParams.set(
        "selectedSessions",
        projects.map((p) => p.id).join(",")
      );

      result.searchParams.set(
        "comparativeExperiment",
        comparativeExperiment.id
      );
      return result.toString();
    }

    return null;
  })();

  if (viewUrl != null) {
    console.log(`View results at: ${viewUrl}`);
  }

  const experimentRuns = await Promise.all(
    projects.map((p) =>
      loadTraces(client, p.id, { loadNested: !!options.loadNested })
    )
  );

  let exampleIdsIntersect: Set<string> | undefined;
  for (const runs of experimentRuns) {
    const exampleIdsSet = new Set(
      runs
        .map((r) => r.reference_example_id)
        .filter((x): x is string => x != null)
    );

    if (!exampleIdsIntersect) {
      exampleIdsIntersect = exampleIdsSet;
    } else {
      exampleIdsIntersect = new Set(
        [...exampleIdsIntersect].filter((x) => exampleIdsSet.has(x))
      );
    }
  }

  const exampleIds = [...(exampleIdsIntersect ?? [])];
  if (!exampleIds.length) {
    throw new Error("No examples found in common between experiments.");
  }

  const exampleMap: Record<string, Example> = {};
  for (let start = 0; start < exampleIds.length; start += 99) {
    const exampleIdsChunk = exampleIds.slice(start, start + 99);
    for await (const example of client.listExamples({
      datasetId: referenceDatasetId,
      exampleIds: exampleIdsChunk,
      asOf: datasetVersion,
    })) {
      exampleMap[example.id] = example;
    }
  }

  const runMapByExampleId: Record<string, Run[]> = {};
  for (const runs of experimentRuns) {
    for (const run of runs) {
      if (
        run.reference_example_id == null ||
        !exampleIds.includes(run.reference_example_id)
      ) {
        continue;
      }

      runMapByExampleId[run.reference_example_id] ??= [];
      runMapByExampleId[run.reference_example_id].push(run);
    }
  }

  const caller = new AsyncCaller({ maxConcurrency: options.maxConcurrency });

  async function evaluateAndSubmitFeedback(
    runs: Run[],
    example: Example,
    evaluator: (
      runs: Run[],
      example: Example
    ) => ComparisonEvaluationResultRow | Promise<ComparisonEvaluationResultRow>
  ) {
    const expectedRunIds = new Set(runs.map((r) => r.id));
    const result = await evaluator(
      options.randomizeOrder ? shuffle(runs) : runs,
      example
    );

    for (const [runId, score] of Object.entries(result.scores)) {
      // validate if the run id
      if (!expectedRunIds.has(runId)) {
        throw new Error(`Returning an invalid run id ${runId} from evaluator.`);
      }

      await client.createFeedback(runId, result.key, {
        score,
        sourceRunId: result.source_run_id,
        comparativeExperimentId: comparativeExperiment.id,
      });
    }

    return result;
  }

  const promises = Object.entries(runMapByExampleId).flatMap(
    ([exampleId, runs]) => {
      const example = exampleMap[exampleId];
      if (!example) throw new Error(`Example ${exampleId} not found.`);

      return options.evaluators.map((evaluator) =>
        caller.call(
          evaluateAndSubmitFeedback,
          runs,
          exampleMap[exampleId],
          evaluator
        )
      );
    }
  );

  const results: ComparisonEvaluationResultRow[] = await Promise.all(promises);
  return { experimentName, results };
}
