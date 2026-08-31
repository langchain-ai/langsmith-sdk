import io
import tarfile

import pytest

from langsmith.sandbox._client import _make_docker_context_tar
from langsmith.sandbox._dockerignore import DockerIgnoreMatcher

# Observable compatibility cases from moby/patternmatcher at
# 5a6d8429a19bb6948a372ff19e86fe83599a04b7. Compile-type and generated-regexp
# assertions are implementation details of the Go matcher and do not apply here.
MOBY_MATCH_CASES = [
    ("**", "file", True),
    ("**", "file/", True),
    ("**/", "file", True),
    ("**/", "file/", True),
    ("**", "/", True),
    ("**/", "/", True),
    ("**", "dir/file", True),
    ("**/", "dir/file", True),
    ("**", "dir/file/", True),
    ("**/", "dir/file/", True),
    ("**/**", "dir/file", True),
    ("**/**", "dir/file/", True),
    ("dir/**", "dir/file", True),
    ("dir/**", "dir/file/", True),
    ("dir/**", "dir/dir2/file", True),
    ("dir/**", "dir/dir2/file/", True),
    ("**/dir", "dir", True),
    ("**/dir", "dir/file", True),
    ("**/dir2/*", "dir/dir2/file", True),
    ("**/dir2/*", "dir/dir2/file/", True),
    ("**/dir2/**", "dir/dir2/dir3/file", True),
    ("**/dir2/**", "dir/dir2/dir3/file/", True),
    ("**file", "file", True),
    ("**file", "dir/file", True),
    ("**/file", "dir/file", True),
    ("**file", "dir/dir/file", True),
    ("**/file", "dir/dir/file", True),
    ("**/file*", "dir/dir/file", True),
    ("**/file*", "dir/dir/file.txt", True),
    ("**/file*txt", "dir/dir/file.txt", True),
    ("**/file*.txt", "dir/dir/file.txt", True),
    ("**/file*.txt*", "dir/dir/file.txt", True),
    ("**/**/*.txt", "dir/dir/file.txt", True),
    ("**/**/*.txt2", "dir/dir/file.txt", False),
    ("**/*.txt", "file.txt", True),
    ("**/**/*.txt", "file.txt", True),
    ("a**/*.txt", "a/file.txt", True),
    ("a**/*.txt", "a/dir/file.txt", True),
    ("a**/*.txt", "a/dir/dir/file.txt", True),
    ("a/*.txt", "a/dir/file.txt", False),
    ("a/*.txt", "a/file.txt", True),
    ("a/*.txt**", "a/file.txt", True),
    ("a[b-d]e", "ae", False),
    ("a[b-d]e", "ace", True),
    ("a[b-d]e", "aae", False),
    ("a[^b-d]e", "aze", True),
    (".*", ".foo", True),
    (".*", "foo", False),
    ("abc.def", "abcdef", False),
    ("abc.def", "abc.def", True),
    ("abc.def", "abcZdef", False),
    ("abc?def", "abcZdef", True),
    ("abc?def", "abcdef", False),
    (r"a\\", "a\\", True),
    ("**/foo/bar", "foo/bar", True),
    ("**/foo/bar", "dir/foo/bar", True),
    ("**/foo/bar", "dir/dir2/foo/bar", True),
    ("abc/**", "abc", False),
    ("abc/**", "abc/def", True),
    ("abc/**", "abc/def/ghi", True),
    ("**/.foo", ".foo", True),
    ("**/.foo", "bar.foo", False),
    ("a(b)c/def", "a(b)c/def", True),
    ("a(b)c/def", "a(b)c/xyz", False),
    ("a.|)$(}+{bc", "a.|)$(}+{bc", True),
    (
        "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
        "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
        True,
    ),
    (
        "dist/*.whl",
        "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
        True,
    ),
    (r"a\*b", "a*b", True),
]

