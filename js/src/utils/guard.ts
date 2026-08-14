import { isEnvTracingEnabled } from "../env.js";
import { getCurrentRunTree } from "../singletons/traceable.js";

/**
 * Check if tracing is enabled for the current run tree or environment.
 *
 * @returns `true` if tracing is enabled, `false` otherwise.
 */
export function isTracingEnabled() {
  return getCurrentRunTree(true)?.tracingEnabled ?? isEnvTracingEnabled();
}
