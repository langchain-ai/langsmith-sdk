import { addressFromEnv } from "../address.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";

const tryAddressFromEnv = () => {
  try {
    const address = addressFromEnv();
    if (address != null) return undefined;
  } catch {
    return undefined;
  }
};

export const getDefaultProjectName = () => {
  if (tryAddressFromEnv() != null) return undefined;
  return (
    getLangSmithEnvironmentVariable("PROJECT") ??
    getEnvironmentVariable("LANGCHAIN_SESSION") ?? // TODO: Deprecate
    "default"
  );
};
