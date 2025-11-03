import { validate as uuidValidate } from "uuid";

export function assertUuid(str: string, which?: string): string {
  if (!uuidValidate(str)) {
    const msg =
      which !== undefined
        ? `Invalid UUID for ${which}: ${str}`
        : `Invalid UUID: ${str}`;
    throw new Error(msg);
  }
  return str;
}

/**
 * Get the version of a UUID string.
 * @param uuidStr - The UUID string to check
 * @returns The version number (1-7) or null if invalid
 */
export function getUuidVersion(uuidStr: string): number | null {
  if (!uuidValidate(uuidStr)) {
    return null;
  }

  // Version is in bits 48-51
  // Format: xxxxxxxx-xxxx-Vxxx-xxxx-xxxxxxxxxxxx
  const versionChar = uuidStr[14];
  return parseInt(versionChar, 16);
}

/**
 * Warn if a UUID is not version 7.
 *
 * @param uuidStr - The UUID string to check
 * @param idType - The type of ID (e.g., "run_id", "trace_id") for the warning message
 */
export function warnIfNotUuidV7(uuidStr: string, idType: string): void {
  const version = getUuidVersion(uuidStr);
  if (version !== null && version !== 7) {
    console.warn(
      `LangSmith now uses UUID v7 for ${idType}. The provided ${idType} ` +
        `'${uuidStr}' is UUID v${version}. ` +
        `Please migrate to using UUID v7. ` +
        `Future versions will require UUID v7.`
    );
  }
}
