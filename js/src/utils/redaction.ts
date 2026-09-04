import { SECRET_PLACEHOLDER } from "../anonymizer/index.js";
import type { KVMap } from "../schemas.js";

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Mask a value, keeping object key names so a trace shows what was set. */
export function mask(value: unknown): unknown {
  if (isPlainObject(value)) {
    return Object.fromEntries(
      Object.keys(value).map((key) => [key, SECRET_PLACEHOLDER]),
    );
  }
  return SECRET_PLACEHOLDER;
}

/** Copy `entry`, masking values outside `safeKeys`, so unknown keys fail closed. */
export function redactOutside(
  entry: unknown,
  safeKeys: ReadonlySet<string>,
): unknown {
  if (!isPlainObject(entry)) return entry;
  return Object.fromEntries(
    Object.entries(entry).map(([key, value]) => [
      key,
      safeKeys.has(key) ? value : SECRET_PLACEHOLDER,
    ]),
  );
}

/**
 * Apply `redact` to every object argument, since `traceable` shapes a
 * multi-argument call as `{ args: [params, requestOptions] }`.
 */
export function overParams(
  inputs: KVMap,
  redact: (params: KVMap) => KVMap,
): KVMap {
  if (Array.isArray(inputs?.args)) {
    return {
      ...inputs,
      args: inputs.args.map((arg) =>
        isPlainObject(arg) ? redact(arg as KVMap) : arg,
      ),
    };
  }
  return redact(inputs);
}
