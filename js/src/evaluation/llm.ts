// eslint-disable-next-line import/no-extraneous-dependencies
import { ChatPromptTemplate } from "@langchain/core/prompts";
import * as uuid from "uuid";
import {
  EvaluationResult,
  EvaluationResults,
  RunEvaluator,
} from "./evaluator.js";
import type { Run, Example } from "../schemas.js";
// eslint-disable-next-line import/no-extraneous-dependencies
import { BaseChatModel } from "@langchain/core/language_models/chat_models";

/**
 * Configuration for categorical (enum-based) scoring in evaluations.
 * Used to define discrete categories or labels for evaluation results.
 */
export class CategoricalScoreConfig {
  /** Feedback key for the evaluator */
  key: string;
  /** Array of valid categorical choices/labels that can be assigned */
  choices: string[];
  /** Description of what this score measures or represents */
  description: string;
  /** Optional key for the LLM reasoning/explanation for the score */
  reasoningKey?: string;
  /** Optional description of score reasoning, provided to the LLM in the structured output */
  reasoningDescription?: string;

  /**
   * Creates a new categorical score configuration
   * @param params Configuration parameters
   * @param params.key Feedback key for the evaluator
   * @param params.choices Array of valid categorical options
   * @param params.description Description of the scoring criteria
   * @param params.reasoningKey Optional key for the LLM reasoning/explanation for the score
   * @param params.reasoningDescription Optional description of score reasoning, provided to the LLM in the structured output
   */
  constructor(params: {
    key: string;
    choices: string[];
    description: string;
    reasoningKey?: string;
    reasoningDescription?: string;
  }) {
    this.key = params.key;
    this.choices = params.choices;
    this.description = params.description;
    this.reasoningKey = params.reasoningKey;
    this.reasoningDescription = params.reasoningDescription;
  }
}

/**
 * Configuration for continuous (numeric) scoring in evaluations.
 * Used to define scores that fall within a numeric range.
 */
export class ContinuousScoreConfig {
  /** Feedback key for the evaluator */
  key: string;
  /** Minimum allowed score value (defaults to 0) */
  min: number;
  /** Maximum allowed score value (defaults to 1) */
  max: number;
  /** Description of the scoring criteria */
  description: string;
  /** Optional key for the LLM reasoning/explanation for the score */
  reasoningKey?: string;
  /** Optional description of score reasoning, provided to the LLM in the structured output */
  reasoningDescription?: string;

  /**
   * Creates a new continuous score configuration
   * @param params Configuration parameters
   * @param params.key Feedback key for the evaluator
   * @param params.description Description of the scoring criteria
   * @param params.min Optional minimum score value (defaults to 0)
   * @param params.max Optional maximum score value (defaults to 1)
   * @param params.reasoningKey Optional key for the LLM reasoning/explanation for the score
   * @param params.reasoningDescription Optional description of score reasoning, provided to the LLM in the structured output
   */
  constructor(params: {
    key: string;
    description: string;
    min?: number;
    max?: number;
    reasoningKey?: string;
    reasoningDescription?: string;
  }) {
    this.key = params.key;
    this.min = params.min ?? 0;
    this.max = params.max ?? 1;
    this.description = params.description;
    this.reasoningKey = params.reasoningKey;
    this.reasoningDescription = params.reasoningDescription;
  }
}

type ScoreConfig = CategoricalScoreConfig | ContinuousScoreConfig;

function createScoreJsonSchema(scoreConfig: ScoreConfig): Record<string, any> {
  const properties: Record<string, any> = {};

  if (scoreConfig.reasoningKey) {
    properties[scoreConfig.reasoningKey] = {
      type: "string",
      description:
        scoreConfig.reasoningDescription ||
        "First, think step by step to explain your score.",
    };
  }

  if ("choices" in scoreConfig) {
    properties.value = {
      type: "string",
      enum: scoreConfig.choices,
      description: `The score for the evaluation, one of ${scoreConfig.choices.join(
        ", "
      )}.`,
    };
  } else {
    properties.score = {
      type: "number",
      minimum: scoreConfig.min,
      maximum: scoreConfig.max,
      description: `The score for the evaluation, between ${scoreConfig.min} and ${scoreConfig.max}, inclusive.`,
    };
  }

  return {
    title: scoreConfig.key,
    description: scoreConfig.description,
    type: "object",
    properties,
    required: scoreConfig.reasoningKey
      ? ["choices" in scoreConfig ? "value" : "score", scoreConfig.reasoningKey]
      : ["choices" in scoreConfig ? "value" : "score"],
  };
}

