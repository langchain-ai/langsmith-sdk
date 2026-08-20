import { describe, expect, it } from "@jest/globals";
import { DockerIgnoreMatcher } from "../sandbox/dockerignore.js";

// Observable compatibility cases from moby/patternmatcher at
// 5a6d8429a19bb6948a372ff19e86fe83599a04b7. Compile-type and generated-regexp
// assertions are implementation details of the Go matcher and do not apply to
// this implementation, which delegates matching to path.matchesGlob.
const mobyMatchCases: [pattern: string, path: string, ignored: boolean][] = [
  ["**", "file", true],
  ["**", "file/", true],
  ["**/", "file", true],
  ["**/", "file/", true],
  ["**", "/", true],
  ["**/", "/", true],
  ["**", "dir/file", true],
  ["**/", "dir/file", true],
  ["**", "dir/file/", true],
  ["**/", "dir/file/", true],
  ["**/**", "dir/file", true],
  ["**/**", "dir/file/", true],
  ["dir/**", "dir/file", true],
  ["dir/**", "dir/file/", true],
  ["dir/**", "dir/dir2/file", true],
  ["dir/**", "dir/dir2/file/", true],
  ["**/dir", "dir", true],
  ["**/dir", "dir/file", true],
  ["**/dir2/*", "dir/dir2/file", true],
  ["**/dir2/*", "dir/dir2/file/", true],
  ["**/dir2/**", "dir/dir2/dir3/file", true],
  ["**/dir2/**", "dir/dir2/dir3/file/", true],
  ["**file", "file", true],
  ["**file", "dir/file", true],
  ["**/file", "dir/file", true],
  ["**file", "dir/dir/file", true],
  ["**/file", "dir/dir/file", true],
  ["**/file*", "dir/dir/file", true],
  ["**/file*", "dir/dir/file.txt", true],
  ["**/file*txt", "dir/dir/file.txt", true],
  ["**/file*.txt", "dir/dir/file.txt", true],
  ["**/file*.txt*", "dir/dir/file.txt", true],
  ["**/**/*.txt", "dir/dir/file.txt", true],
  ["**/**/*.txt2", "dir/dir/file.txt", false],
  ["**/*.txt", "file.txt", true],
  ["**/**/*.txt", "file.txt", true],
  ["a**/*.txt", "a/file.txt", true],
  ["a**/*.txt", "a/dir/file.txt", true],
  ["a**/*.txt", "a/dir/dir/file.txt", true],
  ["a/*.txt", "a/dir/file.txt", false],
  ["a/*.txt", "a/file.txt", true],
  ["a/*.txt**", "a/file.txt", true],
  ["a[b-d]e", "ae", false],
  ["a[b-d]e", "ace", true],
  ["a[b-d]e", "aae", false],
  ["a[^b-d]e", "aze", true],
  [".*", ".foo", true],
  [".*", "foo", false],
  ["abc.def", "abcdef", false],
  ["abc.def", "abc.def", true],
  ["abc.def", "abcZdef", false],
  ["abc?def", "abcZdef", true],
  ["abc?def", "abcdef", false],
  ["a\\\\", "a\\", true],
  ["**/foo/bar", "foo/bar", true],
  ["**/foo/bar", "dir/foo/bar", true],
  ["**/foo/bar", "dir/dir2/foo/bar", true],
  ["abc/**", "abc", false],
  ["abc/**", "abc/def", true],
  ["abc/**", "abc/def/ghi", true],
  ["**/.foo", ".foo", true],
  ["**/.foo", "bar.foo", false],
  ["a(b)c/def", "a(b)c/def", true],
  ["a(b)c/def", "a(b)c/xyz", false],
  ["a.|)$(}+{bc", "a.|)$(}+{bc", true],
  [
    "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
    "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
    true,
  ],
  [
    "dist/*.whl",
    "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
    true,
  ],
  ["a\\*b", "a*b", true],
];

const mobyFilepathMatchCases: [
  pattern: string,
  path: string,
  ignored: boolean,
][] = [
  ["abc", "abc", true],
  ["*", "abc", true],
  ["*c", "abc", true],
  ["a*", "a", true],
  ["a*", "abc", true],
  ["a*", "ab/c", true],
  ["a*/b", "abc/b", true],
  ["a*/b", "a/c/b", false],
  ["a*b*c*d*e*/f", "axbxcxdxe/f", true],
  ["a*b*c*d*e*/f", "axbxcxdxexxx/f", true],
  ["a*b*c*d*e*/f", "axbxcxdxe/xxx/f", false],
  ["a*b*c*d*e*/f", "axbxcxdxexxx/fff", false],
  ["a*b?c*x", "abxbbxdbxebxczzx", true],
  ["a*b?c*x", "abxbbxdbxebxczzy", false],
  ["ab[c]", "abc", true],
  ["ab[b-d]", "abc", true],
  ["ab[e-g]", "abc", false],
  ["ab[^c]", "abc", false],
  ["ab[^b-d]", "abc", false],
  ["ab[^e-g]", "abc", true],
  ["a\\*b", "a*b", true],
  ["a\\*b", "ab", false],
  ["a?b", "a☺b", true],
  ["a[^a]b", "a☺b", true],
  ["a???b", "a☺b", false],
  ["a[^a][^a][^a]b", "a☺b", false],
  ["[a-ζ]*", "α", true],
  ["*[a-ζ]", "A", false],
  ["a?b", "a/b", false],
  ["a*b", "a/b", false],
  ["[\\]a]", "]", true],
  ["[\\-]", "-", true],
  ["[x\\-]", "x", true],
  ["[x\\-]", "-", true],
  ["[x\\-]", "z", false],
  ["[\\-x]", "x", true],
  ["[\\-x]", "-", true],
  ["[\\-x]", "a", false],
  ["*x", "xxx", true],
];

