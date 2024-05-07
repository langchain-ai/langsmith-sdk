import * as uuid from "uuid";

export function assertUuid(str: string): void {
  if (!uuid.validate(str)) {
    throw new Error(`Invalid UUID: ${str}`);
  }
}

export function isValidUuid(str: string): boolean {
  return uuid.validate(str);
}
