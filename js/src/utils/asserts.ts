export function isPromiseMethod(
  x: string | symbol
): x is "then" | "catch" | "finally" {
  if (x === "then" || x === "catch" || x === "finally") {
    return true;
  }
  return false;
}

export function isKVMap(x: unknown): x is Record<string, unknown> {
  if (typeof x !== "object" || x == null) {
    return false;
  }

  const prototype = Object.getPrototypeOf(x);
  return (
    (prototype === null ||
      prototype === Object.prototype ||
      Object.getPrototypeOf(prototype) === null) &&
    !(Symbol.toStringTag in x) &&
    !(Symbol.iterator in x)
  );
}
export const isAsyncIterable = (x: unknown): x is AsyncIterable<unknown> =>
  x != null &&
  typeof x === "object" &&
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  typeof (x as any)[Symbol.asyncIterator] === "function";

export const isIteratorLike = (x: unknown): x is Iterator<unknown> =>
  x != null &&
  typeof x === "object" &&
  "next" in x &&
  typeof x.next === "function";

const GeneratorFunction = function* () {}.constructor;
export const isGenerator = (x: unknown): x is Generator =>
  // eslint-disable-next-line no-instanceof/no-instanceof
  x != null && typeof x === "function" && x instanceof GeneratorFunction;

export const isThenable = (x: unknown): x is Promise<unknown> =>
  x != null &&
  typeof x === "object" &&
  "then" in x &&
  typeof x.then === "function";

export const isReadableStream = (x: unknown): x is ReadableStream =>
  x != null &&
  typeof x === "object" &&
  "getReader" in x &&
  typeof x.getReader === "function";
