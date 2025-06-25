import * as uuid from "uuid";

/**
 * Get OpenTelemetry trace ID as hex string from UUID.
 * @param uuidStr - The UUID string to convert
 * @returns Hex string representation of the trace ID
 */
export function getOtelTraceIdFromUuid(uuidStr: string): string {
  // Use full UUID hex (like Python's uuid_val.hex)
  return uuidStr.replace(/-/g, "");
}

/**
 * Get OpenTelemetry span ID as hex string from UUID.
 * @param uuidStr - The UUID string to convert
 * @returns Hex string representation of the span ID
 */
export function getOtelSpanIdFromUuid(uuidStr: string): string {
  // Convert UUID string to bytes equivalent (first 8 bytes for span ID)
  // Like Python's uuid_val.bytes[:8].hex()
  const cleanUuid = uuidStr.replace(/-/g, "");
  return cleanUuid.substring(0, 16); // First 8 bytes (16 hex chars)
}

/**
 * Validate and normalize a UUID string.
 * @param uuidStr - The UUID string to validate
 * @returns The normalized UUID string
 * @throws Error if the UUID is invalid
 */
export function validateAndNormalizeUuid(uuidStr: string): string {
  if (!uuid.validate(uuidStr)) {
    throw new Error(`Invalid UUID: ${uuidStr}`);
  }
  return uuidStr;
}
