import { KVMap } from "../schemas.js";

function extractInputTokenDetails(
  providerMetadata: Record<string, unknown>,
  spanAttributes?: Record<string, unknown>
) {
  const inputTokenDetails: Record<string, number> = {};
  if (
    providerMetadata.anthropic != null &&
    typeof providerMetadata.anthropic === "object"
  ) {
    const anthropic = providerMetadata.anthropic as Record<string, unknown>;
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
    return inputTokenDetails;
  } else if (
    providerMetadata.openai != null &&
    typeof providerMetadata.openai === "object"
  ) {
    const openai = providerMetadata.openai as Record<string, unknown>;
    if (
      openai.cachedPromptTokens != null &&
      typeof openai.cachedPromptTokens === "number"
    ) {
      inputTokenDetails.cache_read = openai.cachedPromptTokens;
    } else if (
      typeof spanAttributes?.["ai.usage.cachedInputTokens"] === "number"
    ) {
      inputTokenDetails.cache_read =
        spanAttributes["ai.usage.cachedInputTokens"];
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
        span.attributes
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
