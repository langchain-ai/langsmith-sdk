import re  # noqa
import inspect
from abc import abstractmethod
from collections import defaultdict
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

    queue: list[tuple[Any, int, list[Union[str, int]]]] = [(data, 0, [])]
    result: list[StringNode] = []

    while queue:
        task = queue.pop(0)
        if task is None:
            continue
        value, depth, path = task

        if isinstance(value, (dict, defaultdict)):
            if depth >= max_depth:
                continue
            for key, nested_value in value.items():
                queue.append((nested_value, depth + 1, path + [key]))
        elif isinstance(value, list):
            if depth >= max_depth:
                continue
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

    def __init__(self, rules: list[StringNodeRule]):
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

    def mask_nodes(self, nodes: list[StringNode]) -> list[StringNode]:
        """Mask nodes using the rules."""
        result = []
        for item in nodes:
            new_value = item["value"]
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
        "pattern": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        "replace": SECRET_PLACEHOLDER,
    },
    # OpenAI: project / service-account / admin keys, then legacy `sk-...`
    {
        "pattern": re.compile(r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}"),
        "replace": SECRET_PLACEHOLDER,
    },
    {"pattern": re.compile(r"sk-[A-Za-z0-9]{32,}"), "replace": SECRET_PLACEHOLDER},
    # LangSmith (keys are multi-segment: lsv2_pt_<key>_<tail> — match the full
    # underscore-delimited tail so none of it leaks past the placeholder)
    {
        "pattern": re.compile(r"lsv2_(?:pt|sk)_[A-Za-z0-9]{32,}(?:_[A-Za-z0-9]+)*"),
        "replace": SECRET_PLACEHOLDER,
    },
    {"pattern": re.compile(r"ls__[A-Za-z0-9]{16,}"), "replace": SECRET_PLACEHOLDER},
    # GitHub personal access / app tokens
    {
        "pattern": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
        "replace": SECRET_PLACEHOLDER,
    },
    {
        "pattern": re.compile(r"github_pat_[A-Za-z0-9_]{82}"),
        "replace": SECRET_PLACEHOLDER,
    },
    # AWS access key id (long-term + temporary)
    {
        "pattern": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "replace": SECRET_PLACEHOLDER,
    },
    # Google API key + OAuth access token
    {"pattern": re.compile(r"AIza[0-9A-Za-z_-]{35}"), "replace": SECRET_PLACEHOLDER},
    {"pattern": re.compile(r"ya29\.[0-9A-Za-z_-]+"), "replace": SECRET_PLACEHOLDER},
    # Slack tokens + incoming webhooks
    {
        "pattern": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        "replace": SECRET_PLACEHOLDER,
    },
    {
        "pattern": re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"),
        "replace": SECRET_PLACEHOLDER,
    },
    # Stripe
    {
        "pattern": re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b"),
        "replace": SECRET_PLACEHOLDER,
    },
    # npm
    {"pattern": re.compile(r"npm_[A-Za-z0-9]{36}"), "replace": SECRET_PLACEHOLDER},
    # SendGrid
    {
        "pattern": re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"),
        "replace": SECRET_PLACEHOLDER,
    },
    # ── Structured tokens ────────────────────────────────────────────────────
    # JWT (header.payload.signature)
    {
        "pattern": re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
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
    # ── Structural / contextual (sensitive NAME + assignment) ─────────────────
    # KEY=value / "key": "value" where the name looks sensitive. Keep the name
    # and separator (group 1), redact the value. Notes:
    #  - (?![A-Za-z0-9]) after the keyword requires a component boundary, so
    #    `token` matches `api_token`/`mytoken` but NOT `tokenizer`/`tokens`.
    #  - the value may start with an auth scheme word (Bearer/Token/Basic) so a
    #    `X-Api-Key: Bearer <tok>` shape redacts the credential, not just "Bearer".
    #  - value excludes & and ; so query-string params past the secret survive.
    #  - requires a 6+ char value so short non-secret values are left intact.
    {
        "pattern": re.compile(
            r"""\b([A-Za-z0-9_.-]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY|ACCESS[_-]?KEY|AUTH[_-]?TOKEN|CLIENT[_-]?SECRET)(?![A-Za-z0-9])(?:[_.-][A-Za-z0-9]+)*["']?\s*[:=]\s*["']?)(?:(?:bearer|token|basic)\s+)?[^\s"'&;]{6,}""",
            re.IGNORECASE,
        ),
        "replace": rf"\g<1>{SECRET_PLACEHOLDER}",
    },
    # Authorization / API-key headers. Keep the header name + separator
    # (groups 1-2) and an optional scheme (group 3); redact the credential.
    # Group 3 preserves "Bearer "/"Token "/"Basic " to match the JS preset.
    {
        "pattern": re.compile(
            r"""\b(authorization|x-api-key|x-auth-token)(["']?\s*[:=]\s*["']?)(bearer\s+|token\s+|basic\s+)?[A-Za-z0-9._~+/-]{8,}=*""",
            re.IGNORECASE,
        ),
        "replace": rf"\g<1>\g<2>\g<3>{SECRET_PLACEHOLDER}",
    },
    # Bare "Bearer <token>" (any case; the scheme word is preserved via group 1).
    {
        "pattern": re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/-]{10,}=*", re.IGNORECASE),
        "replace": rf"\g<1>{SECRET_PLACEHOLDER}",
    },
    # Credentials embedded in URLs: proto://user:PASS@host -> redact PASS only.
    # Username is optional so proto://:PASS@host (empty user) is still covered.
    {
        "pattern": re.compile(
            r"\b([a-z][a-z0-9+.-]*://[^:@/\s]*:)[^@/\s]+(@)", re.IGNORECASE
        ),
        "replace": rf"\g<1>{SECRET_PLACEHOLDER}\g<2>",
    },
]
"""Curated, high-precision rules for detecting common credentials in traced
data (prompts, tool inputs/outputs, file contents, shell commands).

Favors low false positives over exhaustive coverage: provider rules are
anchored to known key prefixes, and structural rules only fire when a sensitive
*name* is paired with an assignment/separator. This is the Python parity of the
JS SDK's ``DEFAULT_SECRET_RULES``; it is NOT a port of gitleaks/secretlint
(pattern shapes are drawn from those projects as a reference only)."""


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
    rules = list(DEFAULT_SECRET_RULES)
    if extra_rules:
        rules = rules + list(extra_rules)
    return create_anonymizer(rules, max_depth=max_depth)