interface LLMEvaluatorParams {
  promptTemplate: string | [string, string][];
  scoreConfig: ScoreConfig;
  chatModel: BaseChatModel;
  mapVariables?: (run: Run, example?: Example) => Record<string, any>;
}

/**
 * An LLM-as-a-judge evluator to assess runs based on configured scoring criteria.
 *
 * This evaluator can handle both categorical (enum-based) and continuous (numeric) scoring,
 * and can provide CoT style explanations for its evaluations when configured to do so.
 *
 * @example
 * ```typescript
 * import { LLMEvaluator, ContinuousScoreConfig } from "langsmith/evaluation/llm";
 * import { OpenAI } from "@langchain/openai"
 *
 *
 * const evaluator = new LLMEvaluator({
 *   promptTemplate: "Rate the quality of this response...",
 *   scoreConfig: new ContinuousScoreConfig({
 *     key: "quality",
 *     description: "Quality score from 0-1",
 *     min: 0,
 *     max: 1
 *   }),
 *   chatModel: new OpenAI({ model: "gpt-4" })
 * });
 * ```
 *
 * @implements {RunEvaluator}
 */
export class LLMEvaluator implements RunEvaluator {
  prompt: any;
  mapVariables?: (run: Run, example?: Example) => Record<string, any>;
  scoreConfig: ScoreConfig;
  scoreSchema: Record<string, any>;
  runnable: any;

  constructor(params: LLMEvaluatorParams) {
    const { promptTemplate, scoreConfig, chatModel, mapVariables } = params;

    // Store the configuration
    this.scoreConfig = scoreConfig;
    this.mapVariables = mapVariables;

    // Create the score schema
    this.scoreSchema = createScoreJsonSchema(scoreConfig);

    // Create the prompt template
    if (typeof promptTemplate === "string") {
      this.prompt = ChatPromptTemplate.fromMessages([
        { role: "human", content: promptTemplate },
      ]);
    } else {
      this.prompt = ChatPromptTemplate.fromMessages(promptTemplate);
    }

    const modelWithStructuredOutput = chatModel.withStructuredOutput
      ? chatModel.withStructuredOutput(this.scoreSchema)
      : null;
    if (!modelWithStructuredOutput) {
      throw new Error("Passed chat model must support structured output");
    }
    this.runnable = this.prompt.pipe(modelWithStructuredOutput);
  }

  async evaluateRun(
    run: Run,
    example?: Example
  ): Promise<EvaluationResult | EvaluationResults> {
    const runId = uuid.v4();
    const variables = this.prepareVariables(run, example);
    const output = await this.runnable.invoke(variables, { runId: runId });

    return this.parseOutput(output, runId);
  }

  private prepareVariables(run: Run, example?: Example): Record<string, any> {
    if (this.mapVariables) {
      return this.mapVariables(run, example);
    }

    const variables: Record<string, any> = {};

    // Input handling
    if (Object.keys(run.inputs).length === 0) {
      throw new Error(
        "No input keys are present in run.inputs but the prompt requires 'input'."
      );
    }
    if (Object.keys(run.inputs).length !== 1) {
      throw new Error(
        "Multiple input keys are present in run.inputs. Please provide a mapVariables function."
      );
    }
    variables.input = Object.values(run.inputs)[0];

    // Output handling
    if (!run.outputs || Object.keys(run.outputs).length === 0) {
      throw new Error(
        "No output keys are present in run.outputs but the prompt requires 'output'."
      );
    }
    if (Object.keys(run.outputs).length !== 1) {
      throw new Error(
        "Multiple output keys are present in run.outputs. Please provide a mapVariables function."
      );
    }
    variables.output = Object.values(run.outputs)[0];

    // Expected output handling
    if (example?.outputs) {
      if (Object.keys(example.outputs).length === 0) {
        throw new Error(
          "No output keys are present in example.outputs but the prompt requires 'expected'."
        );
      }
      if (Object.keys(example.outputs).length !== 1) {
        throw new Error(
          "Multiple output keys are present in example.outputs. Please provide a mapVariables function."
        );
      }
      variables.expected = Object.values(example.outputs)[0];
    }

    return variables;
  }

  protected parseOutput(
    output: Record<string, any>,
    runId: string
  ): EvaluationResult {
    const explanation = this.scoreConfig.reasoningKey
      ? output[this.scoreConfig.reasoningKey]
      : undefined;
    if ("choices" in this.scoreConfig) {
      const value = output.value;
      return {
        key: this.scoreConfig.key,
        value,
        comment: explanation,
        sourceRunId: runId,
      };
    } else {
      const score = output.score;
      return {
        key: this.scoreConfig.key,
        score,
        comment: explanation,
        sourceRunId: runId,
      };
    }
  }
}
