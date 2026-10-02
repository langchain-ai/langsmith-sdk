type CharacterRange = [start: number, end: number];

type GlobToken =
  | { type: "literal"; value: string }
  | { type: "star" }
  | { type: "globstar" }
  | { type: "globstarSegments" }
  | { type: "any" }
  | { type: "class"; negated: boolean; ranges: CharacterRange[] };

type DockerIgnoreRule = {
  exclusion: boolean;
  pattern: string;
  tokens: GlobToken[];
  staticPrefix: string;
  hasSlash: boolean;
  hasGlob: boolean;
};

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

class DockerGlobParser {
  private readonly characters: string[];

  private cursor = 0;

  constructor(private readonly pattern: string) {
    this.characters = Array.from(pattern);
  }

  parse(): GlobToken[] {
    const tokens: GlobToken[] = [];
    while (!this.atEnd()) {
      tokens.push(this.parseToken());
    }
    return tokens;
  }

  private parseToken(): GlobToken {
    const character = this.consume();
    if (character === "\\") {
      return this.parseEscapedLiteral();
    }
    if (character === "*") {
      return this.parseStar();
    }
    if (character === "?") {
      return { type: "any" };
    }
    if (character === "[") {
      return this.parseCharacterClass();
    }
    return { type: "literal", value: character };
  }

  private parseEscapedLiteral(): GlobToken {
    if (this.atEnd()) {
      throw new Error(`invalid trailing escape in pattern ${this.pattern}`);
    }
    return { type: "literal", value: this.consume() };
  }

  private parseStar(): GlobToken {
    if (this.peek() !== "*") {
      return { type: "star" };
    }
    this.consume();
    if (this.peek() === "/") {
      this.consume();
      return { type: "globstarSegments" };
    }
    return { type: "globstar" };
  }

  private parseCharacterClass(): GlobToken {
    const negated = this.peek() === "^";
    if (negated) {
      this.consume();
    }

    const ranges: CharacterRange[] = [];
    while (!this.atEnd() && this.peek() !== "]") {
      ranges.push(this.parseCharacterRange());
    }
    if (ranges.length === 0 || this.atEnd()) {
      this.invalidCharacterClass();
    }
    this.consume();
    return { type: "class", negated, ranges };
  }

  private parseCharacterRange(): CharacterRange {
    if (this.peek() === "-") {
      this.invalidCharacterClass();
    }
    const start = this.parseClassCharacter();
    if (this.peek() !== "-") {
      return [start, start];
    }

    this.consume();
    if (this.atEnd() || this.peek() === "]" || this.peek() === "-") {
      this.invalidCharacterClass();
    }
    const end = this.parseClassCharacter();
    if (end < start) {
      this.invalidCharacterClass();
    }
    return [start, end];
  }

  private parseClassCharacter(): number {
    if (this.peek() === "\\") {
      this.consume();
      if (this.atEnd()) {
        this.invalidCharacterClass();
      }
    }
    return this.consume().codePointAt(0) ?? 0;
  }

  private peek(): string | undefined {
    return this.characters[this.cursor];
  }

  private consume(): string {
    return this.characters[this.cursor++];
  }

  private atEnd(): boolean {
    return this.cursor >= this.characters.length;
  }

  private invalidCharacterClass(): never {
    throw new Error(`invalid character class in pattern ${this.pattern}`);
  }
}

function matchesDockerGlob(value: string, tokens: GlobToken[]): boolean {
  const characters = Array.from(value);
  const memo = new Map<string, boolean>();

  const match = (tokenIndex: number, characterIndex: number): boolean => {
    const key = `${tokenIndex}:${characterIndex}`;
    const cached = memo.get(key);
    if (cached !== undefined) {
      return cached;
    }

    const token = tokens[tokenIndex];
    let matched: boolean;
    if (token === undefined) {
      matched = characterIndex === characters.length;
    } else if (token.type === "literal") {
      matched =
        characters[characterIndex] === token.value &&
        match(tokenIndex + 1, characterIndex + 1);
    } else if (token.type === "any") {
      matched =
        characters[characterIndex] !== undefined &&
        characters[characterIndex] !== "/" &&
        match(tokenIndex + 1, characterIndex + 1);
    } else if (token.type === "star") {
      matched =
        match(tokenIndex + 1, characterIndex) ||
        (characters[characterIndex] !== undefined &&
          characters[characterIndex] !== "/" &&
          match(tokenIndex, characterIndex + 1));
    } else if (token.type === "globstar") {
      matched =
        match(tokenIndex + 1, characterIndex) ||
        (characterIndex < characters.length &&
          match(tokenIndex, characterIndex + 1));
    } else if (token.type === "globstarSegments") {
      matched = match(tokenIndex + 1, characterIndex);
      for (let i = characterIndex; !matched && i < characters.length; i += 1) {
        if (characters[i] === "/") {
          matched = match(tokenIndex + 1, i + 1);
        }
      }
    } else {
      const codePoint = characters[characterIndex]?.codePointAt(0);
      const inClass =
        codePoint !== undefined &&
        token.ranges.some(
          ([start, end]) => codePoint >= start && codePoint <= end,
        );
      matched =
        codePoint !== undefined &&
        characters[characterIndex] !== "/" &&
        (token.negated ? !inClass : inClass) &&
        match(tokenIndex + 1, characterIndex + 1);
    }

    memo.set(key, matched);
    return matched;
  };

  return match(0, 0);
}

function ruleMatches(rule: DockerIgnoreRule, path: string): boolean {
  let candidate = path;
  while (candidate) {
    const value = rule.hasSlash
      ? candidate
      : candidate.slice(candidate.lastIndexOf("/") + 1);
    if (matchesDockerGlob(value, rule.tokens)) {
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

      const absolute = pattern.startsWith("/");
      const segments: string[] = [];
      for (const segment of pattern.split("/")) {
        if (!segment || segment === ".") {
          continue;
        }
        if (segment === "..") {
          if (segments.length > 0 && segments.at(-1) !== "..") {
            segments.pop();
          } else if (!absolute) {
            segments.push(segment);
          }
        } else {
          segments.push(segment);
        }
      }
      pattern = segments.join("/");
      if (!pattern || pattern === ".") {
        continue;
      }
      const tokens = new DockerGlobParser(pattern).parse();
      const globIndex = firstGlobIndex(pattern);
      const hasGlob = globIndex !== -1;
      const prefixBeforeGlob = hasGlob ? pattern.slice(0, globIndex) : pattern;
      const prefixEnd = prefixBeforeGlob.lastIndexOf("/");
      rules.push({
        exclusion,
        pattern,
        tokens,
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
