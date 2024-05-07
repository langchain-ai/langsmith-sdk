import { v4 as uuid4, validate } from "uuid";
import { Client } from "../index.js";
import { ComparisonEvaluationResult, Example, Run } from "../schemas.js";
import { EvaluationResult, EvaluationResults } from "./evaluator.js";

function loadExperiment(client: Client, experimentIdOrName: string) {
  if (validate(experimentIdOrName)) {
    return client.readProject({ projectId: experimentIdOrName });
  }
  return client.readProject({ projectName: experimentIdOrName });
}

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
    maxConcurrency?: number;
  }
) {
  // list all

  if (experiments.length < 2) {
    throw new Error("Comparative evaluation requires at least 2 experiments.");
  }

  if (!options.evaluators.length) {
    throw new Error(
      "At least one evaluator is required for comparative evaluation."
    );
  }

  if (options.maxConcurrency && options.maxConcurrency < 0) {
    throw new Error("maxConcurrency must be a positive integer");
  }

  const client = options.client ?? new Client();

  const projects = await Promise.all(
    experiments.map((experiment) => loadExperiment(client, experiment))
  );

  if (new Set(projects.map((p) => p.reference_dataset_id)).size > 1) {
    throw new Error("All experiments must have the same reference dataset.");
  }

  const id = uuid4();

  const comparativeExperiment = await client.createComparativeExperiment({
    experimentName: "lol",
    id,
    experiments: projects.map((p) => p.id),
    description: options.description,
    metadata: options.metadata,
  });


}
