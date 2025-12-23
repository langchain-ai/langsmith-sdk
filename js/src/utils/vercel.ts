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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const usageAny = usage as Record<string, any>;

  // AI SDK 6: Check for built-in outputTokens breakdown first
  if (
    typeof usageAny?.outputTokens === "object" &&
    usageAny.outputTokens != null
  ) {
    const outputTokens = usageAny.outputTokens;

    // Extract reasoning tokens from AI SDK 6
    if (
      typeof outputTokens.reasoning === "number" &&
      outputTokens.reasoning > 0
    ) {
      outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] =
        outputTokens.reasoning;
    }

    // Apply service tier logic for AI SDK 6
    if (openAIServiceTier && typeof outputTokens.total === "number") {
      // Avoid counting reasoning tokens towards the output token count
      // since service tier tokens are already priced differently
      outputTokenDetails[openAIServiceTier] =
        outputTokens.total -
        (outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] ?? 0);
    }

    // Return AI SDK 6 results (even if empty, to prevent falling through to SDK 5 logic)
    return outputTokenDetails;
  }

  // Provider-specific extraction for AI SDK 5/4 or when SDK 6 doesn't have breakdowns
  let reasoningTokens: number | undefined;

  // AI SDK 5: reasoningTokens
  if (typeof usage?.reasoningTokens === "number") {
    reasoningTokens = usage.reasoningTokens;
  }

  if (typeof reasoningTokens === "number") {
    outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] =
      reasoningTokens;
  }

  // Extract total output tokens for service tier calculation
  let outputTokensTotal: number | undefined;
  if (typeof usage?.outputTokens === "number") {
    // AI SDK 5: outputTokens
    outputTokensTotal = usage.outputTokens;
  }

  if (openAIServiceTier && typeof outputTokensTotal === "number") {
    // Avoid counting reasoning tokens towards the output token count
    // since service tier tokens are already priced differently
    outputTokenDetails[openAIServiceTier] =
      outputTokensTotal -
      (outputTokenDetails[`${outputTokenDetailsKeyPrefix}reasoning`] ?? 0);
  }
  return outputTokenDetails;
}

export function extractInputTokenDetails(
  usage?: Partial<LanguageModelV2Usage>,
  providerMetadata?: Record<string, unknown>
) {
  let inputTokenDetails: Record<string, number> = {};
  const usageAny = usage as Record<string, any>;

  // AI SDK 6: Check for built-in inputTokens breakdown first
  if (
    typeof usageAny?.inputTokens === "object" &&
    usageAny.inputTokens != null
  ) {
    const inputTokens = usageAny.inputTokens;

    // Extract standard AI SDK 6 input token breakdowns
    // Map AI SDK 6 fields to LangSmith token detail fields:
    // - cacheRead -> cache_read
    // - cacheWrite -> cache_creation
    if (
      typeof inputTokens.cacheRead === "number" &&
      inputTokens.cacheRead > 0
    ) {
      inputTokenDetails.cache_read = inputTokens.cacheRead;
    }
    if (
      typeof inputTokens.cacheWrite === "number" &&
      inputTokens.cacheWrite > 0
    ) {
      inputTokenDetails.cache_creation = inputTokens.cacheWrite;
    }

    // Handle OpenAI service tier for AI SDK 6
    const openAIServiceTier = extractTraceableServiceTier(
      providerMetadata ?? {}
    );
    if (openAIServiceTier) {
      const serviceTierPrefix = `${openAIServiceTier}_`;

      // Add cache_read with service tier prefix if we have cached tokens
      if (
        typeof inputTokens.cacheRead === "number" &&
        inputTokens.cacheRead > 0
      ) {
        inputTokenDetails[`${serviceTierPrefix}cache_read`] =
          inputTokens.cacheRead;
        // Remove the non-prefixed version since we're using service tier
        delete inputTokenDetails.cache_read;
      }

      // Calculate service tier tokens (total minus cached)
      if (typeof inputTokens.total === "number") {
        inputTokenDetails[openAIServiceTier] =
          inputTokens.total -
          (inputTokenDetails[`${serviceTierPrefix}cache_read`] ?? 0);
      }
    }

    // Return AI SDK 6 results (even if empty, to prevent falling through to SDK 5 logic)
    return inputTokenDetails;
  }

  // Provider-specific extraction for AI SDK 5/4 or when SDK 6 doesn't have breakdowns
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

    const usageAny = usage as Record<string, any>;
    let cachedInputTokens: number | undefined;

    // AI SDK 6: inputTokens.cacheRead
    if (
      typeof usageAny?.inputTokens === "object" &&
      usageAny.inputTokens?.cacheRead != null
    ) {
      cachedInputTokens = usageAny.inputTokens.cacheRead;
    } else if (typeof usage?.cachedInputTokens === "number") {
      // AI SDK 5: cachedInputTokens
      cachedInputTokens = usage.cachedInputTokens;
    } else if (
      "cachedPromptTokens" in providerMetadata.openai &&
      providerMetadata.openai.cachedPromptTokens != null &&
      typeof providerMetadata.openai.cachedPromptTokens === "number"
    ) {
      // AI SDK 4: cachedPromptTokens in providerMetadata
      cachedInputTokens = providerMetadata.openai.cachedPromptTokens;
    }

    if (typeof cachedInputTokens === "number") {
      inputTokenDetails[`${outputTokenDetailsKeyPrefix}cache_read`] =
        cachedInputTokens;
    }

    // Extract total input tokens for service tier calculation
    let inputTokensTotal: number | undefined;
    if (
      typeof usageAny?.inputTokens === "object" &&
      usageAny.inputTokens?.total != null
    ) {
      // AI SDK 6: inputTokens.total
      inputTokensTotal = usageAny.inputTokens.total;
    } else if (typeof usage?.inputTokens === "number") {
      // AI SDK 5: inputTokens
      inputTokensTotal = usage.inputTokens;
    }

    if (openAIServiceTier && typeof inputTokensTotal === "number") {
      // Avoid counting cached input tokens towards the input token count
      // since service tier tokens are already priced differently
      inputTokenDetails[openAIServiceTier] =
        inputTokensTotal -
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
