import type { RunTreeConfig } from "../index.js";
import {
  isTraceableFunction,
  traceable,
  type TraceableConfig,
} from "../traceable.js";
import { KVMap, InvocationParamsSchema } from "../schemas.js";

type GoogleGenAIType = {
  models: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    generateContent: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    generateContentStream: (...args: any[]) => any;
  };
};

type PatchedGeminiClient<T extends GoogleGenAIType> = T & {
  models: T["models"] & {
    generateContent: T["models"]["generateContent"];
    generateContentStream: T["models"]["generateContentStream"];
  };
};

interface UsageMetadata {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_token_details?: {
    cache_read?: number;
    cache_read_over_200k?: number;
    over_200k?: number;
  };
  output_token_details?: {
    reasoning?: number;
    over_200k?: number;
  };
}

const _createUsageMetadata = (usage: Record<string, any>): KVMap => {
  const usageMetadata: UsageMetadata = {
    input_tokens: usage.promptTokenCount || 0,
    output_tokens: usage.responseTokenCount || usage.candidatesTokenCount || 0,
    total_tokens: usage.totalTokenCount || 0,
  };

  // Add input token details if available
  usageMetadata.input_token_details = {
    ...(usage.cachedContentTokenCount && {
      cache_read_over_200k: Math.max(0, usage.cachedContentTokenCount - 200000),
    }),
    ...(usage.promptTokenCount && {
      over_200k: Math.max(0, usage.promptTokenCount - 200000),
    }),
    ...(usage.cachedContentTokenCount && {
      cache_read: usage.cachedContentTokenCount,
    }),
  };

  // Add output token details if available
  usageMetadata.output_token_details = {
    ...(usage.candidatesTokenCount && {
      over_200k: Math.max(0, usage.candidatesTokenCount - 200000),
    }),
    ...(usage.thoughtsTokenCount && {
      reasoning: usage.thoughtsTokenCount,
    }),
  };

  return usageMetadata;
};

const chatAggregator = (chunks: Record<string, any>[]): KVMap => {
  if (!chunks || chunks.length === 0) {
    return { content: "", role: "assistant" };
  }

  let text = "";
  let thoughtText = "";
  const toolCalls: Array<Record<string, unknown>> = [];
  const otherParts: Array<Record<string, unknown>> = [];
  let usageMetadata: Record<string, any> | null = null;
  let finishReason: string | null = null;
  let safetyRatings: Array<Record<string, any>> | null = null;

  for (const chunk of chunks) {
    if (chunk?.usageMetadata) {
      usageMetadata = chunk.usageMetadata;
    }

    if (chunk?.candidates && Array.isArray(chunk.candidates)) {
      for (const candidate of chunk.candidates) {
        if (candidate.finishReason) {
          finishReason = candidate.finishReason;
        }
        if (candidate.safetyRatings) {
          safetyRatings = candidate.safetyRatings;
        }

        if (candidate.content?.parts) {
          for (const part of candidate.content.parts) {
            if ("text" in part && part.text !== undefined) {
              if (part.thought) {
                thoughtText += part.text;
              } else {
                text += part.text;
              }
            } else if ("functionCall" in part && part.functionCall) {
              toolCalls.push({
                type: "function",
                function: {
                  name: part.functionCall.name || "",
                  arguments: JSON.stringify(part.functionCall.args || {}),
                },
              });
            } else if (
              "codeExecutionResult" in part &&
              part.codeExecutionResult
            ) {
              otherParts.push({
                type: "code_execution_result",
                code_execution_result: part.codeExecutionResult,
              });
            } else if ("executableCode" in part && part.executableCode) {
              otherParts.push({
                type: "executable_code",
                executable_code: part.executableCode,
              });
            } else if ("inlineData" in part && part.inlineData) {
              const mimeType = part.inlineData.mimeType || "image/jpeg";
              const data = part.inlineData.data || "";
              otherParts.push({
                type: "image_url",
                image_url: {
                  url: `data:${mimeType};base64,${data}`,
                  detail: "high",
                },
              });
            } else if ("fileData" in part && part.fileData) {
              otherParts.push({
                type: "file_data",
                mime_type: part.fileData.mimeType,
                file_uri: part.fileData.fileUri,
              });
            }
          }
        }
      }
    } else if (chunk?.text) {
      text += chunk.text;
    }
  }

  const contentParts: Array<Record<string, unknown>> = [];

  if (thoughtText) {
    contentParts.push({ type: "text", text: thoughtText, thought: true });
  }

  if (text) {
    contentParts.push({ type: "text", text: text });
  }

  contentParts.push(...otherParts);

  const result: KVMap = {
    role: "assistant",
  };

  if (
    contentParts.length > 1 ||
    (contentParts.length > 0 && contentParts[0].type !== "text")
  ) {
    result.content = contentParts;
  } else if (
    contentParts.length === 1 &&
    contentParts[0].type === "text" &&
    !contentParts[0].thought
  ) {
    result.content = contentParts[0].text as string;
  } else if (thoughtText && !text) {
    result.content = contentParts;
  } else {
    result.content = text || "";
  }

  if (toolCalls.length > 0) {
    result.tool_calls = toolCalls;
  }

  if (finishReason) {
    result.finish_reason = finishReason;
  }

  if (safetyRatings) {
    result.safety_ratings = safetyRatings;
  }

  if (usageMetadata) {
    result.usage_metadata = _createUsageMetadata(usageMetadata);
  }

  return result;
};