MOBY_FILEPATH_MATCH_CASES = [
    ("abc", "abc", True),
    ("*", "abc", True),
    ("*c", "abc", True),
    ("a*", "a", True),
    ("a*", "abc", True),
    ("a*", "ab/c", True),
    ("a*/b", "abc/b", True),
    ("a*/b", "a/c/b", False),
    ("a*b*c*d*e*/f", "axbxcxdxe/f", True),
    ("a*b*c*d*e*/f", "axbxcxdxexxx/f", True),
    ("a*b*c*d*e*/f", "axbxcxdxe/xxx/f", False),
    ("a*b*c*d*e*/f", "axbxcxdxexxx/fff", False),
    ("a*b?c*x", "abxbbxdbxebxczzx", True),
    ("a*b?c*x", "abxbbxdbxebxczzy", False),
    ("ab[c]", "abc", True),
    ("ab[b-d]", "abc", True),
    ("ab[e-g]", "abc", False),
    ("ab[^c]", "abc", False),
    ("ab[^b-d]", "abc", False),
    ("ab[^e-g]", "abc", True),
    (r"a\*b", "a*b", True),
    (r"a\*b", "ab", False),
    ("a?b", "a☺b", True),
    ("a[^a]b", "a☺b", True),
    ("a???b", "a☺b", False),
    ("a[^a][^a][^a]b", "a☺b", False),
    ("[a-ζ]*", "α", True),
    ("*[a-ζ]", "A", False),
    ("a?b", "a/b", False),
    ("a*b", "a/b", False),
    (r"[\]a]", "]", True),
    (r"[\-]", "-", True),
    (r"[x\-]", "x", True),
    (r"[x\-]", "-", True),
    (r"[x\-]", "z", False),
    (r"[\-x]", "x", True),
    (r"[\-x]", "-", True),
    (r"[\-x]", "a", False),
    ("*x", "xxx", True),
]


@pytest.mark.parametrize(
    ("pattern", "path", "ignored"), MOBY_MATCH_CASES + MOBY_FILEPATH_MATCH_CASES
)
def test_moby_patterns(pattern: str, path: str, ignored: bool) -> None:
    assert DockerIgnoreMatcher.parse(pattern).is_ignored(path) is ignored


def test_preprocesses_ignore_file_lines() -> None:
    matcher = DockerIgnoreMatcher.parse(
        "\ufeff# comment\r\n\r\n/root.txt\r\ndirectory/\r\n"
        "a/../other.txt\r\n../outside.txt\r\n"
    )
    assert matcher.is_ignored("root.txt")
    assert matcher.is_ignored("nested/root.txt")
    assert matcher.is_ignored("directory/file.txt")
    assert matcher.is_ignored("nested/directory/file.txt")
    assert matcher.is_ignored("other.txt")
    assert not matcher.is_ignored("outside.txt")
    assert not matcher.is_ignored("included.txt")


def test_docker_wildcards() -> None:
    matcher = DockerIgnoreMatcher.parse(
        "**/*.tmp\nlogs/**/debug-?.[0-9].log\nassets/icon[^0-3].png"
    )
    assert matcher.is_ignored("root.tmp")
    assert matcher.is_ignored("nested/root.tmp")
    assert matcher.is_ignored("logs/debug-a.4.log")
    assert matcher.is_ignored("logs/archive/debug-b.7.log")
    assert not matcher.is_ignored("logs/archive/debug-long.7.log")
    assert matcher.is_ignored("assets/icon8.png")
    assert not matcher.is_ignored("assets/icon2.png")
    assert not DockerIgnoreMatcher.parse("*.go").is_ignored("FILE.GO")


def test_non_docker_glob_extensions_are_literal() -> None:
    matcher = DockerIgnoreMatcher.parse("*.{js,ts}\n@(foo|bar)")
    assert not matcher.is_ignored("file.js")
    assert not matcher.is_ignored("file.ts")
    assert matcher.is_ignored("file.{js,ts}")
    assert matcher.is_ignored("@(foo|bar)")


def test_matches_dotfiles() -> None:
    matcher = DockerIgnoreMatcher.parse("**/*\n!visible.txt")
    assert matcher.is_ignored(".env")
    assert matcher.is_ignored("nested/.env")
    assert not matcher.is_ignored("visible.txt")


def test_ordered_exclusions_and_descendants() -> None:
    matcher = DockerIgnoreMatcher.parse("vendor\n!vendor/keep.txt\nvendor/private.txt")
    assert matcher.is_ignored("vendor")
    assert matcher.is_ignored("vendor/drop.txt")
    assert not matcher.is_ignored("vendor/keep.txt")
    assert not matcher.is_ignored("vendor/keep.txt/child")
    assert matcher.is_ignored("vendor/private.txt")
    assert matcher.could_include_descendant("vendor")
    assert not matcher.could_include_descendant("node_modules")


