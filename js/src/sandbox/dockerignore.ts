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
    } else if (pattern[i] === "*" || pattern[i] === "?" || pattern[i] === "[") {
      return i;
    }
  }
  return -1;
}

function validatePattern(pattern: string): void {
  let inCharacterClass = false;
  for (let i = 0; i < pattern.length; i += 1) {
    if (pattern[i] === "\\") {
      i += 1;
    } else if (pattern[i] === "[") {
      inCharacterClass = true;
    } else if (pattern[i] === "]") {
      inCharacterClass = false;
    }
  }
  if (inCharacterClass) {
    throw new Error(`invalid character class in pattern ${pattern}`);
  }
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
  return path.matchesGlob(
    makeDotfilesVisible(value, false),
    makeDotfilesVisible(pattern, true),
  );
}

function ruleMatches(rule: DockerIgnoreRule, path: string): boolean {
  let candidate = path;
  while (candidate) {
    if (matchesDockerGlob(candidate, rule.pattern)) {
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
