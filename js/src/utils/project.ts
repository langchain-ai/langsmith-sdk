import { getLangSmithEnvironmentVariable } from "./env.js";

export const getProjectName = () => {
  return (
    getLangSmithEnvironmentVariable("PROJECT") ??
    getLangSmithEnvironmentVariable("SESSION")
  );
};
