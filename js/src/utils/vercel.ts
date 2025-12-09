import type { LanguageModelV2Usage } from "@ai-sdk/provider";
import { KVMap } from "../schemas.js";
import { convertAnthropicUsageToInputTokenDetails } from "./usage.js";

function extractTraceableServiceTier(
  providerMetadata: Record<string, unknown>
): "priority" | "flex" | undefined {
  if (
    providerMetadata?.openai != null &&
    typeof providerMetadata.openai === "object"
  ) {
    const openai = providerMetadata.openai as Record<string, unknown>;
    if (
      openai.serviceTier != null &&
      typeof openai.serviceTier === "string" &&
      ["priority", "flex"].includes(openai.serviceTier)
    ) {
      return openai.serviceTier as "priority" | "flex";
    }
  }
  return undefined;
}

export function extractOutputTokenDetails(
  usage?: Partial<LanguageModelV2Usage>,
  providerMetadata?: Record<string, unknown>
) {
  const openAIServiceTier = extractTraceableServiceTier(providerMetadata ?? {});
  const outputTokenDetailsKeyPrefix = openAIServiceTier
    ? `${openAIServiceTier}_`
    : "";
  const outputTokenDetails: Record<string, number> = {};
  if (typeof usage?.reasoningTokens === "number") {
    outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] =
      usage.reasoningTokens;
  }
  if (openAIServiceTier && typeof usage?.outputTokens === "number") {
    // Avoid counting reasoning tokens towards the output token count
    // since service tier tokens are already priced differently
    outputTokenDetails[openAIServiceTier] =
      usage.outputTokens -
      (outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] ?? 0);
  }
  return outputTokenDetails;
}

export function extractInputTokenDetails(
  usage?: Partial<LanguageModelV2Usage>,
  providerMetadata?: Record<string, unknown>
) {
  let inputTokenDetails: Record<string, number> = {};
  if (
    providerMetadata?.anthropic != null &&
    typeof providerMetadata?.anthropic === "object"
  ) {
    const anthropic = providerMetadata.anthropic as Record<string, unknown>;
    if (anthropic.usage != null && typeof anthropic.usage === "object") {
      // Raw usage from Anthropic returned in AI SDK 5
      const usage = anthropic.usage as Record<string, unknown>;
      inputTokenDetails = convertAnthropicUsageToInputTokenDetails(usage);
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
    providerMetadata?.openai != null &&
    typeof providerMetadata?.openai === "object"
  ) {
    const openAIServiceTier = extractTraceableServiceTier(
      providerMetadata ?? {}
    );
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
      // Avoid counting cached input tokens towards the input token count
      // since service tier tokens are already priced differently
      inputTokenDetails[openAIServiceTier] =
        usage.inputTokens -
        (inputTokenDetails[`${outputTokenDetailsKeyPrefix}cache_read`] ?? 0);
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
        typeof span.attributes["ai.usage.cachedInputTokens"] === "number"
          ? { cachedInputTokens: span.attributes["ai.usage.cachedInputTokens"] }
          : undefined,
        providerMetadata
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
