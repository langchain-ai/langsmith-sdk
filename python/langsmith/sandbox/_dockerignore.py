"""Docker-compatible ``.dockerignore`` parsing and matching."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Literal

CharacterRange = tuple[int, int]


@dataclass(frozen=True)
class _GlobToken:
    kind: Literal["literal", "star", "globstar", "globstar_segments", "any", "class"]
    value: str = ""
    negated: bool = False
    ranges: tuple[CharacterRange, ...] = ()


@dataclass(frozen=True)
class _DockerIgnoreRule:
    exclusion: bool
    pattern: str
    tokens: tuple[_GlobToken, ...]
    static_prefix: str
    has_slash: bool
    has_glob: bool


def _first_glob_index(pattern: str) -> int:
    cursor = 0
    while cursor < len(pattern):
        if pattern[cursor] == "\\":
            cursor += 2
            continue
        if pattern[cursor] in "*?[":
            return cursor
        cursor += 1
    return -1


class _DockerGlobParser:
    def __init__(self, pattern: str) -> None:
        self._pattern = pattern
        self._characters = list(pattern)
        self._cursor = 0

    def parse(self) -> tuple[_GlobToken, ...]:
        tokens: list[_GlobToken] = []
        while not self._at_end():
            tokens.append(self._parse_token())
        return tuple(tokens)

    def _parse_token(self) -> _GlobToken:
        character = self._consume()
        if character == "\\":
            return self._parse_escaped_literal()
        if character == "*":
            return self._parse_star()
        if character == "?":
            return _GlobToken("any")
        if character == "[":
            return self._parse_character_class()
        return _GlobToken("literal", value=character)

    def _parse_escaped_literal(self) -> _GlobToken:
        if self._at_end():
            raise ValueError(f"invalid trailing escape in pattern {self._pattern}")
        return _GlobToken("literal", value=self._consume())

    def _parse_star(self) -> _GlobToken:
        if self._peek() != "*":
            return _GlobToken("star")
        self._consume()
        if self._peek() == "/":
            self._consume()
            return _GlobToken("globstar_segments")
        return _GlobToken("globstar")

    def _parse_character_class(self) -> _GlobToken:
        negated = self._peek() == "^"
        if negated:
            self._consume()

        ranges: list[CharacterRange] = []
        while not self._at_end() and self._peek() != "]":
            ranges.append(self._parse_character_range())
        if not ranges or self._at_end():
            self._invalid_character_class()
        self._consume()
        return _GlobToken("class", negated=negated, ranges=tuple(ranges))

    def _parse_character_range(self) -> CharacterRange:
        if self._peek() == "-":
            self._invalid_character_class()
        start = self._parse_class_character()
        if self._peek() != "-":
            return start, start

        self._consume()
        if self._at_end() or self._peek() in ("]", "-"):
            self._invalid_character_class()
        end = self._parse_class_character()
        if end < start:
            self._invalid_character_class()
        return start, end

    def _parse_class_character(self) -> int:
        if self._peek() == "\\":
            self._consume()
            if self._at_end():
                self._invalid_character_class()
        return ord(self._consume())

    def _peek(self) -> str | None:
        if self._at_end():
            return None
        return self._characters[self._cursor]

    def _consume(self) -> str:
        character = self._characters[self._cursor]
        self._cursor += 1
        return character

    def _at_end(self) -> bool:
        return self._cursor >= len(self._characters)

    def _invalid_character_class(self) -> None:
        raise ValueError(f"invalid character class in pattern {self._pattern}")


def _matches_docker_glob(value: str, tokens: tuple[_GlobToken, ...]) -> bool:
    characters = list(value)

    @cache
    def match(token_index: int, character_index: int) -> bool:
        if token_index == len(tokens):
            return character_index == len(characters)

        token = tokens[token_index]
        character = (
            characters[character_index] if character_index < len(characters) else None
        )
        if token.kind == "literal":
            return character == token.value and match(
                token_index + 1, character_index + 1
            )
        if token.kind == "any":
            return (
                character is not None
                and character != "/"
                and match(token_index + 1, character_index + 1)
            )
        if token.kind == "star":
            return match(token_index + 1, character_index) or (
                character is not None
                and character != "/"
                and match(token_index, character_index + 1)
            )
        if token.kind == "globstar":
            return match(token_index + 1, character_index) or (
                character is not None and match(token_index, character_index + 1)
            )
        if token.kind == "globstar_segments":
            if match(token_index + 1, character_index):
                return True
            for index in range(character_index, len(characters)):
                if characters[index] == "/" and match(token_index + 1, index + 1):
                    return True
            return False

        code_point = ord(character) if character is not None else None
        in_class = code_point is not None and any(
            start <= code_point <= end for start, end in token.ranges
        )
        return (
            character is not None
            and character != "/"
            and (not in_class if token.negated else in_class)
            and match(token_index + 1, character_index + 1)
        )

    return match(0, 0)


def _rule_matches(rule: _DockerIgnoreRule, path: str) -> bool:
    candidate = path
    while candidate:
        value = candidate if rule.has_slash else candidate.rsplit("/", 1)[-1]
        if _matches_docker_glob(value, rule.tokens):
            return True
        if "/" not in candidate:
            break
        candidate = candidate.rsplit("/", 1)[0]
    return False


class DockerIgnoreMatcher:
    """Match paths relative to a Docker build context against ignore rules."""

    def __init__(self, rules: tuple[_DockerIgnoreRule, ...]) -> None:
        self._rules = rules

    @classmethod
    def parse(cls, contents: str) -> DockerIgnoreMatcher:
        """Parse the contents of a ``.dockerignore`` file."""
        if contents.startswith("\ufeff"):
            contents = contents[1:]

        rules: list[_DockerIgnoreRule] = []
        for raw_line in contents.splitlines():
            if raw_line.startswith("#"):
                continue
            pattern = raw_line.strip()
            if not pattern:
                continue

            exclusion = pattern.startswith("!")
            if exclusion:
                pattern = pattern[1:].strip()
                if not pattern:
                    raise ValueError("invalid empty exclusion pattern")

            absolute = pattern.startswith("/")
            segments: list[str] = []
            for segment in pattern.split("/"):
                if not segment or segment == ".":
                    continue
                if segment == "..":
                    if segments and segments[-1] != "..":
                        segments.pop()
                    elif not absolute:
                        segments.append(segment)
                else:
                    segments.append(segment)
            pattern = "/".join(segments)
            if not pattern or pattern == ".":
                continue

            tokens = _DockerGlobParser(pattern).parse()
            glob_index = _first_glob_index(pattern)
            has_glob = glob_index != -1
            prefix_before_glob = pattern[:glob_index] if has_glob else pattern
            prefix_end = prefix_before_glob.rfind("/")
            rules.append(
                _DockerIgnoreRule(
                    exclusion=exclusion,
                    pattern=pattern,
                    tokens=tokens,
                    static_prefix=(
                        prefix_before_glob[: max(0, prefix_end)]
                        if has_glob
                        else pattern
                    ),
                    has_slash="/" in pattern,
                    has_glob=has_glob,
                )
            )
        return cls(tuple(rules))

    def is_ignored(self, path: str) -> bool:
        """Return whether the last matching rule excludes ``path``."""
        ignored = False
        for rule in self._rules:
            if _rule_matches(rule, path):
                ignored = not rule.exclusion
        return ignored

    def could_include_descendant(self, path: str) -> bool:
        """Return whether an exclusion rule could re-include a child path."""
        for rule in self._rules:
            if not rule.exclusion or not rule.has_slash:
                continue
            if not rule.has_glob:
                if rule.pattern.startswith(f"{path}/"):
                    return True
                continue
            if not rule.static_prefix:
                return True
            if (
                rule.static_prefix == path
                or rule.static_prefix.startswith(f"{path}/")
                or path.startswith(f"{rule.static_prefix}/")
            ):
                return True
        return False
