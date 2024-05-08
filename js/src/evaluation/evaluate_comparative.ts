import { v4 as uuid4, validate } from "uuid";
import { Client } from "../index.js";
import { ComparisonEvaluationResult, Example, Run } from "../schemas.js";

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

// TODO: handle
export async function evaluateComparative(
  experiments: Array<string>,
  options: {
    evaluators: Array<
      (
        runs: Run[],
        example: Example
      ) => ComparisonEvaluationResult | Promise<ComparisonEvaluationResult>
    >;
    client?: Client;
    metadata?: Record<string, unknown>;
    experimentPrefix?: string;
    description?: string;
    loadNested?: boolean;
  }
): Promise<{ results: ComparisonEvaluationResult[] }> {
  // list all

  if (experiments.length < 2) {
    throw new Error("Comparative evaluation requires at least 2 experiments.");
  }

  if (!options.evaluators.length) {
    throw new Error(
      "At least one evaluator is required for comparative evaluation."
    );
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
  const name = (() => {
    if (!options.experimentPrefix) {
      const names = projects
        .map((p) => p.name)
        .filter(Boolean)
        .join(" vs. ");
      return `${names}-${uuid4().slice(0, 4)}`;
    }

    return `${options.experimentPrefix}-${uuid4().slice(0, 4)}`;
  })();

  const comparativeExperiment = await client.createComparativeExperiment({
    id,
    name,
    experimentIds: projects.map((p) => p.id),
    description: options.description,
    metadata: options.metadata,
    referenceDatasetId: projects.at(0)?.reference_dataset_id,
  });

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

  // TODO: batch only 99 examples at a time
  const exampleMap: Record<string, Example> = {};
  for await (const example of client.listExamples({
    datasetId: referenceDatasetId,
    exampleIds,
    asOf: datasetVersion,
  })) {
    exampleMap[example.id] = example;
  }

  const runMapByExampleId: Record<string, Run[]> = {};
  for (const runs of experimentRuns) {
    for (const run of runs) {
      if (run.reference_example_id == null) continue;
      runMapByExampleId[run.reference_example_id] ??= [];
      runMapByExampleId[run.reference_example_id].push(run);
    }
  }

  const results: ComparisonEvaluationResult[] = [];

  for (const [exampleId, runs] of Object.entries(runMapByExampleId)) {
    const example = exampleMap[exampleId];
    if (!example) {
      console.warn(`Example ${exampleId} not found.`);
      continue;
    }

    for (const evaluator of options.evaluators) {
      const result = await evaluator(runs, example);
      results.push(result);

      for (const [runId, score] of Object.entries(result.scores)) {
        // validate if the run id
        if (!runMapByExampleId[runId]) {
          throw new Error(
            `Returning an invalid run id ${runId} from evaluator.`
          );
        }

        await client.createFeedback(runId, result.key, {
          score,
          sourceRunId: result.source_run_id,
        });
      }
    }
  }

  return { results };
}
