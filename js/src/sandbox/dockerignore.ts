import { posix as path } from "node:path";

type DockerIgnoreRule = {
  exclusion: boolean;
  pattern: string;
  staticPrefix: string;
  hasSlash: boolean;
  hasGlob: boolean;
};

function normalizePattern(pattern: string): string {
  let normalized = path.normalize(pattern);
  while (normalized.startsWith("/")) {
    normalized = normalized.slice(1);
  }
  while (normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1);
  }
  return normalized;
}

function firstGlobIndex(pattern: string): number {
  for (let i = 0; i < pattern.length; i += 1) {
    if (pattern[i] === "\\") {
      i += 1;
    } else if (
      pattern[i] === "*" ||
      pattern[i] === "?" ||
      pattern[i] === "[" ||
      pattern[i] === "{" ||
      ((pattern[i] === "@" || pattern[i] === "+" || pattern[i] === "!") &&
        pattern[i + 1] === "(")
    ) {
      return i;
    }
  }
  return -1;
}

function validatePattern(pattern: string): void {
  for (let i = 0; i < pattern.length; i += 1) {
    if (pattern[i] === "\\") {
      if (i + 1 === pattern.length) {
        throw new Error(`invalid trailing escape in pattern ${pattern}`);
      }
      i += 1;
      continue;
    }
    if (pattern[i] !== "[") {
      continue;
    }

    i += 1;
    if (pattern[i] === "^") {
      i += 1;
    }
    let members = 0;
    while (i < pattern.length && pattern[i] !== "]") {
      if (pattern[i] === "-") {
        throw new Error(`invalid character class in pattern ${pattern}`);
      }
      let rangeStart = pattern.codePointAt(i) ?? 0;
      if (pattern[i] === "\\") {
        i += 1;
        if (i === pattern.length) {
          throw new Error(`invalid character class in pattern ${pattern}`);
        }
        rangeStart = pattern.codePointAt(i) ?? 0;
      }
      members += 1;
      i += 1;
      if (pattern[i] === "-") {
        i += 1;
        if (i === pattern.length || pattern[i] === "]" || pattern[i] === "-") {
          throw new Error(`invalid character class in pattern ${pattern}`);
        }
        if (pattern[i] === "\\") {
          i += 1;
          if (i === pattern.length) {
            throw new Error(`invalid character class in pattern ${pattern}`);
          }
        }
        const rangeEnd = pattern.codePointAt(i) ?? 0;
        if (rangeEnd < rangeStart) {
          throw new Error(`invalid character class in pattern ${pattern}`);
        }
        i += 1;
      }
    }
    if (members === 0 || i === pattern.length) {
      throw new Error(`invalid character class in pattern ${pattern}`);
    }
  }
}

function prepareNativeGlob(
  value: string,
  pattern: string,
): { value: string; pattern: string } {
  // Adapt Go-style literal escapes and mid-segment globstars before handing
  // matching to the native implementation.
  const escaped = new Map<string, string>();
  let nativePattern = "";
  for (let i = 0; i < pattern.length; i += 1) {
    if (pattern[i] === "\\") {
      const literal = pattern[(i += 1)];
      let replacement = escaped.get(literal);
      if (replacement === undefined) {
        replacement = String.fromCodePoint(0xe000 + escaped.size);
        escaped.set(literal, replacement);
      }
      nativePattern += replacement;
      continue;
    }
    if (
      pattern[i] === "*" &&
      pattern[i + 1] === "*" &&
      pattern[i + 2] === "/" &&
      i > 0 &&
      pattern[i - 1] !== "/"
    ) {
      nativePattern += "*/**/";
      i += 2;
      continue;
    }
    nativePattern += pattern[i];
  }
  let nativeValue = value;
  for (const [literal, replacement] of escaped) {
    nativeValue = nativeValue.split(literal).join(replacement);
  }
  return { value: nativeValue, pattern: nativePattern };
}

function expandCaseFoldedRanges(pattern: string): string[] {
  // On case-insensitive hosts, matchesGlob case-folds magic patterns. Split a
  // lower-case-to-Unicode range before masking ASCII case below.
  for (let i = 0; i + 4 < pattern.length; i += 1) {
    const start = pattern.charCodeAt(i + 1);
    const end = pattern.charCodeAt(i + 3);
    if (
      pattern[i] === "[" &&
      pattern[i + 2] === "-" &&
      pattern[i + 4] === "]" &&
      start >= 0x61 &&
      start <= 0x7a &&
      end > 0x7a
    ) {
      const variants: string[] = [];
      const prefix = pattern.slice(0, i);
      const suffix = pattern.slice(i + 5);
      for (let codePoint = start; codePoint <= 0x7a; codePoint += 1) {
        variants.push(`${prefix}${String.fromCodePoint(codePoint)}${suffix}`);
      }
      variants.push(`${prefix}[{-${pattern[i + 3]}]${suffix}`);
      return variants;
    }
  }
  return [pattern];
}

