export function getNumberProperty(
  obj: unknown,
  key: string
): number | undefined {
  if (!obj || typeof obj !== "object" || !(key in obj)) {
    return undefined;
  }
  const value = Reflect.get(obj, key);
  return typeof value === "number" ? value : undefined;
}
