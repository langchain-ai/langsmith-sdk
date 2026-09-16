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
 * Read from that name only: unlike most LangSmith variables there is no legacy
 * `LANGCHAIN_` alias, since that namespace is not taking new members. There is
 * also no default -- an agent-addressed run must name its environment.
 */
export const getDefaultAgentEnvironment = () => {
  return getEnvironmentVariable("LANGSMITH_AGENT_ENVIRONMENT");
};

/**
 * The ID of the agent to ingest runs into, read from `LANGSMITH_AGENT_ID`.
 *
 * That name only -- there is no legacy `LANGCHAIN_` alias. This is an agent
 * identifier, not a credential: the server resolves the agent by this ID and
 * creates one if it doesn't exist yet. When unset the run is addressed by
 * project instead.
 */
export const getDefaultAgentId = () => {
  return getEnvironmentVariable("LANGSMITH_AGENT_ID");
};
