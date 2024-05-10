import { evaluateComparative, evaluate } from "../evaluation";
import { Client } from "../index";

const TESTING_DATASET_NAME = "test_evaluate_comparative_js";

const client = new Client();

if (!(await client.hasDataset({ datasetName: TESTING_DATASET_NAME }))) {
  await client.createDataset(TESTING_DATASET_NAME, {
    description: "For testing pruposes",
  });

  await client.createExamples({
    inputs: [{ input: 1 }, { input: 2 }],
    outputs: [{ output: 2 }, { output: 3 }],
    datasetName: TESTING_DATASET_NAME,
  });
}

const firstEval = await evaluate((input) => ({ foo: `first:${input.input}` }), {
  data: TESTING_DATASET_NAME,
});

const secondEval = await evaluate(
  (input) => ({ foo: `second:${input.input}` }),
  { data: TESTING_DATASET_NAME }
);

const pairwise = await evaluateComparative(
  [firstEval.experimentName, secondEval.experimentName],
  {
    evaluators: [
      (runs) => ({
        key: "latter_precedence",
        scores: Object.fromEntries(runs.map((run, i) => [run.id, i % 2])),
      }),
    ],
  }
);

console.dir(pairwise, { depth: null });
