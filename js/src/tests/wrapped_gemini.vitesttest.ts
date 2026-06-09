import { describe, it, expect } from "vitest";
import { createGeminiUsageMetadata } from "../wrappers/gemini.utils.js";
import type { UsageMetadata } from "@google/genai";
describe("create usage metadata", () => {
  it("basic usage", () => {
    const usage: UsageMetadata = {
      promptTokenCount: 10,
      responseTokenCount: 20,
      totalTokenCount: 30,
    };

    const result = createGeminiUsageMetadata(usage);

    expect(result).toEqual({
      input_tokens: 10,
      output_tokens: 20,
      total_tokens: 30,
      input_token_details: {
        cache_read: undefined,
        cache_read_over_200k: undefined,
        over_200k: 0,
      },
      output_token_details: {
        reasoning: undefined,
        over_200k: undefined,
      },
    });
  });

  it("includes cached tokens", () => {
    const usage: UsageMetadata = {
      promptTokenCount: 10,
      responseTokenCount: 20,
      cachedContentTokenCount: 5,
      totalTokenCount: 30,
    };

    const result = createGeminiUsageMetadata(usage);
    expect(result).toEqual({
      input_tokens: 10,
      output_tokens: 20,
      total_tokens: 30,
      input_token_details: {
        cache_read: 5,
        cache_read_over_200k: 0,
        over_200k: 0,
      },
      output_token_details: {
        reasoning: undefined,
        over_200k: undefined,
      },
    });
  });

  it("includes cached tokens over 200k", () => {
    const usage: UsageMetadata = {
      promptTokenCount: 1_000_000,
      responseTokenCount: 500_000,
      cachedContentTokenCount: 250_000,
      totalTokenCount: 1_500_000,
    };

    const result = createGeminiUsageMetadata(usage);
    expect(result).toEqual({
      input_tokens: 1_000_000,
      output_tokens: 500_000,
      total_tokens: 1_500_000,
      input_token_details: {
        cache_read: 200_000,
        cache_read_over_200k: 50_000,
        over_200k: 550_000,
      },
      output_token_details: {
        reasoning: undefined,
        over_200k: undefined,
      },
    });
  });

  it("includes reasoning tokens", () => {
    const usage: UsageMetadata = {
      promptTokenCount: 10,
      responseTokenCount: 20,
      thoughtsTokenCount: 15,
      totalTokenCount: 30,
    };

    const result = createGeminiUsageMetadata(usage);

    expect(result).toEqual({
      input_tokens: 10,
      output_tokens: 20,
      total_tokens: 30,
      input_token_details: {
        cache_read: undefined,
        cache_read_over_200k: undefined,
        over_200k: 0,
      },
      output_token_details: {
        reasoning: 15,
        over_200k: undefined,
      },
    });
  });
});
