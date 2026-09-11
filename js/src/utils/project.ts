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
 * The agent environment to ingest runs into, read from
 * `LANGSMITH_AGENT_ENVIRONMENT`.
 *
 * Unlike the project, this has no default: when unset the run is ingested
 * without an environment and the server picks one.
 */
export const getDefaultAgentEnvironment = () => {
  return getLangSmithEnvironmentVariable("AGENT_ENVIRONMENT");
};

/**
 * The ID of the agent to ingest runs into, read from `LANGSMITH_AGENT_ID`.
 *
 * This is an agent identifier, not a credential: the server resolves the agent
 * by this ID and creates one if it doesn't exist yet. Like the environment, it
 * has no default: when unset the run is ingested without an agent ID and
 * addressed by project instead.
 */
export const getDefaultAgentId = () => {
  return getLangSmithEnvironmentVariable("AGENT_ID");
};
