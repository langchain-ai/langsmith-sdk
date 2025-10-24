// Relaxed UUID validation regex (allows any valid UUID format including nil UUIDs)
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function assertUuid(str: string, which?: string): string {
  // Use relaxed regex validation instead of strict uuid.validate()
  // This allows edge cases like nil UUIDs or test UUIDs that might not pass strict validation
  if (!UUID_REGEX.test(str)) {
    const msg =
      which !== undefined
        ? `Invalid UUID for ${which}: ${str}`
        : `Invalid UUID: ${str}`;
    throw new Error(msg);
  }
  return str;
}