function processGeminiInputs(inputs: KVMap): KVMap {
  const { contents, model, ...rest } = inputs;

  if (!contents) {
    return inputs;
  }

  if (typeof contents === "string") {
    return {
      messages: [{ role: "user", content: contents }],
      ...rest,
    };
  }

  if (Array.isArray(contents)) {
    if (contents.every((item) => typeof item === "string")) {
      return {
        messages: contents.map((text) => ({ role: "user", content: text })),
        ...rest,
      };
    }

    const messages = contents
      .map((content) => {
        if (typeof content !== "object" || content === null) {
          return null;
        }

        const role = content.role || "user";
        const parts = content.parts || [];
        const textParts: string[] = [];
        const contentParts: Array<Record<string, any>> = [];

        for (const part of parts) {
          if (typeof part === "object" && part !== null) {
            if ("text" in part && part.text) {
              textParts.push(part.text);
              contentParts.push({ type: "text", text: part.text });
            } else if ("inlineData" in part) {
              const inlineData = part.inlineData;
              const mimeType = inlineData?.mimeType || "image/jpeg";
              const data = inlineData?.data || "";

              contentParts.push({
                type: "image_url",
                image_url: {
                  url: `data:${mimeType};base64,${data}`,
                  detail: "high",
                },
              });
            } else if ("functionResponse" in part) {
              const funcResponse = part.functionResponse;
              contentParts.push({
                type: "function_response", //TODO: add testing for function_response
                function_response: {
                  name: funcResponse?.name,
                  response: funcResponse?.response || {},
                },
              });
            }
          } else if (typeof part === "string") {
            textParts.push(part);
            contentParts.push({ type: "text", text: part });
          }
        }

        const messageContent =
          contentParts.length > 0 &&
          contentParts.every((p) => p.type === "text")
            ? textParts.join("\n")
            : contentParts.length > 0
            ? contentParts
            : "";

        return { role, content: messageContent };
      })
      .filter((msg): msg is { role: string; content: any } => msg !== null);

    return {
      messages,
      ...rest,
    };
  }

  return inputs;
}

function processGeminiOutputs(outputs: Record<string, any>): KVMap {
  const response = outputs?.outputs || outputs;

  if (!response) {
    return { content: "", role: "assistant" };
  }

  if (
    "content" in response &&
    "role" in response &&
    !("candidates" in response)
  ) {
    return response;
  }

  let text = "";
  let thoughtText = "";
  const toolCalls: Array<Record<string, unknown>> = [];
  const otherParts: Array<Record<string, unknown>> = [];
  let finishReason: string | null = null;
  let safetyRatings: Array<Record<string, any>> | null = null;

  if (
    "candidates" in response &&
    Array.isArray(response.candidates) &&
    response.candidates.length > 0
  ) {
    const firstCandidate = response.candidates[0];

    if (firstCandidate.finishReason) {
      finishReason = firstCandidate.finishReason;
    }
    if (firstCandidate.safetyRatings) {
      safetyRatings = firstCandidate.safetyRatings;
    }

    if (firstCandidate?.content?.parts) {
      for (const part of firstCandidate.content.parts) {
        if ("text" in part && part.text !== undefined) {
          if (part.thought) {
            thoughtText += part.text;
          } else {
            text += part.text;
          }
        } else if ("functionCall" in part && part.functionCall) {
          toolCalls.push({
            type: "function",
            function: {
              name: part.functionCall.name || "",
              arguments: JSON.stringify(part.functionCall.args || {}),
            },
          });
        } else if ("codeExecutionResult" in part && part.codeExecutionResult) {
          otherParts.push({
            type: "code_execution_result",
            code_execution_result: part.codeExecutionResult,
          });
        } else if ("executableCode" in part && part.executableCode) {
          otherParts.push({
            type: "executable_code",
            executable_code: part.executableCode,
          });
        } else if ("inlineData" in part && part.inlineData) {
          const mimeType = part.inlineData.mimeType || "image/jpeg";
          const data = part.inlineData.data || "";
          otherParts.push({
            type: "image_url",
            image_url: {
              url: `data:${mimeType};base64,${data}`,
              detail: "high",
            },
          });
        } else if ("fileData" in part && part.fileData) {
          otherParts.push({
            type: "file_data",
            mime_type: part.fileData.mimeType,
            file_uri: part.fileData.fileUri,
          });
        }
      }
    }
  }

  const contentParts: Array<Record<string, unknown>> = [];

  if (thoughtText) {
    contentParts.push({ type: "text", text: thoughtText, thought: true });
  }
  if (text) {
    contentParts.push({ type: "text", text: text });
  }
  contentParts.push(...otherParts);

  const result: KVMap = {
    role: "assistant",
  };

  if (
    contentParts.length > 1 ||
    (contentParts.length > 0 && contentParts[0].type !== "text")
  ) {
    result.content = contentParts;
  } else if (
    contentParts.length === 1 &&
    contentParts[0].type === "text" &&
    !contentParts[0].thought
  ) {
    result.content = contentParts[0].text as string;
  } else if (thoughtText && !text) {
    result.content = contentParts;
  } else {
    result.content = text || "";
  }

  if (toolCalls.length > 0) {
    result.tool_calls = toolCalls;
  }

  if (finishReason) {
    result.finish_reason = finishReason;
  }

  if (safetyRatings) {
    result.safety_ratings = safetyRatings;
  }

  if ("usageMetadata" in response && response.usageMetadata) {
    result.usage_metadata = _createUsageMetadata(response.usageMetadata);
  }

  return result;
}

