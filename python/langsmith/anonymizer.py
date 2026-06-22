import re  # noqa
import inspect
from abc import abstractmethod
from collections import defaultdict, deque
from typing import Any, Callable, Optional, TypedDict, Union


class _ExtractOptions(TypedDict):
    max_depth: Optional[int]
    """
    Maximum depth to traverse to to extract string nodes
    """


class StringNode(TypedDict):
    """String node extracted from the data."""

    value: str
    """String value."""

    path: list[Union[str, int]]
    """Path to the string node in the data."""


def _extract_string_nodes(data: Any, options: _ExtractOptions) -> list[StringNode]:
    max_depth = options.get("max_depth") or 10

    queue: deque[tuple[Any, int, list[Union[str, int]]]] = deque([(data, 0, [])])
    result: list[StringNode] = []
    seen: set[int] = set()

    while queue:
        task = queue.popleft()
        if task is None:
            continue
        value, depth, path = task

        if isinstance(value, (dict, defaultdict)):
            if depth >= max_depth:
                continue
            obj_id = id(value)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            for key, nested_value in value.items():
                queue.append((nested_value, depth + 1, path + [key]))
        elif isinstance(value, list):
            if depth >= max_depth:
                continue
            obj_id = id(value)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            for i, item in enumerate(value):
                queue.append((item, depth + 1, path + [i]))
        elif isinstance(value, str):
            result.append(StringNode(value=value, path=path))

    return result


class StringNodeProcessor:
    """Processes a list of string nodes for masking."""

    @abstractmethod
    def mask_nodes(self, nodes: list[StringNode]) -> list[StringNode]:
        """Accept and return a list of string nodes to be masked."""


class ReplacerOptions(TypedDict):
    """Configuration options for replacing sensitive data."""

    max_depth: Optional[int]
    """Maximum depth to traverse to to extract string nodes."""

    deep_clone: Optional[bool]
    """Deep clone the data before replacing."""


class StringNodeRule(TypedDict):
    """Declarative rule used for replacing sensitive data."""

    pattern: re.Pattern
    """Regex pattern to match."""

    replace: Optional[str]
    """Replacement value. Defaults to `[redacted]` if not specified."""


class RuleNodeProcessor(StringNodeProcessor):
    """String node processor that uses a list of rules to replace sensitive data."""

    rules: list[StringNodeRule]
    """List of rules to apply for replacing sensitive data.

    Each rule is a StringNodeRule, which contains a regex pattern to match
    and an optional replacement string.
    """

    def __init__(
        self,
        rules: list[StringNodeRule],
        *,
        prefilter: Optional[Callable[[str], bool]] = None,
    ):
        """Initialize the processor with a list of rules."""
        self.rules = [
            {
                "pattern": (
                    rule["pattern"]
                    if isinstance(rule["pattern"], re.Pattern)
                    else re.compile(rule["pattern"])
                ),
                "replace": (
                    rule["replace"]
                    if isinstance(rule.get("replace"), str)
                    else "[redacted]"
                ),
            }
            for rule in rules
        ]
        self.prefilter = prefilter
        # Combined-regex optimization: when all rules share the same replacement
        # string and no rule uses capture groups, merge them into a single
        # alternation regex so each node is matched with one .sub() call instead
        # of N.
        self._combined_regex: Optional[re.Pattern] = None
        self._combined_replace: Optional[str] = None
        replacements = {r["replace"] for r in self.rules}
        if (
            len(replacements) == 1
            and not any(
                r"\g<" in r["replace"] or r"\1" in r["replace"]
                for r in self.rules
            )
            and not any(
                "(" in r["pattern"].pattern
                and not r["pattern"].pattern.startswith("(?:")
                for r in self.rules
            )
        ):
            repl = self.rules[0]["replace"]
            # Check none of the patterns have capture groups (non-capturing
            # groups (?:...) are fine).
            has_capture = False
            for r in self.rules:
                pat = r["pattern"].pattern
                i = 0
                while i < len(pat):
                    if pat[i] == "(" and (
                        i + 2 >= len(pat) or pat[i : i + 3] != "(?:"
                    ):
                        has_capture = True
                        break
                    i += 1
            if not has_capture:
                self._combined_regex = re.compile(
                    "|".join(
                        f"(?:{r['pattern'].pattern})" for r in self.rules
                    )
                )
                self._combined_replace = repl

    def mask_nodes(self, nodes: list[StringNode]) -> list[StringNode]:
        """Mask nodes using the rules."""
        result = []
        for item in nodes:
            if self.prefilter is not None and not self.prefilter(item["value"]):
                continue
            new_value = item["value"]
            if self._combined_regex is not None:
                new_value = self._combined_regex.sub(
                    self._combined_replace, new_value
                )
            else:
                for rule in self.rules:
                    new_value = rule["pattern"].sub(rule["replace"], new_value)
            if new_value != item["value"]:
                result.append(StringNode(value=new_value, path=item["path"]))
        return result


