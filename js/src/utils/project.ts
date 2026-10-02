import { addressFromEnv } from "../address.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";

export const getDefaultProjectName = () => {
  const address = addressFromEnv();
  if (address != null) return undefined;

  return (
    getLangSmithEnvironmentVariable("PROJECT") ??
    getEnvironmentVariable("LANGCHAIN_SESSION") ?? // TODO: Deprecate
    "default"
  );
};
