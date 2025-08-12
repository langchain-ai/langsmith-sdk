/* eslint-disable import/no-extraneous-dependencies */
import {
  wrapLanguageModel,
  generateText as generateTextAI,
  streamText as streamTextAI,
  streamObject as streamObjectAI,
  generateObject as generateObjectAI,
} from "ai";
import { LangSmithMiddleware } from "./middleware.js";
import { traceable } from "../../traceable.js";

const formatToolsForTracing = (tools?: Record<string, any>) => {
  let formattedTools: Record<string, any> | undefined;
  if (tools) {
    formattedTools = {};
    for (const [key, tool] of Object.entries(tools)) {
      if (tool == null || typeof tool !== "object") {
        continue;
      }
      const castTool = tool as any;
      formattedTools[key] = {
        description: castTool.description,
        inputSchema: castTool.inputSchema,
      };
      if (
        "inputSchema" in formattedTools[key] &&
        "toJSONSchema" in formattedTools[key].inputSchema
      ) {
        formattedTools[key].inputSchema =
          formattedTools[key].inputSchema.toJSONSchema();
      }
    }
  }
  return formattedTools;
};

const wrapTools = (tools?: Record<string, any>) => {
  const wrappedTools: Record<string, any> = {};
  if (tools) {
    for (const [key, tool] of Object.entries(tools)) {
      wrappedTools[key] = tool;
      if (typeof tool.execute === "function") {
        wrappedTools[key].execute = traceable(tool.execute.bind(tool), {
          name: key,
          run_type: "tool",
        });
      }
    }
  }
  return wrappedTools;
};

const generateText = async (params: Parameters<typeof generateTextAI>[0]) => {
  if (typeof params.model === "string") {
    throw new Error("Model must be a LanguageModelV2 instance");
  }
  return traceable(
    async (
      params: Parameters<typeof generateTextAI>[0]
    ): Promise<ReturnType<typeof generateTextAI>> => {
      if (typeof params.model === "string") {
        throw new Error("Model must be a LanguageModelV2 instance");
      }
      const wrappedModel = wrapLanguageModel({
        model: params.model,
        middleware: LangSmithMiddleware({ name: params.model.modelId }),
      });
      return generateTextAI({
        ...params,
        tools: wrapTools(params.tools),
        model: wrappedModel,
      });
    },
    {
      name: params.model.provider ?? "generateText",
      processInputs: (inputs) => {
        return { ...inputs, tools: formatToolsForTracing(inputs.tools) };
      },
    }
  )(params);
};

const generateObject = async (
  params: Parameters<typeof generateObjectAI>[0]
) => {
  if (typeof params.model === "string") {
    throw new Error("Model must be a LanguageModelV2 instance");
  }
  return traceable(
    async (
      params: Parameters<typeof generateObjectAI>[0]
    ): Promise<ReturnType<typeof generateObjectAI>> => {
      if (typeof params.model === "string") {
        throw new Error("Model must be a LanguageModelV2 instance");
      }
      const wrappedModel = wrapLanguageModel({
        model: params.model,
        middleware: LangSmithMiddleware({ name: params.model.modelId }),
      });
      return generateObjectAI({
        ...params,
        model: wrappedModel,
      });
    },
    {
      name: params.model.provider ?? "generateObject",
    }
  )(params);
};

const streamText = async (params: Parameters<typeof streamTextAI>[0]) => {
  if (typeof params.model === "string") {
    throw new Error("Model must be a LanguageModelV2 instance");
  }
  return traceable(
    async (
      params: Parameters<typeof streamTextAI>[0]
    ): Promise<ReturnType<typeof streamTextAI>> => {
      if (typeof params.model === "string") {
        throw new Error("Model must be a LanguageModelV2 instance");
      }
      const wrappedModel = wrapLanguageModel({
        model: params.model,
        middleware: LangSmithMiddleware({ name: params.model.modelId }),
      });
      return streamTextAI({
        ...params,
        tools: wrapTools(params.tools),
        model: wrappedModel,
      });
    },
    {
      name: params.model.provider ?? "streamText",
      processInputs: (inputs) => {
        return { ...inputs, tools: formatToolsForTracing(inputs.tools) };
      },
    }
  )(params);
};

const streamObject = async (params: Parameters<typeof streamObjectAI>[0]) => {
  if (typeof params.model === "string") {
    throw new Error("Model must be a LanguageModelV2 instance");
  }
  return traceable(
    async (
      params: Parameters<typeof streamObjectAI>[0]
    ): Promise<ReturnType<typeof streamObjectAI>> => {
      if (typeof params.model === "string") {
        throw new Error("Model must be a LanguageModelV2 instance");
      }
      const wrappedModel = wrapLanguageModel({
        model: params.model,
        middleware: LangSmithMiddleware({ name: params.model.modelId }),
      });
      return streamObjectAI({
        ...params,
        model: wrappedModel,
      });
    },
    {
      name: params.model.provider ?? "streamObject",
    }
  )(params);
};

export { generateText, streamText, generateObject, streamObject };
