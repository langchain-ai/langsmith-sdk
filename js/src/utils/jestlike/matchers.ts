// Levenshtein distance implementation
function levenshteinDistance(a: string, b: string): number {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;

  const matrix = Array(b.length + 1)
    .fill(null)
    .map(() => Array(a.length + 1).fill(null));

  for (let i = 0; i <= a.length; i++) matrix[0][i] = i;
  for (let j = 0; j <= b.length; j++) matrix[j][0] = j;

  for (let j = 1; j <= b.length; j++) {
    for (let i = 1; i <= a.length; i++) {
      const substitutionCost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[j][i] = Math.min(
        matrix[j][i - 1] + 1,
        matrix[j - 1][i] + 1,
        matrix[j - 1][i - 1] + substitutionCost
      );
    }
  }
  return matrix[b.length][a.length];
}

export type RelativeCloseToMatcherOptions = {
  threshold?: number;
  algorithm?: "levenshtein";
};

export async function toBeRelativeCloseTo(
  received: string,
  expected: string,
  options: RelativeCloseToMatcherOptions = {}
) {
  const { threshold = 0.1, algorithm = "levenshtein" } = options;

  if (threshold < 0 || threshold > 1) {
    throw new Error(
      "Relative distance is normalized, and threshold must be between 0 and 1."
    );
  }

  let distance: number;
  let maxLength: number;

  switch (algorithm) {
    case "levenshtein":
      distance = levenshteinDistance(received, expected);
      maxLength = Math.max(received.length, expected.length);
      break;
    default:
      throw new Error(`Unsupported algorithm: ${algorithm}`);
  }

  // Calculate relative distance (normalized between 0 and 1)
  const relativeDistance = maxLength === 0 ? 0 : distance / maxLength;
  const pass = relativeDistance <= threshold;

  return {
    pass,
    message: () =>
      pass
        ? `Expected "${received}" not to be relatively close to "${expected}" (threshold: ${threshold}, actual distance: ${relativeDistance})`
        : `Expected "${received}" to be relatively close to "${expected}" (threshold: ${threshold}, actual distance: ${relativeDistance})`,
  };
}

export type AbsoluteCloseToMatcherOptions = {
  threshold?: number;
  algorithm?: "levenshtein";
};

export async function toBeAbsoluteCloseTo(
  received: string,
  expected: string,
  options: AbsoluteCloseToMatcherOptions = {}
) {
  const { threshold = 3, algorithm = "levenshtein" } = options;

  let distance: number;

  switch (algorithm) {
    case "levenshtein":
      distance = levenshteinDistance(received, expected);
      break;
    default:
      throw new Error(`Unsupported algorithm: ${algorithm}`);
  }

  const pass = distance <= threshold;

  return {
    pass,
    message: () =>
      pass
        ? `Expected "${received}" not to be absolutely close to "${expected}" (threshold: ${threshold}, actual distance: ${distance})`
        : `Expected "${received}" to be absolutely close to "${expected}" (threshold: ${threshold}, actual distance: ${distance})`,
  };
}

export type SemanticCloseToMatcherOptions = {
  embeddings: { embedQuery: (query: string) => number[] | Promise<number[]> };
  threshold?: number;
  algorithm?: "cosine" | "dot-product";
};

export async function toBeSemanticCloseTo(
  received: string,
  expected: string,
  options: SemanticCloseToMatcherOptions
) {
  const { threshold = 0.2, embeddings, algorithm = "cosine" } = options;

  // Get embeddings for both strings
  const [receivedEmbedding, expectedEmbedding] = await Promise.all([
    embeddings.embedQuery(received),
    embeddings.embedQuery(expected),
  ]);

  // Calculate similarity based on chosen algorithm
  let similarity: number;
  switch (algorithm) {
    case "cosine": {
      // Compute cosine similarity
      const dotProduct = receivedEmbedding.reduce(
        (sum, a, i) => sum + a * expectedEmbedding[i],
        0
      );
      const receivedMagnitude = Math.sqrt(
        receivedEmbedding.reduce((sum, a) => sum + a * a, 0)
      );
      const expectedMagnitude = Math.sqrt(
        expectedEmbedding.reduce((sum, a) => sum + a * a, 0)
      );
      similarity = dotProduct / (receivedMagnitude * expectedMagnitude);
      break;
    }
    case "dot-product": {
      // Compute dot product similarity
      similarity = receivedEmbedding.reduce(
        (sum, a, i) => sum + a * expectedEmbedding[i],
        0
      );
      break;
    }
    default:
      throw new Error(`Unsupported algorithm: ${algorithm}`);
  }

  const pass = similarity >= 1 - threshold;

  return {
    pass,
    message: () =>
      pass
        ? `Expected "${received}" not to be semantically close to "${expected}" (threshold: ${threshold}, similarity: ${similarity})`
        : `Expected "${received}" to be semantically close to "${expected}" (threshold: ${threshold}, similarity: ${similarity})`,
  };
}
