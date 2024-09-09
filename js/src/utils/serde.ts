export const CIRCULAR_VALUE_REPLACEMENT_STRING = "[Circular]";

/**
 * JSON.stringify version that handles circular references by replacing them
 * with an object marking them as such ({ result: "[Circular]" }).
 */
export const stringifyForTracing = (value: any): string => {
  const seen = new WeakSet();

  const serializer = (_: string, value: any): any => {
    if (typeof value === "object" && value !== null) {
      if (seen.has(value)) {
        return {
          result: CIRCULAR_VALUE_REPLACEMENT_STRING,
        };
      }
      seen.add(value);
    }
    return value;
  };
  return JSON.stringify(value, serializer);
};
