import { evaluate } from "../evaluation/_runner.js";
import {
  evaluateComparative,
  _ComparativeEvaluator,
} from "../evaluation/evaluate_comparative.js";
import { Client } from "../index.js";
import { Run } from "../schemas.js";
import { waitUntilRunFound } from "./utils.js";
import { v4 as uuidv4 } from "uuid";

const TESTING_DATASET_NAME = `test_evaluate_comparative_js_${uuidv4()}`;

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
    const client = new Client();

    const firstEval = await evaluate(
      (input) => ({ foo: `first:${input.input}` }),
      { data: TESTING_DATASET_NAME }
    );

    const secondEval = await evaluate(
      (input) => ({ foo: `second:${input.input}` }),
      { data: TESTING_DATASET_NAME }
    );

    await Promise.all(
      [firstEval, secondEval].flatMap(({ results }) =>
        results.flatMap(({ run }) => waitUntilRunFound(client, run.id))
      )
    );

    const pairwise = await evaluateComparative(
      [firstEval.experimentName, secondEval.experimentName],
      {
        evaluators: [
          ({ runs }: { runs?: Run[] }) => ({
            key: "latter_precedence",
            scores: Object.fromEntries(
              runs?.map((run, i) => [run.id, i % 2]) ?? []
            ),
          }),
        ],
      }
    );

    expect(pairwise.results.length).toEqual(2);
  });

  test("pass directly", async () => {
    const pairwise = await evaluateComparative(
      [
        evaluate((input) => ({ foo: `first:${input.input}` }), {
          data: TESTING_DATASET_NAME,
        }),
        evaluate((input) => ({ foo: `second:${input.input}` }), {
          data: TESTING_DATASET_NAME,
        }),
      ],
      {
        evaluators: [
          ({ runs }: { runs?: Run[] }) => ({
            key: "latter_precedence",
            scores: Object.fromEntries(
              runs?.map((run, i) => [run.id, i % 2]) ?? []
            ),
          }),
        ],
      }
    );

    expect(pairwise.results.length).toEqual(2);
  });

  describe("evaluator formats", () => {
    test("old format evaluator", async () => {
      const pairwise = await evaluateComparative(
        [
          evaluate((input) => ({ foo: `first:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
          evaluate((input) => ({ foo: `second:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
        ],
        {
          evaluators: [
            // Old format evaluator
            (runs, example) => ({
              key: "old_format",
              scores: Object.fromEntries(
                runs.map((run) => [
                  run.id,
                  run.outputs?.foo === `second:${example.inputs.input}` ? 1 : 0,
                ])
              ),
            }),
          ],
        }
      );

      expect(pairwise.results.length).toEqual(2);
      expect(pairwise.results[0].key).toBe("old_format");
      // Second run in each pair should have score of 1
      expect(Object.values(pairwise.results[0].scores)).toEqual([0, 1]);
    });

    test("new format evaluator", async () => {
      const matchesSecondEvaluator: _ComparativeEvaluator = ({
        runs,
        inputs,
        outputs,
      }: {
        runs?: Run[];
        inputs?: Record<string, any>;
        outputs?: Record<string, any>[];
      }) => ({
        key: "new_format",
        scores: Object.fromEntries(
          // Add null checks for the optional parameters
          runs?.map((run, i) => [
            run.id,
            outputs?.[i]?.foo === `second:${inputs?.input}` ? 1 : 0,
          ]) ?? []
        ),
      });

      const pairwise = await evaluateComparative(
        [
          evaluate((input) => ({ foo: `first:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
          evaluate((input) => ({ foo: `second:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
        ],
        {
          evaluators: [matchesSecondEvaluator],
        }
      );

      expect(pairwise.results.length).toEqual(2);
      expect(pairwise.results[0].key).toBe("new_format");
      // Second run in each pair should have score of 1
      expect(Object.values(pairwise.results[0].scores)).toEqual([0, 1]);
    });

    test("mixed old and new format evaluators", async () => {
      const matchesSecondEvaluator: _ComparativeEvaluator = ({
        runs,
        inputs,
        outputs,
      }: {
        runs?: Run[];
        inputs?: Record<string, any>;
        outputs?: Record<string, any>[];
      }) => ({
        key: "new_format",
        scores: Object.fromEntries(
          runs?.map((run, i) => [
            run.id,
            outputs?.[i]?.foo === `second:${inputs?.input}` ? 1 : 0,
          ]) ?? []
        ),
      });
      const pairwise = await evaluateComparative(
        [
          evaluate((input) => ({ foo: `first:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
          evaluate((input) => ({ foo: `second:${input.input}` }), {
            data: TESTING_DATASET_NAME,
          }),
        ],
        {
          evaluators: [
            // Old format
            (runs, example) => ({
              key: "old_format",
              scores: Object.fromEntries(
                runs.map((run) => [
                  run.id,
                  run.outputs?.foo === `second:${example.inputs.input}` ? 1 : 0,
                ])
              ),
            }),
            // New format
            matchesSecondEvaluator,
          ],
        }
      );

      expect(pairwise.results.length).toEqual(4); // 2 examples × 2 evaluators
      expect(pairwise.results.map((r) => r.key)).toContain("old_format");
      expect(pairwise.results.map((r) => r.key)).toContain("new_format");
      // Each evaluator should score the second run as 1
      pairwise.results.forEach((result) => {
        expect(Object.values(result.scores)).toEqual([0, 1]);
      });
    });
  });
});
