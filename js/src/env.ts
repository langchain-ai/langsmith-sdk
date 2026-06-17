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
