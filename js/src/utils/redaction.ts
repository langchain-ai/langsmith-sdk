import { SECRET_PLACEHOLDER } from "../anonymizer/index.js";
import type { KVMap } from "../schemas.js";

/**
 * Request params are shallow; a cyclic or pathological payload must not turn
 * tracing into a hang.
 */
const MAX_DEPTH = 12;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Mask a value, keeping object key names so a trace still shows what was set.
 */
export function mask(value: unknown): unknown {
  if (isPlainObject(value)) {
    return Object.fromEntries(
      Object.keys(value).map((key) => [key, SECRET_PLACEHOLDER]),
    );
  }
  return SECRET_PLACEHOLDER;
}

/**
 * Copy `entry` with every value outside `safeKeys` masked.
 *
 * Keys keep their names, so a trace still shows the field was set, and a
 * credential field the provider adds later is masked by default rather than
 * exported.
 */
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
 * Recursively mask the value of any object key named in `secretKeys`.
 *
 * Use where a provider hides credentials across several unrelated subtrees and
 * a per-site allowlist would need a new patch every release. Scope it to the
 * config-shaped part of a payload; walking user message content would mask
 * legitimate tool arguments and schema properties.
 */
export function redactKeys(
  value: unknown,
  secretKeys: ReadonlySet<string>,
  depth = 0,
): unknown {
  if (depth > MAX_DEPTH) return SECRET_PLACEHOLDER;
  if (Array.isArray(value)) {
    return value.map((item) => redactKeys(item, secretKeys, depth + 1));
  }
  if (isPlainObject(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        secretKeys.has(key)
          ? mask(item)
          : redactKeys(item, secretKeys, depth + 1),
      ]),
    );
  }
  return value;
}

/**
 * Apply `redact` to the provider params regardless of how `traceable` shaped
 * them.
 *
 * A single-argument call is traced as the params object itself, but any call
 * with a second argument — including the documented `langsmithExtra` option —
 * is traced as `{ args: [params, requestOptions] }`. A `processInputs` that
 * only reads top-level keys silently stops redacting in that case.
 *
 * `redact` is applied to every object argument, so a credential in the request
 * options is masked too.
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
