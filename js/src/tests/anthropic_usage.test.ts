import { convertAnthropicUsageToInputTokenDetails } from "../utils/usage.js";
import { createUsageMetadata } from "../wrappers/anthropic.js";

describe("convertAnthropicUsageToInputTokenDetails", () => {
  test("1h cache key has no trailing r", () => {
    const result = convertAnthropicUsageToInputTokenDetails({
      cache_creation: { ephemeral_1h_input_tokens: 200 },
    });
    expect(result).toHaveProperty("ephemeral_1hr_input_tokens", 200);
  });

  test("legacy format maps to ephemeral_5m_input_tokens", () => {
    const result = convertAnthropicUsageToInputTokenDetails({
      cache_creation_input_tokens: 7000,
    });
    expect(result).toHaveProperty("ephemeral_5m_input_tokens", 7000);
  });

  test("cache_read_input_tokens maps to cache_read", () => {
    const result = convertAnthropicUsageToInputTokenDetails({
      cache_read_input_tokens: 32000,
    });
    expect(result).toHaveProperty("cache_read", 32000);
  });

  test("new format ephemeral_5m maps correctly", () => {
    const result = convertAnthropicUsageToInputTokenDetails({
      cache_creation: { ephemeral_5m_input_tokens: 800 },
    });
    expect(result).toHaveProperty("ephemeral_5m_input_tokens", 800);
  });
});

describe("createUsageMetadata", () => {
  test("no cache — passthrough", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = createUsageMetadata({
      input_tokens: 100,
      output_tokens: 50,
    } as any);
    expect(result?.input_tokens).toBe(100);
    expect(result?.output_tokens).toBe(50);
    expect(result?.total_tokens).toBe(150);
    expect(result?.input_token_details).toBeUndefined();
  });

  test("legacy cache tokens are summed into input_tokens", () => {
    // Anthropic sends input_tokens=19 (non-cached), cache tokens are additive.
    const result = createUsageMetadata({
      input_tokens: 19,
      output_tokens: 100,
      cache_read_input_tokens: 32000,
      cache_creation_input_tokens: 7000,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    expect(result?.input_tokens).toBe(39019); // 19 + 32000 + 7000
    expect(result?.output_tokens).toBe(100);
    expect(result?.total_tokens).toBe(39119); // 39019 + 100
    expect(result?.input_token_details?.ephemeral_5m_input_tokens).toBe(7000);
    expect(result?.input_token_details?.cache_read).toBe(32000);
  });

  test("new cache_creation object format", () => {
    const result = createUsageMetadata({
      input_tokens: 100,
      output_tokens: 50,
      cache_read_input_tokens: 500,
      cache_creation: {
        ephemeral_5m_input_tokens: 800,
        ephemeral_1h_input_tokens: 200,
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    expect(result?.input_tokens).toBe(1600); // 100 + 500 + 800 + 200
    expect(result?.output_tokens).toBe(50);
    expect(result?.total_tokens).toBe(1650); // 1600 + 50
    expect(result?.input_token_details?.cache_read).toBe(500);
    expect(result?.input_token_details?.ephemeral_5m_input_tokens).toBe(800);
    expect(result?.input_token_details?.ephemeral_1hr_input_tokens).toBe(200);
  });

  test("only cache_read", () => {
    const result = createUsageMetadata({
      input_tokens: 50,
      output_tokens: 30,
      cache_read_input_tokens: 1000,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    expect(result?.input_tokens).toBe(1050); // 50 + 1000
    expect(result?.output_tokens).toBe(30);
    expect(result?.total_tokens).toBe(1080); // 1050 + 30
  });

  test("returns undefined when usage is falsy", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(createUsageMetadata(null as any)).toBeUndefined();
  });
});
