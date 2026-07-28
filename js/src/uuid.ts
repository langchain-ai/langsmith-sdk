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
 * Compute the run ID used for a secondary tracing replica.
 *
 * @param runId - The original UUID v7 run ID.
 * @param projectName - The secondary replica's destination project name.
 * @returns The run ID used in the secondary replica destination.
 */
export function computeRunIdForSecondaryReplica(
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
