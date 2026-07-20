import { v7 as uuidv7 } from "./utils/uuid/src/index.js";
import {
  assertUuid,
  getUuidVersion,
  nonCryptographicUuid7Deterministic,
} from "./utils/_uuid.js";

export { uuid7FromTime } from "./utils/_uuid.js";

/**
 * Generate a random UUID v7 string.
 */
export function uuid7(): string {
  return uuidv7();
}

/**
 * Compute the run ID used for a tracing replica project.
 *
 * @param runId - The original UUID v7 run ID.
 * @param projectName - The destination replica project name.
 * @returns The run ID used in the replica destination.
 */
export function computeRunIdForReplica(
  runId: string,
  projectName: string,
): string {
  if (typeof projectName !== "string" || projectName.length === 0) {
    throw new Error("projectName must be a non-empty string");
  }

  assertUuid(runId, "runId");
  const normalizedRunId = runId.toLowerCase();
  if (getUuidVersion(normalizedRunId) !== 7) {
    throw new Error("runId must be a UUID v7");
  }
  return nonCryptographicUuid7Deterministic(normalizedRunId, projectName);
}
