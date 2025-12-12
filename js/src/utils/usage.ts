export const convertAnthropicUsageToInputTokenDetails = (
  usage: Record<string, unknown>
) => {
  const inputTokenDetails: Record<string, number> = {};
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
  return inputTokenDetails;
};
