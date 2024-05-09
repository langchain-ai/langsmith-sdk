import { evaluate } from "../evaluation/_runner.js";
import { evaluateComparative } from "../evaluation/evaluate_comparative.js";
import { Client } from "../index.js";

const TESTING_DATASET_NAME = "test_evaluate_comparative_js";

beforeAll(async () => {
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
});

afterAll(async () => {
  const client = new Client();
  await client.deleteDataset({ datasetName: TESTING_DATASET_NAME });
});

describe("evaluate comparative", () => {
  test("basic", async () => {
    const firstEval = await evaluate(
      (input) => ({ foo: `first:${input.input}` }),
      { data: TESTING_DATASET_NAME }
    );

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

    // TODO: we should a) wait for runs to be persisted, b) allow passing runnables / traceables directly
    expect(pairwise.results.length).toBeGreaterThanOrEqual(1);
  });
});
