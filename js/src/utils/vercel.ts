import type { LanguageModelV2Usage } from "@ai-sdk/provider";
import { KVMap } from "../schemas.js";

function isOpenAIResponse(
  aiSDKResponse: Record<string, unknown>
): aiSDKResponse is Record<string, unknown> {
  const providerMetadata =
    "providerMetadata" in aiSDKResponse
      ? (aiSDKResponse.providerMetadata as Record<string, unknown>)
      : {};
  return (
    providerMetadata != null &&
    typeof providerMetadata === "object" &&
    "openai" in providerMetadata
  );
}

function extractTraceableServiceTier(
  aiSDKResponse: Record<string, unknown>
): "priority" | "flex" | undefined {
  if (
    isOpenAIResponse(aiSDKResponse) &&
    aiSDKResponse.response != null &&
    typeof aiSDKResponse.response === "object" &&
    "body" in aiSDKResponse.response &&
    aiSDKResponse.response.body != null &&
    typeof aiSDKResponse.response.body === "object" &&
    "service_tier" in aiSDKResponse.response.body &&
    typeof aiSDKResponse.response.body.service_tier === "string" &&
    ["priority", "flex"].includes(aiSDKResponse.response.body.service_tier)
  ) {
    return aiSDKResponse.response.body.service_tier as "priority" | "flex";
  }
  return undefined;
}

export function extractOutputTokenDetails(
  usage: Partial<LanguageModelV2Usage>,
  aiSDKResponse: Record<string, unknown> = {}
) {
  const openAIServiceTier = extractTraceableServiceTier(aiSDKResponse);
  const outputTokenDetailsKeyPrefix = openAIServiceTier
    ? `${openAIServiceTier}_`
    : "";
  const outputTokenDetails: Record<string, number> = {};
  if (typeof usage.reasoningTokens === "number") {
    outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] =
      usage.reasoningTokens;
  }
  if (openAIServiceTier && typeof usage.outputTokens === "number") {
    outputTokenDetails[openAIServiceTier] = usage.outputTokens;
  }
  return outputTokenDetails;
}

export function extractInputTokenDetails(
  providerMetadata: Record<string, unknown>,
  usage?: Partial<LanguageModelV2Usage>,
  aiSDKResponse?: Record<string, unknown>
) {
  const inputTokenDetails: Record<string, number> = {};
  if (
    providerMetadata.anthropic != null &&
    typeof providerMetadata.anthropic === "object"
  ) {
    const anthropic = providerMetadata.anthropic as Record<string, unknown>;
    if (anthropic.usage != null && typeof anthropic.usage === "object") {
      // Raw usage from Anthropic returned in AI SDK 5
      const usage = anthropic.usage as Record<string, unknown>;
      if (
        usage.cache_creation != null &&
        typeof usage.cache_creation === "object"
      ) {
        const cacheCreation = usage.cache_creation as Record<string, unknown>;
        if (typeof cacheCreation.ephemeral_5m_input_tokens === "number") {
          inputTokenDetails.ephemeral_5m_input_tokens =
            cacheCreation.ephemeral_5m_input_tokens;
        }
        if (typeof cacheCreation.ephemeral_1h_input_tokens === "number") {
          inputTokenDetails.ephemeral_1hr_input_tokens =
            cacheCreation.ephemeral_1h_input_tokens;
        }
        // If cache_creation not returned (no beta header passed),
        // fallback to assuming 5m cache tokens
      } else if (typeof usage.cache_creation_input_tokens === "number") {
        inputTokenDetails.ephemeral_5m_input_tokens =
          usage.cache_creation_input_tokens;
      }
      if (typeof usage.cache_read_input_tokens === "number") {
        inputTokenDetails.cache_read = usage.cache_read_input_tokens;
      }
    } else {
      // AI SDK 4 fields
      if (
        anthropic.cacheReadInputTokens != null &&
        typeof anthropic.cacheReadInputTokens === "number"
      ) {
        inputTokenDetails.cache_read = anthropic.cacheReadInputTokens;
      }
      if (
        anthropic.cacheCreationInputTokens != null &&
        typeof anthropic.cacheCreationInputTokens === "number"
      ) {
        inputTokenDetails.ephemeral_5m_input_tokens =
          anthropic.cacheCreationInputTokens;
      }
    }
    return inputTokenDetails;
  } else if (
    providerMetadata.openai != null &&
    typeof providerMetadata.openai === "object"
  ) {
    const openAIServiceTier = extractTraceableServiceTier(aiSDKResponse ?? {});
    const outputTokenDetailsKeyPrefix = openAIServiceTier
      ? `${openAIServiceTier}_`
      : "";
    if (typeof usage?.cachedInputTokens === "number") {
      inputTokenDetails[`${outputTokenDetailsKeyPrefix}cache_read`] =
        usage.cachedInputTokens;
    } else if (
      "cachedPromptTokens" in providerMetadata.openai &&
      providerMetadata.openai.cachedPromptTokens != null &&
      typeof providerMetadata.openai.cachedPromptTokens === "number"
    ) {
      inputTokenDetails[`${outputTokenDetailsKeyPrefix}cache_read`] =
        providerMetadata.openai.cachedPromptTokens;
    }
    if (openAIServiceTier && typeof usage?.inputTokens === "number") {
      inputTokenDetails[openAIServiceTier] = usage.inputTokens;
    }
  }
  return inputTokenDetails;
}

export function extractUsageMetadata(span?: {
  status?: { code: number };
  attributes?: Record<string, unknown>;
}) {
  const isError = span?.status?.code === 2;
  if (isError || !span || !span.attributes) {
    return {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
    };
  }

  const usageMetadata: KVMap = {
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  };

  if (
    typeof span.attributes["ai.usage.promptTokens"] === "number" ||
    typeof span.attributes["ai.usage.inputTokens"] === "number"
  ) {
    usageMetadata.input_tokens =
      span.attributes["ai.usage.promptTokens"] ??
      span.attributes["ai.usage.inputTokens"];
  }

  if (
    typeof span.attributes["ai.usage.completionTokens"] === "number" ||
    typeof span.attributes["ai.usage.outputTokens"] === "number"
  ) {
    usageMetadata.output_tokens =
      span.attributes["ai.usage.completionTokens"] ??
      span.attributes["ai.usage.outputTokens"];
  }

  if (typeof span.attributes["ai.response.providerMetadata"] === "string") {
    try {
      const providerMetadata = JSON.parse(
        span.attributes["ai.response.providerMetadata"]
      );
      usageMetadata.input_token_details = extractInputTokenDetails(
        providerMetadata,
        typeof span.attributes["ai.usage.cachedInputTokens"] === "number"
          ? { cachedInputTokens: span.attributes["ai.usage.cachedInputTokens"] }
          : undefined
      );
      if (
        providerMetadata.anthropic != null &&
        typeof providerMetadata.anthropic === "object"
      ) {
        // AI SDK does not include Anthropic cache tokens in their stated input token
        // numbers, so we need to add them manually
        for (const key in usageMetadata.input_token_details) {
          usageMetadata.input_tokens += usageMetadata.input_token_details[key];
        }
      }
    } catch {
      // pass
    }
  }
  usageMetadata.total_tokens =
    usageMetadata.input_tokens + usageMetadata.output_tokens;
  return usageMetadata;
}
