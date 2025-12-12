import { _LC_CONTEXT_VARIABLES_KEY } from "../singletons/constants.js";

/**
 * Get a context variable from a run tree instance
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getContextVar(runTree: any, key: symbol): unknown {
  if (_LC_CONTEXT_VARIABLES_KEY in runTree) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const contextVars = (runTree as any)[_LC_CONTEXT_VARIABLES_KEY];
    return contextVars[key];
  }
  return undefined;
}

/**
 * Set a context variable on a run tree instance
 */
export function setContextVar(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  runTree: any,
  key: symbol,
  value: unknown
): void {
  const contextVars =
    _LC_CONTEXT_VARIABLES_KEY in runTree
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (runTree as any)[_LC_CONTEXT_VARIABLES_KEY]
      : {};

  contextVars[key] = value;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (runTree as any)[_LC_CONTEXT_VARIABLES_KEY] = contextVars;
}