describe("DockerIgnoreMatcher", () => {
  it("parses comments, blank lines, and normalized paths", () => {
    const matcher = DockerIgnoreMatcher.parse(
      "\uFEFF# comment\r\n\r\n/root.txt\r\ndirectory/\r\na/../other.txt\r\n../outside.txt\r\n",
    );

    expect(matcher.isIgnored("root.txt")).toBe(true);
    expect(matcher.isIgnored("nested/root.txt")).toBe(true);
    expect(matcher.isIgnored("directory/file.txt")).toBe(true);
    expect(matcher.isIgnored("nested/directory/file.txt")).toBe(true);
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
    expect(DockerIgnoreMatcher.parse("*.go").isIgnored("FILE.GO")).toBe(false);
  });

  it("uses native matchesGlob syntax", () => {
    const matcher = DockerIgnoreMatcher.parse(
      "*.{js,ts}\n@(foo|bar)\n*\n!@(foo|bar)/keep.txt",
    );

    expect(matcher.isIgnored("file.js")).toBe(true);
    expect(matcher.isIgnored("file.ts")).toBe(true);
    expect(matcher.isIgnored("foo")).toBe(true);
    expect(matcher.isIgnored("bar")).toBe(true);
    expect(matcher.isIgnored("foo/keep.txt")).toBe(false);
    expect(matcher.couldIncludeDescendant("foo")).toBe(true);
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

  describe("moby/patternmatcher compatibility", () => {
    it.each([...mobyMatchCases, ...mobyFilepathMatchCases])(
      "matches pattern %j against %j",
      (pattern, path, ignored) => {
        expect(DockerIgnoreMatcher.parse(pattern).isIgnored(path)).toBe(
          ignored,
        );
      },
    );

    it.each([
      [["!fileutils.go", "*.go"], "fileutils.go", true],
      [["docs", "!docs/README.md"], "docs/README.md", false],
      [["docs/", "!docs/README.md"], "docs/README.md", false],
      [["docs/*", "!docs/README.md"], "docs/README.md", false],
      [["*.go", "!fileutils.go"], "fileutils.go", false],
      [["**", "!util/docker/web"], "util/docker/web/foo", false],
      [
        ["**", "!util/docker/web", "util/docker/web/foo"],
        "util/docker/web/foo",
        true,
      ],
      [
        ["**", "!dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl"],
        "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
        false,
      ],
      [
        ["**", "!dist/*.whl"],
        "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
        false,
      ],
    ] as [patterns: string[], path: string, ignored: boolean][])(
      "applies ordered patterns %j to %j",
      (patterns, path, ignored) => {
        expect(
          DockerIgnoreMatcher.parse(patterns.join("\n")).isIgnored(path),
        ).toBe(ignored);
      },
    );

    it("preprocesses ignore-file lines like moby/ignorefile", () => {
      const matcher = DockerIgnoreMatcher.parse(`test1
/test2
/a/file/here

lastfile
# this is a comment
! /inverted/abs/path`);

      expect(matcher.isIgnored("test1")).toBe(true);
      expect(matcher.isIgnored("test2")).toBe(true);
      expect(matcher.isIgnored("a/file/here")).toBe(true);
      expect(matcher.isIgnored("lastfile")).toBe(true);
      expect(matcher.isIgnored("inverted/abs/path")).toBe(false);
      const inverseMatcher = DockerIgnoreMatcher.parse(
        "**\n! /inverted/abs/path",
      );
      expect(inverseMatcher.isIgnored("other/path")).toBe(true);
      expect(inverseMatcher.isIgnored("inverted/abs/path")).toBe(false);
      expect(DockerIgnoreMatcher.parse("").isIgnored("any/path")).toBe(false);
      expect(DockerIgnoreMatcher.parse("*.go").isIgnored(".")).toBe(false);
      expect(
        DockerIgnoreMatcher.parse("docs\nconfig\n\n").isIgnored("docs"),
      ).toBe(true);
      expect(
        DockerIgnoreMatcher.parse("docs\n  !docs/README.md  ").isIgnored(
          "docs/README.md",
        ),
      ).toBe(false);
    });

    it.each([
      "[]a]",
      "[-]",
      "[x-]",
      "[-x]",
      "\\",
      "[a-b-c]",
      "[",
      "[^",
      "[^bc",
      "a[",
      "[Local-Only]/",
    ])("rejects malformed upstream pattern %j", (pattern) => {
      expect(() => DockerIgnoreMatcher.parse(pattern)).toThrow();
      expect(() => DockerIgnoreMatcher.parse(pattern)).toThrow();
    });

    it.each(["!", "! "])(
      "rejects the empty exclusion pattern %j",
      (pattern) => {
        expect(() => DockerIgnoreMatcher.parse(pattern)).toThrow();
      },
    );
  });
});
