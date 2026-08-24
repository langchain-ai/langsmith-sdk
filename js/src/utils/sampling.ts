/**
 * Deterministic trace sampling, kept consistent across LangSmith SDKs.
 */

const SAMPLING_HASH_MODULUS = 1_000_000n;
const FNV_64_OFFSET_BASIS = 14_695_981_039_346_656_037n;
const FNV_64_PRIME = 1_099_511_628_211n;
const FNV_64_MASK = (1n << 64n) - 1n;

/**
 * Compute the 64-bit FNV-1a hash of a string.
 *
 * Implemented explicitly so the result matches other SDKs byte-for-byte,
 * keeping sampling decisions consistent across SDKs.
 */
const fnv1a64 = (value: string): bigint => {
  let hashValue = FNV_64_OFFSET_BASIS;
  for (let i = 0; i < value.length; i += 1) {
    hashValue ^= BigInt(value.charCodeAt(i));
    hashValue = (hashValue * FNV_64_PRIME) & FNV_64_MASK;
  }
  return hashValue;
};

/**
 * Decide whether `identifier` is sampled in at `samplingRate`.
 *
 * The decision is a pure function of the identifier, so every process and
 * every SDK agrees on it, and a run's create and patch never disagree.
 */
export const isSampledById = (
  identifier: string | null | undefined,
  samplingRate: number | undefined
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
  // The identifier is sampled in when its fraction of the modulus falls below
  // the rate, which is also expressed in [0, 1).
  const bucket = fnv1a64(identifier.toLowerCase()) % SAMPLING_HASH_MODULUS;
  return Number(bucket) / Number(SAMPLING_HASH_MODULUS) < samplingRate;
};