class CallableNodeProcessor(StringNodeProcessor):
    """String node processor that uses a callable function to replace sensitive data."""

    func: Union[Callable[[str], str], Callable[[str, list[Union[str, int]]], str]]
    """The callable function used to replace sensitive data.
    
    It can be either a function that takes a single string argument and returns a string,
    or a function that takes a string and a list of path elements (strings or integers) 
    and returns a string."""

    accepts_path: bool
    """Indicates whether the callable function accepts a path argument.
    
    If True, the function expects two arguments: the string to be processed and the path to that string.
    If False, the function expects only the string to be processed."""

    def __init__(
        self,
        func: Union[Callable[[str], str], Callable[[str, list[Union[str, int]]], str]],
    ):
        """Initialize the processor with a callable function."""
        self.func = func
        self.accepts_path = len(inspect.signature(func).parameters) == 2

    def mask_nodes(self, nodes: list[StringNode]) -> list[StringNode]:
        """Mask nodes using the callable function."""
        retval: list[StringNode] = []
        for node in nodes:
            candidate = (
                self.func(node["value"], node["path"])  # type: ignore[call-arg]
                if self.accepts_path
                else self.func(node["value"])  # type: ignore[call-arg]
            )
            if candidate != node["value"]:
                retval.append(StringNode(value=candidate, path=node["path"]))
        return retval


ReplacerType = Union[
    Callable[[str, list[Union[str, int]]], str],
    list[StringNodeRule],
    StringNodeProcessor,
]


def _get_node_processor(replacer: ReplacerType) -> StringNodeProcessor:
    if isinstance(replacer, list):
        return RuleNodeProcessor(rules=replacer)
    elif callable(replacer):
        return CallableNodeProcessor(func=replacer)
    else:
        return replacer


def create_anonymizer(
    replacer: ReplacerType,
    *,
    max_depth: Optional[int] = None,
) -> Callable[[Any], Any]:
    """Create an anonymizer function."""
    processor = _get_node_processor(replacer)

    def anonymizer(data: Any) -> Any:
        nodes = _extract_string_nodes(data, {"max_depth": max_depth or 10})
        mutate_value = data

        to_update = processor.mask_nodes(nodes)
        for node in to_update:
            if not node["path"]:
                mutate_value = node["value"]
            else:
                temp = mutate_value
                for part in node["path"][:-1]:
                    temp = temp[part]

                last_part = node["path"][-1]
                temp[last_part] = node["value"]

        return mutate_value

    return anonymizer


SECRET_PLACEHOLDER = "[SECRET_DETECTED]"
"""Replacement token written in place of detected secrets by
:data:`DEFAULT_SECRET_RULES` / :func:`create_secret_anonymizer`."""


