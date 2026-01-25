/**
 * Gets a number property from an object.
 * @internal
 */
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

/**
 * Checks if a value is iterable.
 * @internal
 */
export function isIterable<T>(value: unknown): value is Iterable<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<typeof Symbol.iterator, unknown>)[
      Symbol.iterator
    ] === "function"
  );
}
