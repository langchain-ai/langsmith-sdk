import { v7 as uuidv7 } from "./utils/uuid/src/index.js";
import { nonCryptographicUuid7Deterministic } from "./utils/_uuid.js";

export { uuid7FromTime } from "./utils/_uuid.js";

/**
 * Generate a random UUID v7 string.
 */
export function uuid7(): string {
  return uuidv7();
}

/**
 * Generate the run ID used for a tracing replica.
 *
 * Use this ID when creating feedback for a run in a replica project. The
 * result matches the deterministic ID remapping performed when LangSmith
 * sends a UUID v7 run to a replica whose project differs from the run's
 * original project.
 *
 * @param runId - The original run ID.
 * @param projectName - The destination replica project name.
 * @returns The run ID used in the replica project.
 */
export function computeRunIdForReplica(
  runId: string,
  projectName: string,
): string {
  return nonCryptographicUuid7Deterministic(runId, projectName);
}
