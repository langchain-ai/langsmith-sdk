/**
 * Deterministic trace sampling, kept consistent across LangSmith SDKs.
 */

import { XXH3_128 } from "./xxhash/xxhash.js";

const SAMPLING_HASH_MODULUS = 1_000_000n;

// Reused across calls: constructing a TextEncoder per hash costs more than the
// hash itself.
const encoder = new TextEncoder();

/**
 * Decide whether `identifier` is sampled in at `samplingRate`.
 *
 * The decision is a pure function of the identifier, so every process and
 * every SDK agrees on it, and a run's create and patch never disagree.
 */
export const isSampledById = (
  identifier: string | null | undefined,
  samplingRate: number | undefined,
): boolean => {
  if (samplingRate === undefined || samplingRate >= 1) {
    return true;
  }
  if (samplingRate <= 0) {
    return false;
  }
  if (identifier === undefined || identifier === null) {
    return true;
  }
  // XXH3-128 over the UTF-8 bytes, matching the Python SDK's `xxhash.xxh3_128`.
  // The identifier is sampled in when its fraction of the modulus falls below
  // the rate, which is also expressed in [0, 1).
  const bucket =
    XXH3_128(encoder.encode(identifier.toLowerCase())) % SAMPLING_HASH_MODULUS;
  return Number(bucket) / Number(SAMPLING_HASH_MODULUS) < samplingRate;
};
