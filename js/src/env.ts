import { getLangSmithEnvironmentVariable } from "./utils/env.js";

export const isEnvTracingEnabled = (tracingEnabled?: boolean): boolean => {
  if (tracingEnabled !== undefined) {
    return tracingEnabled;
  }
  const envVars = ["TRACING_V2", "TRACING"];
  return !!envVars.find(
    (envVar) => getLangSmithEnvironmentVariable(envVar) === "true",
  );
};

/**
 * Whether a failed redactor should fall back to tracing the raw payload.
 *
 * Set `LANGSMITH_ALLOW_UNPROCESSED_PAYLOADS` to restore the pre-fail-closed
 * behavior in an emergency. It uploads data no redactor processed, so it is off
 * by default and the caller logs a warning naming it whenever it takes effect.
 * Read only on failure, so it stays off the hot path.
 */
export const allowUnprocessedPayloads = (): boolean => {
  const value = getLangSmithEnvironmentVariable("ALLOW_UNPROCESSED_PAYLOADS");
  return value?.toLowerCase() === "true" || value === "1";
};