DEFAULT_SECRET_RULES: list[StringNodeRule] = [
    # ── Provider API keys (prefix-anchored, case-sensitive) ──────────────────
    # Anthropic
    {
        "pattern": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # OpenAI: project / service-account / admin keys, then legacy `sk-...`
    {
        "pattern": re.compile(r"\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    {"pattern": re.compile(r"\bsk-[A-Za-z0-9]{32,}(?![A-Za-z0-9])"), "replace": SECRET_PLACEHOLDER},
    # LangSmith (keys are multi-segment: lsv2_pt_<key>_<tail> — match the full
    # underscore-delimited tail so none of it leaks past the placeholder)
    {
        "pattern": re.compile(r"\blsv2_(?:pt|sk)_[A-Za-z0-9]{32,}(?:_[A-Za-z0-9]+)*(?![A-Za-z0-9_])"),
        "replace": SECRET_PLACEHOLDER,
    },
    {"pattern": re.compile(r"\bls__[A-Za-z0-9]{16,}(?![A-Za-z0-9])"), "replace": SECRET_PLACEHOLDER},
    # GitHub personal access / app tokens
    {
        "pattern": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}(?![A-Za-z0-9])"),
        "replace": SECRET_PLACEHOLDER,
    },
    {
        "pattern": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}(?![A-Za-z0-9_])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # GitLab personal access token
    {"pattern": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"), "replace": SECRET_PLACEHOLDER},
    # AWS access key id (covers AKIA/ASIA/ABIA/ACCA/A3T* prefixes)
    {
        "pattern": re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[0-9A-Z]{16}\b"),
        "replace": SECRET_PLACEHOLDER,
    },
    # Google API key + OAuth access token
    {"pattern": re.compile(r"\bAIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"), "replace": SECRET_PLACEHOLDER},
    {"pattern": re.compile(r"\bya29\.[0-9A-Za-z_-]+(?![0-9A-Za-z_-])"), "replace": SECRET_PLACEHOLDER},
    # Slack tokens (bot/user + app-level) + incoming webhooks
    {
        "pattern": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}(?![A-Za-z0-9-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    {
        "pattern": re.compile(r"\bxapp-\d-[A-Za-z0-9-]{10,}(?![A-Za-z0-9-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    {
        "pattern": re.compile(r"\bhttps://hooks\.slack\.com/services/[A-Za-z0-9/]+(?![A-Za-z0-9/])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # Stripe
    {
        "pattern": re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b"),
        "replace": SECRET_PLACEHOLDER,
    },
    # npm
    {"pattern": re.compile(r"\bnpm_[A-Za-z0-9]{36}(?![A-Za-z0-9])"), "replace": SECRET_PLACEHOLDER},
    # PyPI upload token
    {
        "pattern": re.compile(r"\bpypi-AgEIcHlwaS[A-Za-z0-9_-]{50,}(?![A-Za-z0-9_-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # SendGrid
    {
        "pattern": re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # ── Structured tokens ────────────────────────────────────────────────────
    # JWT (header.payload.signature)
    {
        "pattern": re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![A-Za-z0-9_-])"),
        "replace": SECRET_PLACEHOLDER,
    },
    # PEM private key blocks (RSA/EC/OPENSSH/DSA/plain + PGP "...KEY BLOCK")
    {
        "pattern": re.compile(
            r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----"
            r"[\s\S]+?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----"
        ),
        "replace": SECRET_PLACEHOLDER,
    },
]
"""Curated, high-precision rules for detecting common credentials in traced
data (prompts, tool inputs/outputs, file contents, shell commands).

Favors low false positives over exhaustive coverage: all rules are prefix-
anchored to well-known token shapes (provider key formats, JWT structure, PEM
armor). No contextual/heuristic "KEY=value" patterns. This is the Python parity
of the JS SDK's ``DEFAULT_SECRET_RULES``; it is NOT a port of gitleaks/secretlint
(pattern shapes are drawn from those projects as a reference only)."""


_SECRET_INDICATORS = (
    "sk-",
    "lsv2_",
    "ls__",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",
    "glpat-",
    "akia",
    "asia",
    "abia",
    "acca",
    "a3t",
    "aiza",
    "ya29.",
    "xox",
    "xapp-",
    "hooks.slack.com/services",
    "sk_live_",
    "sk_test_",
    "rk_live_",
    "rk_test_",
    "npm_",
    "pypi-ageichlwas",
    "sg.",
    "eyj",
    "-----begin",
)

# Threshold for base64 detection: strings longer than this that are almost
# entirely base64 characters (with optional whitespace) are treated as binary
# blobs and skipped. 100 chars is conservative — real secrets are short and
# contain distinctive prefixes that never look like base64.
_BASE64_MIN_LENGTH = 100
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/\s]+={0,2}$")


def _is_likely_base64(value: str) -> bool:
    """Return True if *value* looks like a base64-encoded blob.

    We only flag long strings that are almost entirely base64 alphabet
    characters with optional whitespace. Short strings and strings containing
    characters outside the base64 alphabet (spaces in the middle, punctuation,
    etc.) are not flagged.
    """
    if len(value) < _BASE64_MIN_LENGTH:
        return False
    return bool(_BASE64_RE.match(value))


def _secret_prefilter(value: str) -> bool:
    """Fast pre-filter for the secret rules processor.

    Returns True if the value *might* contain a secret (and should proceed to
    regex matching), False if it can be safely skipped. Two criteria:

    1. The value must contain at least one known secret indicator substring.
    2. The value must NOT look like a base64 blob (large binary payloads are
       the dominant performance cost and never contain format-prefixed secrets).
    """
    if _is_likely_base64(value):
        return False
    value_lower = value.lower()
    return any(indicator in value_lower for indicator in _SECRET_INDICATORS)


def create_secret_anonymizer(
    *,
    extra_rules: Optional[list[StringNodeRule]] = None,
    max_depth: Optional[int] = 24,
) -> Callable[[Any], Any]:
    """Build an anonymizer pre-loaded with :data:`DEFAULT_SECRET_RULES`.

    Pass the result to ``Client(anonymizer=...)`` to redact detected secrets
    from run inputs, outputs, and metadata client-side, before upload.

    Args:
        extra_rules: Additional rules appended after the defaults.
        max_depth: Max recursion depth (default 24; higher than
            ``create_anonymizer``'s default of 10 because traced payloads nest
            deeply, e.g. ``messages[].content[].args``).

    Example:
        >>> from langsmith import Client
        >>> from langsmith.anonymizer import create_secret_anonymizer
        >>> client = Client(anonymizer=create_secret_anonymizer())
    """
    if extra_rules:
        # When extra rules are provided, use the node-based pipeline without
        # the prefilter — custom rules may match patterns that don't contain
        # standard secret indicators.
        rules = list(DEFAULT_SECRET_RULES) + list(extra_rules)
        processor = RuleNodeProcessor(rules)
    else:
        # Default path: use the node-based pipeline with the pre-skip prefilter.
        # The prefilter skips large base64 blobs (the dominant performance cost)
        # and short-circuits strings with no secret indicators, so regex only
        # runs on text fields that might actually contain a secret.
        processor = RuleNodeProcessor(
            DEFAULT_SECRET_RULES, prefilter=_secret_prefilter
        )
    return create_anonymizer(processor, max_depth=max_depth)
