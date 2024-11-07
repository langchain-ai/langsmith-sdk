import { initChatModel } from "langchain/chat_models/universal";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import * as uuid from "uuid";
import {
  EvaluationResult,
  EvaluationResults,
  RunEvaluator,
} from "./evaluator.js";
import type { Run, Example } from "../schemas.js";

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
  mapVariables?: (run: Run, example?: Example) => Record<string, any>;
  modelName?: string;
  modelProvider?: string;
  reasoningKey?: string;
}

export class LLMEvaluator implements RunEvaluator {
  prompt: any;
  mapVariables?: (run: Run, example?: Example) => Record<string, any>;
  scoreConfig: ScoreConfig;
  scoreSchema: Record<string, any>;
  runnable: any;
  reasoningKey: string;

  constructor() {}

  static async create(params: LLMEvaluatorParams): Promise<LLMEvaluator> {
    const evaluator = new LLMEvaluator();
    await evaluator.initialize(
      params.promptTemplate,
      params.scoreConfig,
      params.mapVariables,
      params.modelName || "gpt-4o",
      params.modelProvider || "openai"
    );
    return evaluator;
  }
  private async initialize(
    promptTemplate: string | [string, string][],
    scoreConfig: ScoreConfig,
    mapVariables?: (run: Run, example?: Example) => Record<string, any>,
    modelName: string = "gpt-4o",
    modelProvider: string = "openai"
  ) {
    try {
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

      // Initialize the chat model with structured output
      const chatModel = await initChatModel(modelName, {
        modelProvider: modelProvider,
      });

      // Create the runnable pipeline
      const modelWithStructuredOutput = chatModel.withStructuredOutput(
        this.scoreSchema
      );
      this.runnable = this.prompt.pipe(modelWithStructuredOutput);
    } catch (e) {
      throw new Error(
        "LLMEvaluator requires langchain to be installed. " +
          "Please install langchain by running `npm install langchain`."
      );
    }
  }

  async evaluateRun(
    run: Run,
    example?: Example
  ): Promise<EvaluationResult | EvaluationResults> {
    const runId = uuid.v4();
    const variables = this.prepareVariables(run, example);
    let output = await this.runnable.invoke(variables, { runId: runId });

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
        "Multiple input keys are present in run.inputs. Please provide a map_variables function."
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
        "Multiple output keys are present in run.outputs. Please provide a map_variables function."
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
          "Multiple output keys are present in example.outputs. Please provide a map_variables function."
        );
      }
      variables.expected = Object.values(example.outputs)[0];
    }

    return variables;
  }

  private parseOutput(
    output: Record<string, any>,
    runId: string
  ): EvaluationResult {
    if ("choices" in this.scoreConfig) {
      const value = output.value;
      const explanation = output[this.reasoningKey];
      return {
        key: this.scoreConfig.key,
        value,
        comment: explanation,
        sourceRunId: runId,
      };
    } else {
      const score = output.score;
      const explanation = output[this.reasoningKey];
      return {
        key: this.scoreConfig.key,
        score,
        comment: explanation,
        sourceRunId: runId,
      };
    }
  }
}
