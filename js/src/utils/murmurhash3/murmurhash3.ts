// murmurhash3 - a fast non-cryptographic hash function
// https://caolan.uk/src/murmurhash3/about
//
// Original C++ implementation:
// https://github.com/aappleby/smhasher/blob/master/src/MurmurHash3.cpp
// By Austin Appleby
// Public Domain
//
// This JavaScript port:
// Copyright (c) 2025 Caolan McMahon
// MIT License

const c1 = 0xcc9e2d51 >> 0;
const c2 = 0x1b873593 >> 0;

export function murmurhash3_32(key: Uint8Array, seed: number) {
  const tail = (key.length >>> 2) << 2;
  let h1 = seed >> 0;
  // Body
  let i = 0;
  while (i < tail) {
    // Read 32-bit integer into k1.
    // Note: this benchmarks faster than creating
    // a DataView on the underlying key buffer.
    let k1 = key[i] | (key[++i] << 8) | (key[++i] << 16) | (key[++i] << 24);
    ++i;
    k1 = Math.imul(k1, c1);
    k1 = (k1 << 15) | (k1 >>> 17);
    h1 ^= Math.imul(k1, c2);
    h1 = (h1 << 13) | (h1 >>> 19);
    h1 = (Math.imul(h1, 5) + 0xe6546b64) >> 0;
  }
  // Tail
  let k1 = 0;
  switch (
    key.length & 3 // Switch on remaining bytes
  ) {
    case 3:
      k1 ^= key[tail + 2] << 16; // Falls through
    case 2:
      k1 ^= key[tail + 1] << 8; // Falls through
    case 1:
      k1 ^= key[tail];
      k1 = Math.imul(k1, c1);
      k1 = (k1 << 15) | (k1 >>> (32 - 15));
      h1 ^= Math.imul(k1, c2);
  }
  // Finalization
  h1 ^= key.length;
  h1 ^= h1 >>> 16;
  h1 = Math.imul(h1, 0x85ebca6b);
  h1 ^= h1 >>> 13;
  h1 = Math.imul(h1, 0xc2b2ae35);
  h1 ^= h1 >>> 16;
  return h1 >>> 0;
}
