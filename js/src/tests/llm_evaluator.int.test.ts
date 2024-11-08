import { expect, test } from "@jest/globals";
import { Client } from "../index.js";
import {
  CategoricalScoreConfig,
  ContinuousScoreConfig,
  LLMEvaluator,
} from "../evaluation/llm_evaluator.js";
import { evaluate } from "../evaluation/_runner.js";

const TESTING_DATASET_NAME = "LLMEvaluator dataset";

test("llm evaluator initialization with categorical config", async () => {
  const evaluator = await LLMEvaluator.create({
    promptTemplate: "Is the response vague? Y/N\n{input}",
    scoreConfig: new CategoricalScoreConfig({
      key: "vagueness",
      choices: ["Y", "N"],
      description: "Whether the response is vague. Y for yes, N for no.",
      reasoningKey: "explanation",
    }),
  });

  expect(evaluator).toBeDefined();
  // Check input variables extracted from template
  expect(evaluator.prompt.inputVariables).toEqual(["input"]);
  // Verify JSON schema for categorical scoring
  expect(evaluator.scoreSchema).toEqual({
    type: "object",
    description: "Whether the response is vague. Y for yes, N for no.",
    title: "vagueness",
    properties: {
      value: {
        type: "string",
        enum: ["Y", "N"],
        description: "The score for the evaluation, one of Y, N.",
      },
      explanation: {
        type: "string",
        description: "First, think step by step to explain your score.",
      },
    },
    required: ["value", "explanation"],
  });

  expect((evaluator.scoreConfig as CategoricalScoreConfig).choices).toEqual([
    "Y",
    "N",
  ]);
});

test("llm evaluator initialization with continuous config", async () => {
  const evaluator = await LLMEvaluator.create({
    promptTemplate: "Rate the response from 0 to 1.\n{input}",
    scoreConfig: new ContinuousScoreConfig({
      key: "rating",
      description: "The rating of the response, from 0 to 1.",
      min: 0,
      max: 1,
    }),
  });

  expect(evaluator).toBeDefined();
  // Check input variables extracted from template
  expect(evaluator.prompt.inputVariables).toEqual(["input"]);
  // Verify JSON schema for continuous scoring
  expect(evaluator.scoreSchema).toEqual({
    type: "object",
    title: "rating",
    description: "The rating of the response, from 0 to 1.",
    properties: {
      score: {
        type: "number",
        minimum: 0,
        maximum: 1,
        description:
          "The score for the evaluation, between 0 and 1, inclusive.",
      },
    },
    required: ["score"],
  });
  // Verify score config properties
  expect(evaluator.scoreConfig.key).toBe("rating");
  expect((evaluator.scoreConfig as ContinuousScoreConfig).min).toBe(0);
  expect((evaluator.scoreConfig as ContinuousScoreConfig).max).toBe(1);
});

test("llm evaluator with custom variable mapping", async () => {
  const evaluator = await LLMEvaluator.create({
    promptTemplate: [
      [
        "system",
        "Is the output accurate with respect to the context and question? Y/N",
      ],
      ["human", "Context: {context}\nQuestion: {question}\nOutput: {output}"],
    ],
    scoreConfig: new CategoricalScoreConfig({
      key: "accuracy",
      choices: ["Y", "N"],
      description:
        "Whether the output is accurate with respect to the context and question.",
      reasoningKey: "explanation",
      reasoningDescription: "First, think step by step to explain your score.",
    }),
    mapVariables: (run: any, example?: any) => ({
      context: example?.inputs?.context || "",
      question: example?.inputs?.question || "",
      output: run.outputs?.output || "",
    }),
  });

  expect(evaluator).toBeDefined();
});

test("llm evaluator can evaluate runs", async () => {
  const client = new Client();
  await client.clonePublicDataset(
    "https://beta.smith.langchain.com/public/06785303-0f70-4466-b637-f23d38c0f28e/d",
    {
      datasetName: TESTING_DATASET_NAME,
    }
  );
  const evaluator = await LLMEvaluator.create({
    promptTemplate: "Is the response vague? Y/N\n{response}",
    scoreConfig: new CategoricalScoreConfig({
      key: "vagueness",
      choices: ["Y", "N"],
      description: "Whether the response is vague. Y for yes, N for no.",
      reasoningKey: "explanation",
      reasoningDescription: "First, think step by step to explain your score.",
    }),
    mapVariables: (run: any, _example?: any) => ({
      response: run.outputs?.["output"] ?? "",
    }),
  });

  const targetFunc = (input: Record<string, any>) => {
    return { output: input.question + " This is a test response" };
  };

  const evalRes = await evaluate(targetFunc, {
    data: TESTING_DATASET_NAME,
    evaluators: [evaluator],
    description: "LLM evaluator test run",
  });

  expect(evalRes.results).toHaveLength(10);
  const firstResult = evalRes.results[0];

  const evaluation = firstResult.evaluationResults.results[0];
  expect(evaluation.key).toBe("vagueness");
  expect(["Y", "N"]).toContain(evaluation.value);
  expect(evaluation.comment).toBeDefined();

  await client.deleteDataset({ datasetName: TESTING_DATASET_NAME });
});

test("llm evaluator with multiple prompt messages", async () => {
  const evaluator = await LLMEvaluator.create({
    promptTemplate: [
      ["system", "You are a helpful assistant evaluating responses."],
      ["human", "Rate this response from 0 to 1: {response}"],
    ],
    scoreConfig: new ContinuousScoreConfig({
      key: "rating",
      description: "Quality rating from 0 to 1",
      min: 0,
      max: 1,
    }),
    mapVariables: (run: any, _example?: any) => ({
      response: run.outputs?.["output"] ?? "",
    }),
  });

  expect(evaluator).toBeDefined();
});