function makeAsciiCaseSensitive(value: string): string {
  // Docker matching is case-sensitive even when the host filesystem is not.
  // Separate private-use ranges keep native wildcard matching case-sensitive.
  return Array.from(value, (character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    if (codePoint >= 0x61 && codePoint <= 0x7a) {
      return String.fromCodePoint(0xe100 + codePoint - 0x61);
    }
    if (codePoint >= 0x41 && codePoint <= 0x5a) {
      return String.fromCodePoint(0xe200 + codePoint - 0x41);
    }
    return character;
  }).join("");
}

function makeDotfilesVisible(value: string, pattern: boolean): string {
  // matchesGlob hides dotfiles from wildcards. Prefix each path segment so
  // Docker patterns such as `**/*` still include them.
  return value
    .split("/")
    .map((part) => (pattern && part === "**" ? part : `_${part}`))
    .join("/");
}

function matchesDockerGlob(value: string, pattern: string): boolean {
  if (typeof path.matchesGlob !== "function") {
    throw new Error(".dockerignore requires Node.js path.matchesGlob support");
  }
  const native = prepareNativeGlob(value, pattern);
  const nativeValue = makeDotfilesVisible(
    makeAsciiCaseSensitive(native.value),
    false,
  );
  return expandCaseFoldedRanges(native.pattern).some((nativePattern) =>
    path.matchesGlob(
      nativeValue,
      makeDotfilesVisible(makeAsciiCaseSensitive(nativePattern), true),
    ),
  );
}

function ruleMatches(rule: DockerIgnoreRule, path: string): boolean {
  let candidate = path;
  while (candidate) {
    const value = rule.hasSlash
      ? candidate
      : candidate.slice(candidate.lastIndexOf("/") + 1);
    if (matchesDockerGlob(value, rule.pattern)) {
      return true;
    }
    const separator = candidate.lastIndexOf("/");
    if (separator === -1) {
      break;
    }
    candidate = candidate.slice(0, separator);
  }
  return false;
}

/** Parsed `.dockerignore` patterns for paths relative to a build context. */
export class DockerIgnoreMatcher {
  private constructor(private readonly rules: DockerIgnoreRule[]) {}

  static parse(contents: string): DockerIgnoreMatcher {
    const rules: DockerIgnoreRule[] = [];
    for (const rawLine of contents.replace(/^\uFEFF/, "").split(/\r?\n/)) {
      if (rawLine.startsWith("#")) {
        continue;
      }
      let pattern = rawLine.trim();
      if (!pattern) {
        continue;
      }
      const exclusion = pattern.startsWith("!");
      if (exclusion) {
        pattern = pattern.slice(1).trim();
        if (!pattern) {
          throw new Error("invalid empty exclusion pattern");
        }
      }
      pattern = normalizePattern(pattern);
      if (!pattern || pattern === ".") {
        continue;
      }
      validatePattern(pattern);
      const globIndex = firstGlobIndex(pattern);
      const hasGlob = globIndex !== -1;
      const prefixBeforeGlob = hasGlob ? pattern.slice(0, globIndex) : pattern;
      const prefixEnd = prefixBeforeGlob.lastIndexOf("/");
      rules.push({
        exclusion,
        pattern,
        staticPrefix: hasGlob
          ? prefixBeforeGlob.slice(0, Math.max(0, prefixEnd))
          : pattern,
        hasSlash: pattern.includes("/"),
        hasGlob,
      });
    }
    if (rules.length > 0 && typeof path.matchesGlob !== "function") {
      throw new Error(
        ".dockerignore requires Node.js path.matchesGlob support",
      );
    }
    return new DockerIgnoreMatcher(rules);
  }

  isIgnored(path: string): boolean {
    let ignored = false;
    for (const rule of this.rules) {
      if (ruleMatches(rule, path)) {
        ignored = !rule.exclusion;
      }
    }
    return ignored;
  }

  couldIncludeDescendant(path: string): boolean {
    return this.rules.some((rule) => {
      if (!rule.exclusion || !rule.hasSlash) {
        return false;
      }
      if (!rule.hasGlob) {
        return rule.pattern.startsWith(`${path}/`);
      }
      if (!rule.staticPrefix) {
        return true;
      }
      return (
        rule.staticPrefix === path ||
        rule.staticPrefix.startsWith(`${path}/`) ||
        path.startsWith(`${rule.staticPrefix}/`)
      );
    });
  }
}
