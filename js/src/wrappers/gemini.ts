import type { RunTreeConfig } from "../index.js";
import {
  isTraceableFunction,
  traceable,
  type TraceableConfig,
} from "../traceable.js";
import { KVMap, InvocationParamsSchema } from "../schemas.js";
import { getCurrentRunTree } from "../singletons/traceable.js";

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
    cache_read_over_200k_threshold?: number;
  };
  output_token_details?: {
    reasoning?: number;
  };
}

/**
 * Store usage metadata in run.extra.metadata.usage_metadata for LangSmith platform integration.
 */
async function storeUsageMetadata(usageMetadata: UsageMetadata): Promise<void> {
  try {
    const currentRun = getCurrentRunTree(true);
    if (!currentRun) return;

    // Initialize nested structure
    if (!currentRun.extra) currentRun.extra = {};
    if (!currentRun.extra.metadata) currentRun.extra.metadata = {};
    if (!currentRun.extra.metadata.usage_metadata) {
      currentRun.extra.metadata.usage_metadata = {};
    }

    currentRun.extra.metadata.usage_metadata = {
      ...currentRun.extra.metadata.usage_metadata,
      ...usageMetadata,
    };

    // Await patch to ensure proper completion
    await currentRun.patchRun();
  } catch {
    // Silently fail if run tree unavailable
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const chatAggregator = (chunks: any[]): any => {
  const fullText = chunks
    .filter((chunk) => chunk?.text)
    .map((chunk) => chunk.text)
    .join("");

  const result: any = {
    content: fullText,
    role: "assistant",
  };

  // Extract usage metadata from the last chunk
  if (chunks.length > 0) {
    const lastChunk = chunks[chunks.length - 1];
    if (lastChunk?.usageMetadata) {
      const usage = lastChunk.usageMetadata;
      const usageMetadata: UsageMetadata = {
        input_tokens: usage.promptTokenCount || 0,
        output_tokens:
          usage.responseTokenCount || usage.candidatesTokenCount || 0,
        total_tokens: usage.totalTokenCount || 0,
      };

      // Add cache details if available
      if (usage.cachedContentTokenCount) {
        const cacheRead = usage.cachedContentTokenCount;
        const cacheReadOver200k = Math.max(0, cacheRead - 200000);
        usageMetadata.input_token_details = {
          cache_read: cacheRead,
          cache_read_over_200k_threshold: cacheReadOver200k,
        };
      }

      // Add thoughts token count if available
      if (usage.thoughtsTokenCount) {
        usageMetadata.output_token_details = {
          reasoning: usage.thoughtsTokenCount,
        };
      }

      result.usage_metadata = usageMetadata;
      void storeUsageMetadata(usageMetadata);
    }
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function processGeminiOutputs(outputs: any): KVMap {
  const response = outputs?.outputs || outputs;

  if (!response) {
    return { content: "", role: "assistant" };
  }

  // Already processed from chatAggregator
  if (
    "content" in response &&
    "role" in response &&
    !("candidates" in response)
  ) {
    return response;
  }

  // Process raw Gemini response
  let content = "";
  const toolCalls: Array<any> = [];
  const parts: Array<any> = [];

  if (
    "candidates" in response &&
    Array.isArray(response.candidates) &&
    response.candidates.length > 0
  ) {
    const firstCandidate = response.candidates[0];

    if (firstCandidate?.content?.parts) {
      for (const part of firstCandidate.content.parts) {
        if ("text" in part && part.text) {
          content += part.text;
          parts.push({ type: "text", text: part.text });
        } else if ("functionCall" in part) {
          const funcCall = part.functionCall;
          toolCalls.push({
            type: "function",
            function: {
              name: funcCall?.name || "",
              arguments: JSON.stringify(funcCall?.args || {}),
            },
          });
        } else if ("inlineData" in part && part.inlineData) {
          // Convert inline data (images) to OpenAI-compatible format for LangSmith UI
          const mimeType = part.inlineData.mimeType || "image/jpeg";
          const data = part.inlineData.data || "";
          parts.push({
            type: "image_url",
            image_url: {
              url: `data:${mimeType};base64,${data}`,
              detail: "high",
            },
          });
        } else if ("fileData" in part && part.fileData) {
          // Handle file data
          parts.push({
            type: "file_data",
            mime_type: part.fileData.mimeType,
            file_uri: part.fileData.fileUri,
          });
        }
      }
    }
  }

  // Build result following Python's logic:
  // - If multiple parts or non-text parts: content = parts array
  // - If text-only: content = string
  let resultContent: string | Array<any>;
  if (parts.length > 1 || (parts.length > 0 && parts[0].type !== "text")) {
    // Multimodal or mixed content: use parts array
    resultContent = parts;
  } else {
    // Text-only: use string
    resultContent = content;
  }

  const result: KVMap = {
    content: resultContent,
    role: "assistant",
  };

  // Extract and store usage metadata
  if ("usageMetadata" in response && response.usageMetadata) {
    const usage = response.usageMetadata;

    const usageMetadata: UsageMetadata = {
      input_tokens: usage.promptTokenCount || 0,
      output_tokens:
        usage.responseTokenCount || usage.candidatesTokenCount || 0,
      total_tokens: usage.totalTokenCount || 0,
    };

    // Add cache details if available
    if (usage.cachedContentTokenCount) {
      const cacheRead = usage.cachedContentTokenCount;
      const cacheReadOver200k = Math.max(0, cacheRead - 200000);
      usageMetadata.input_token_details = {
        cache_read: cacheRead,
        cache_read_over_200k_threshold: cacheReadOver200k,
      };
    }

    // Add thoughts token count if available
    if (usage.thoughtsTokenCount) {
      usageMetadata.output_token_details = {
        reasoning: usage.thoughtsTokenCount,
      };
    }

    result.usage_metadata = usageMetadata;
    void storeUsageMetadata(usageMetadata);
  }

  if (toolCalls.length > 0) {
    result.tool_calls = toolCalls;
  }

  return result;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getInvocationParams(payload: any): InvocationParamsSchema {
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