function getInvocationParams(
  payload: Record<string, any>
): InvocationParamsSchema {
  const config = payload?.[0] || payload;
  return {
    ls_provider: "google",
    ls_model_type: "chat" as const,
    ls_model_name: config?.model || "unknown",
    ls_temperature: config?.config?.temperature,
    ls_max_tokens: config?.config?.maxOutputTokens,
  };
}

/**
 * Wraps a Google Gemini client to enable automatic LangSmith tracing.
 *
 * **⚠️ BETA: This feature is in beta and may change in future releases.**
 *
 * Supports tracing for:
 * - Text generation (streaming and non-streaming)
 * - Multimodal inputs (text + images)
 * - Image generation output (gemini-2.5-flash-image)
 * - Function calling
 * - Usage metadata extraction
 *
 * @param gemini - A Google GenAI client instance
 * @param options - LangSmith tracing configuration options
 * @returns A wrapped client with automatic tracing enabled
 *
 * @example
 * ```ts
 * import { GoogleGenAI } from "@google/genai";
 * import { wrapGemini } from "langsmith/wrappers/gemini";
 *
 * const client = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
 * const wrapped = wrapGemini(client, { tracingEnabled: true });
 *
 * // Use the wrapped client exactly like the original
 * const response = await wrapped.models.generateContent({
 *   model: "gemini-2.0-flash-exp",
 *   contents: "Hello!",
 * });
 * ```
 */
export function wrapGemini<T extends GoogleGenAIType>(
  gemini: T,
  options?: Partial<RunTreeConfig>
): PatchedGeminiClient<T> {
  // Prevent double wrapping
  if (
    isTraceableFunction(gemini.models.generateContent) ||
    isTraceableFunction(gemini.models.generateContentStream)
  ) {
    throw new Error(
      "This Google Gen AI client has already been wrapped. " +
        "Wrapping a client multiple times is not supported."
    );
  }

  const tracedGeminiClient = { ...gemini } as PatchedGeminiClient<T>;

  const geminiTraceConfig: TraceableConfig<
    typeof gemini.models.generateContent
  > = {
    name: "ChatGoogleGenerativeAI",
    run_type: "llm",
    getInvocationParams,
    processInputs: processGeminiInputs,
    processOutputs: processGeminiOutputs,
    ...options,
  };

  const geminiStreamTraceConfig: TraceableConfig<
    typeof gemini.models.generateContentStream
  > = {
    name: "ChatGoogleGenerativeAI",
    run_type: "llm",
    aggregator: chatAggregator,
    getInvocationParams,
    processInputs: processGeminiInputs,
    processOutputs: processGeminiOutputs,
    ...options,
  };

  tracedGeminiClient.models = {
    ...gemini.models,
    generateContent: traceable(
      gemini.models.generateContent.bind(gemini.models),
      geminiTraceConfig
    ),
    generateContentStream: traceable(
      gemini.models.generateContentStream.bind(gemini.models),
      geminiStreamTraceConfig
    ),
  };

  return tracedGeminiClient;
}

export default wrapGemini;
