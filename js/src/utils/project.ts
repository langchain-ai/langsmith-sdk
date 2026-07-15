import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";
import { assertUuid } from "./_uuid.js";

export const getDefaultProjectName = () => {
  return (
    getLangSmithEnvironmentVariable("PROJECT") ??
    getEnvironmentVariable("LANGCHAIN_SESSION") ?? // TODO: Deprecate
    "default"
  );
};

export const getDefaultProjectId = () => {
  const projectId = getEnvironmentVariable("LANGSMITH_PROJECT_ID");
  return projectId ? assertUuid(projectId, "LANGSMITH_PROJECT_ID") : undefined;
};
