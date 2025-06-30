import type { OTELSpanContext } from "./types.js";

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

export function createOtelSpanContextFromRun(run: {
  trace_id?: string;
  id: string;
}): OTELSpanContext {
  const traceId = getOtelTraceIdFromUuid(run.trace_id ?? run.id);
  const spanId = getOtelSpanIdFromUuid(run.id);
  return {
    traceId,
    spanId,
    isRemote: false,
    traceFlags: 1, // SAMPLED
  };
}
