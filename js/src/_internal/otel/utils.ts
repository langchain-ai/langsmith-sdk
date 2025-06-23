import * as uuid from "uuid";

/**
 * Convert a UUID to an OpenTelemetry trace ID (16 bytes as hex string).
 * This function creates a deterministic trace ID from a UUID.
 * @param uuidStr - The UUID string to convert
 * @returns A 32-character hex string representing the trace ID
 */
export function getOtelTraceIdFromUuid(uuidStr: string): string {
  // Remove hyphens from UUID and take first 32 characters (16 bytes)
  const cleanUuid = uuidStr.replace(/-/g, '');
  // For trace ID, use the full UUID (32 hex chars = 16 bytes)
  return cleanUuid;
}

/**
 * Convert a UUID to an OpenTelemetry span ID (8 bytes as hex string).
 * This function creates a deterministic span ID from a UUID.
 * @param uuidStr - The UUID string to convert  
 * @returns A 16-character hex string representing the span ID
 */
export function getOtelSpanIdFromUuid(uuidStr: string): string {
  // Remove hyphens from UUID and take first 16 characters (8 bytes)
  const cleanUuid = uuidStr.replace(/-/g, '');
  // For span ID, use first 16 hex chars (8 bytes)
  return cleanUuid.substring(0, 16);
}

/**
 * Convert hex string trace ID to integer.
 * @param hexTraceId - 32-character hex string
 * @returns BigInt representation of the trace ID
 */
export function hexTraceIdToBigInt(hexTraceId: string): bigint {
  return BigInt('0x' + hexTraceId);
}

/**
 * Convert hex string span ID to integer.
 * @param hexSpanId - 16-character hex string  
 * @returns BigInt representation of the span ID
 */
export function hexSpanIdToBigInt(hexSpanId: string): bigint {
  return BigInt('0x' + hexSpanId);
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