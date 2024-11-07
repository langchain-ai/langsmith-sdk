import { RunEvaluator } from "langsmith/evaluation";
import { initChatModel } from "langchain/chat_models/universal";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import * as uuid from "uuid";
import { EvaluationResult, EvaluationResults } from "./evaluator.js";
import type { Run, Example } from "../schemas.js";
export class CategoricalScoreConfig {
  key: string;
  choices: string[];
  description: string;
  includeExplanation: boolean;
  explanationDescription?: string;

  constructor(params: {
    key: string;
    choices: string[];
    description: string;
    includeExplanation?: boolean;
    explanationDescription?: string;
  }) {
    this.key = params.key;
    this.choices = params.choices;
    this.description = params.description;
    this.includeExplanation = params.includeExplanation ?? false;
    this.explanationDescription = params.explanationDescription;
  }
}
  
export class ContinuousScoreConfig {
  key: string;
  min: number;
  max: number;
  description: string;
  includeExplanation: boolean;
  explanationDescription?: string;

  constructor(params: {
    key: string;
    description: string;
    min?: number;
    max?: number;
    includeExplanation?: boolean;
    explanationDescription?: string;
  }) {
    this.key = params.key;
    this.min = params.min ?? 0;
    this.max = params.max ?? 1;
    this.description = params.description;
    this.includeExplanation = params.includeExplanation ?? false;
    this.explanationDescription = params.explanationDescription;
  }
}

type ScoreConfig = CategoricalScoreConfig | ContinuousScoreConfig;

function createScoreJsonSchema(
  scoreConfig: ScoreConfig,
  reasoningKey: string
): Record<string, any> {
  const properties: Record<string, any> = {};

  if (scoreConfig.includeExplanation) {
    properties[reasoningKey] = {
      type: "string",
      description: scoreConfig.explanationDescription || "The explanation for the score.",
    };
  }

  if ("choices" in scoreConfig) {
    properties.score = {
      type: "string",
      enum: scoreConfig.choices,
      description: `The score for the evaluation, one of ${scoreConfig.choices.join(", ")}.`,
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
    required: scoreConfig.includeExplanation ? ["score", reasoningKey] : ["score"],
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
  private prompt: any;
  private mapVariables?: (run: Run, example?: Example) => Record<string, any>;
  private scoreConfig: ScoreConfig;
  private scoreSchema: Record<string, any>;
  private runnable: any;
  private reasoningKey: string;

  constructor() {}

  static async create(params: LLMEvaluatorParams): Promise<LLMEvaluator> {
    const evaluator = new LLMEvaluator();
    await evaluator.initialize(
      params.promptTemplate,
      params.scoreConfig,
      params.mapVariables,
      params.modelName || "gpt-4o",
      params.modelProvider || "openai", 
      params.reasoningKey || "reasoning"
    );
    return evaluator;
  }
  private async initialize(
    promptTemplate: string | [string, string][],
    scoreConfig: ScoreConfig,
    mapVariables?: (run: Run, example?: Example) => Record<string, any>,
    modelName: string = "gpt-4o",
    modelProvider: string = "openai",
    reasoningKey: string = "reasoning"
  ) {
    try {
      // Store the configuration
      this.scoreConfig = scoreConfig;
      this.mapVariables = mapVariables;
      this.reasoningKey = reasoningKey;

      // Create the score schema
      this.scoreSchema = createScoreJsonSchema(scoreConfig, reasoningKey);

      // Create the prompt template
      if (typeof promptTemplate === "string") {
        this.prompt = ChatPromptTemplate.fromMessages([{ role: "human", content: promptTemplate }]);
      } else {
        this.prompt = ChatPromptTemplate.fromMessages(promptTemplate);
      }

      // Initialize the chat model with structured output
      const chatModel = await initChatModel(modelName, {
        modelProvider: modelProvider,
      });

      // Create the runnable pipeline
      const modelWithStructuredOutput = chatModel.withStructuredOutput(this.scoreSchema);
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
    const variables = this.prepareVariables(run, example);
    const output = await this.runnable.invoke(variables, { config: { run_id: uuid.v4() }} );
    return this.parseOutput(output);
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

  private parseOutput(output: Record<string, any>): EvaluationResult {
    if ("choices" in this.scoreConfig) {
      const value = output.score;
      const explanation = output[this.reasoningKey];
      console.log(output);
      return {
        key: this.scoreConfig.key,
        value,
        comment: explanation,
      };
    } else {
      const score = output.score;
      const explanation = output[this.reasoningKey];
      return {
        key: this.scoreConfig.key,
        score,
        comment: explanation,
      };
    }
  }
}