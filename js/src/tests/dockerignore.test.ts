import { describe, expect, it } from "@jest/globals";
import { DockerIgnoreMatcher } from "../sandbox/dockerignore.js";

describe("DockerIgnoreMatcher", () => {
  it("parses comments, blank lines, and normalized paths", () => {
    const matcher = DockerIgnoreMatcher.parse(
      "\uFEFF# comment\r\n\r\n/root.txt\r\ndirectory/\r\na/../other.txt\r\n../outside.txt\r\n",
    );

    expect(matcher.isIgnored("root.txt")).toBe(true);
    expect(matcher.isIgnored("nested/root.txt")).toBe(false);
    expect(matcher.isIgnored("directory/file.txt")).toBe(true);
    expect(matcher.isIgnored("other.txt")).toBe(true);
    expect(matcher.isIgnored("outside.txt")).toBe(false);
    expect(matcher.isIgnored("included.txt")).toBe(false);
  });

  it("supports Docker wildcards", () => {
    const matcher = DockerIgnoreMatcher.parse(
      ["**/*.tmp", "logs/**/debug-?.[0-9].log", "assets/icon[!0-3].png"].join(
        "\n",
      ),
    );

    expect(matcher.isIgnored("root.tmp")).toBe(true);
    expect(matcher.isIgnored("nested/root.tmp")).toBe(true);
    expect(matcher.isIgnored("logs/debug-a.4.log")).toBe(true);
    expect(matcher.isIgnored("logs/archive/debug-b.7.log")).toBe(true);
    expect(matcher.isIgnored("logs/archive/debug-long.7.log")).toBe(false);
    expect(matcher.isIgnored("assets/icon8.png")).toBe(true);
    expect(matcher.isIgnored("assets/icon2.png")).toBe(false);
  });

  it("matches dotfiles", () => {
    const matcher = DockerIgnoreMatcher.parse("**/*\n!visible.txt");

    expect(matcher.isIgnored(".env")).toBe(true);
    expect(matcher.isIgnored("nested/.env")).toBe(true);
    expect(matcher.isIgnored("visible.txt")).toBe(false);
  });

  it("applies ordered exclusions to ignored directories and their children", () => {
    const matcher = DockerIgnoreMatcher.parse(
      ["vendor", "!vendor/keep.txt", "vendor/private.txt"].join("\n"),
    );

    expect(matcher.isIgnored("vendor")).toBe(true);
    expect(matcher.isIgnored("vendor/drop.txt")).toBe(true);
    expect(matcher.isIgnored("vendor/keep.txt")).toBe(false);
    expect(matcher.isIgnored("vendor/keep.txt/child")).toBe(false);
    expect(matcher.isIgnored("vendor/private.txt")).toBe(true);
    expect(matcher.couldIncludeDescendant("vendor")).toBe(true);
    expect(matcher.couldIncludeDescendant("node_modules")).toBe(false);
  });

  it("uses the last matching pattern", () => {
    const matcher = DockerIgnoreMatcher.parse(
      ["*.md", "!README*.md", "README-secret.md"].join("\n"),
    );

    expect(matcher.isIgnored("guide.md")).toBe(true);
    expect(matcher.isIgnored("README.md")).toBe(false);
    expect(matcher.isIgnored("README-secret.md")).toBe(true);
  });

  it("rejects malformed patterns", () => {
    expect(() => DockerIgnoreMatcher.parse("!")).toThrow(
      "invalid empty exclusion pattern",
    );
    expect(() => DockerIgnoreMatcher.parse("file[abc")).toThrow(
      "invalid character class",
    );
  });
});
