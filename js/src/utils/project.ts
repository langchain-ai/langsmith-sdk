import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";

export const getDefaultProjectName = () => {
  return (
    getLangSmithEnvironmentVariable("PROJECT") ??
    getEnvironmentVariable("LANGCHAIN_SESSION") ?? // TODO: Deprecate
    "default"
  );
};

/**
 * The agent environment to ingest runs into, read from `LANGSMITH_ENVIRONMENT`.
 *
 * Unlike the project, this has no default: when unset the run is ingested
 * without an environment and the server picks one.
 */
export const getDefaultAgentEnvironment = () => {
  return getLangSmithEnvironmentVariable("ENVIRONMENT");
};