@pytest.mark.parametrize(
    ("patterns", "path", "ignored"),
    [
        (["!fileutils.go", "*.go"], "fileutils.go", True),
        (["docs", "!docs/README.md"], "docs/README.md", False),
        (["docs/", "!docs/README.md"], "docs/README.md", False),
        (["docs/*", "!docs/README.md"], "docs/README.md", False),
        (["*.go", "!fileutils.go"], "fileutils.go", False),
        (["**", "!util/docker/web"], "util/docker/web/foo", False),
        (
            ["**", "!util/docker/web", "util/docker/web/foo"],
            "util/docker/web/foo",
            True,
        ),
        (
            ["**", "!dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl"],
            "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
            False,
        ),
        (
            ["**", "!dist/*.whl"],
            "dist/proxy.py-2.4.0rc3.dev36+g08acad9-py3-none-any.whl",
            False,
        ),
    ],
)
def test_ordered_moby_patterns(patterns: list[str], path: str, ignored: bool) -> None:
    matcher = DockerIgnoreMatcher.parse("\n".join(patterns))
    assert matcher.is_ignored(path) is ignored


def test_moby_ignore_file_preprocessing() -> None:
    matcher = DockerIgnoreMatcher.parse(
        "test1\n/test2\n/a/file/here\n\nlastfile\n"
        "# this is a comment\n! /inverted/abs/path"
    )
    assert matcher.is_ignored("test1")
    assert matcher.is_ignored("test2")
    assert matcher.is_ignored("a/file/here")
    assert matcher.is_ignored("lastfile")
    assert not matcher.is_ignored("inverted/abs/path")

    inverse = DockerIgnoreMatcher.parse("**\n! /inverted/abs/path")
    assert inverse.is_ignored("other/path")
    assert not inverse.is_ignored("inverted/abs/path")
    assert not DockerIgnoreMatcher.parse("").is_ignored("any/path")
    assert not DockerIgnoreMatcher.parse("*.go").is_ignored(".")
    assert DockerIgnoreMatcher.parse("docs\nconfig\n\n").is_ignored("docs")
    assert not DockerIgnoreMatcher.parse("docs\n  !docs/README.md  ").is_ignored(
        "docs/README.md"
    )


@pytest.mark.parametrize(
    "pattern",
    [
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
        "!",
        "! ",
    ],
)
def test_rejects_malformed_patterns(pattern: str) -> None:
    with pytest.raises(ValueError):
        DockerIgnoreMatcher.parse(pattern)


def _tar_names(data: bytes) -> set[str]:
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        return set(tar.getnames())


def test_context_tar_respects_dockerignore(tmp_path) -> None:
    (tmp_path / "docker").mkdir()
    (tmp_path / "ignored-dir").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "docker" / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / "included.txt").write_text("included\n")
    (tmp_path / "excluded.txt").write_text("excluded\n")
    (tmp_path / "root-only.txt").write_text("excluded\n")
    (tmp_path / "ignored-dir" / "drop.txt").write_text("excluded\n")
    (tmp_path / "ignored-dir" / "keep.txt").write_text("included\n")
    (tmp_path / "logs" / "debug.log").write_text("excluded\n")
    (tmp_path / "node_modules" / "package.py").write_text("excluded\n")
    (tmp_path / ".dockerignore").write_text(
        "# Ignore generated and local files\n"
        "excluded.txt\n/root-only.txt\nnode_modules\n**/*.log\n"
        "ignored-dir\n!ignored-dir/keep.txt\ndocker\n.dockerignore\n"
    )

    names = _tar_names(_make_docker_context_tar(tmp_path, "docker/Dockerfile"))
    assert {
        ".dockerignore",
        "docker",
        "docker/Dockerfile",
        "ignored-dir/keep.txt",
        "included.txt",
        "logs",
    } <= names
    assert {
        "excluded.txt",
        "root-only.txt",
        "ignored-dir",
        "ignored-dir/drop.txt",
        "logs/debug.log",
        "node_modules",
        "node_modules/package.py",
    }.isdisjoint(names)

    (tmp_path / ".dockerignore").write_text("invalid[")
    fallback_names = _tar_names(_make_docker_context_tar(tmp_path, "docker/Dockerfile"))
    assert {
        "excluded.txt",
        "ignored-dir/drop.txt",
        "logs/debug.log",
        "node_modules/package.py",
    } <= fallback_names

    (tmp_path / ".dockerignore").write_text("excluded.txt\n")
    (tmp_path / "docker" / "Dockerfile.dockerignore").write_text(
        "included.txt\ndocker/Dockerfile.dockerignore\n"
    )
    dockerfile_ignore_names = _tar_names(
        _make_docker_context_tar(tmp_path, "docker/Dockerfile")
    )
    assert "excluded.txt" in dockerfile_ignore_names
    assert "docker/Dockerfile.dockerignore" in dockerfile_ignore_names
    assert "included.txt" not in dockerfile_ignore_names
