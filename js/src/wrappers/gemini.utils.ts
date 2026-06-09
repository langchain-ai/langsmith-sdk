import type {
  GenerateContentResponseUsageMetadata,
  UsageMetadata,
} from "@google/genai";

import { KVMap } from "../schemas.js";

interface LangSmithUsageMetadata {
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

export const createGeminiUsageMetadata = (
  usage: UsageMetadata | GenerateContentResponseUsageMetadata,
): KVMap => {
  const usageMetadata: LangSmithUsageMetadata = {
    input_tokens: usage.promptTokenCount || 0,
    output_tokens: (() => {
      if ("responseTokenCount" in usage) {
        return usage.responseTokenCount || 0;
      }

      if ("candidatesTokenCount" in usage) {
        return usage.candidatesTokenCount || 0;
      }

      return 0;
    })(),
    total_tokens: usage.totalTokenCount || 0,
  };

  // Add input token details if available
  usageMetadata.input_token_details = {
    cache_read:
      usage.cachedContentTokenCount != null
        ? Math.min(usage.cachedContentTokenCount, 200_000)
        : undefined,
    cache_read_over_200k:
      usage.cachedContentTokenCount != null
        ? Math.max(0, usage.cachedContentTokenCount - 200_000)
        : undefined,
    over_200k:
      usage.promptTokenCount != null
        ? Math.max(
            0,
            usage.promptTokenCount -
              (usage.cachedContentTokenCount || 0) -
              200_000,
          )
        : undefined,
  };

  // Add output token details if available
  usageMetadata.output_token_details = {
    over_200k:
      "candidatesTokenCount" in usage && usage.candidatesTokenCount != null
        ? Math.max(0, usage.candidatesTokenCount - 200_000)
        : undefined,
    reasoning: usage.thoughtsTokenCount ?? undefined,
  };

  return usageMetadata;
};
