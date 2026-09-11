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

/**
 * The key of the agent to ingest runs into, read from `LANGSMITH_AGENT_KEY`.
 *
 * This is an agent identifier, not a credential: the server resolves the agent
 * by this key and creates one if it doesn't exist yet. Like the environment, it
 * has no default: when unset the run is ingested without an agent key and
 * addressed by project instead.
 */
export const getDefaultAgentKey = () => {
  return getLangSmithEnvironmentVariable("AGENT_KEY");
};
