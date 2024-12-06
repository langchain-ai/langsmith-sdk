import { getLangSmithEnvironmentVariable } from "./utils/env.js";

export const isTracingEnabled = (tracingEnabled?: boolean): boolean => {
  if (tracingEnabled !== undefined) {
    return tracingEnabled;
  }
  const envVars = ["TRACING_V2", "TRACING"];
  return !!envVars.find(
    (envVar) => getLangSmithEnvironmentVariable(envVar) === "true"
  );
};
