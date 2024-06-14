import copy  # noqa
import re
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Callable, List, Optional, Tuple, TypedDict, Union


class _ExtractOptions(TypedDict):
    maxDepth: Optional[int]
    """
    Maximum depth to traverse to to extract string nodes
    """


class StringNode(TypedDict):
    """String node extracted from the data."""

    value: str
    """String value."""

    path: list[Union[str, int]]
    """Path to the string node in the data."""


def _extract_string_nodes(data: Any, options: _ExtractOptions) -> List[StringNode]:
    max_depth = options.get("maxDepth") or 10

    queue: List[Tuple[Any, int, list[Union[str, int]]]] = [(data, 0, list())]
    result: List[StringNode] = []

    while queue:
        task = queue.pop(0)
        if task is None:
            continue
        value, depth, path = task

        if isinstance(value, dict) or isinstance(value, defaultdict):
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
    def mask_nodes(self, nodes: List[StringNode]) -> List[StringNode]:
        """Accept and return a list of string nodes to be masked."""


class ReplacerOptions(TypedDict):
    """Configuration options for replacing sensitive data."""

    maxDepth: Optional[int]
    """Maximum depth to traverse to to extract string nodes."""

    deepClone: Optional[bool]
    """Deep clone the data before replacing."""


class StringNodeRule(TypedDict):
    """Declarative rule used for replacing sensitive data."""

    pattern: re.Pattern
    """Regex pattern to match."""

    replace: Optional[str]
    """Replacement value. Defaults to `[redacted]` if not specified."""


class RuleNodeProcessor(StringNodeProcessor):
    """String node processor that uses a list of rules to replace sensitive data."""

    rules: List[StringNodeRule]

    def __init__(self, rules: List[StringNodeRule]):
        """Initialize the processor with a list of rules."""
        self.rules = rules

    def mask_nodes(self, nodes: List[StringNode]) -> List[StringNode]:
        """Mask nodes using the rules."""
        result = []
        for item in nodes:
            new_value = item["value"]
            for rule in self.rules:
                new_value = rule["pattern"].sub(
                    (
                        rule["replace"]
                        if isinstance(rule["replace"], str)
                        else "[redacted]"
                    ),
                    new_value,
                )
            if new_value != item["value"]:
                result.append(StringNode(value=new_value, path=item["path"]))
        return result


class CallableNodeProcessor(StringNodeProcessor):
    """String node processor that uses a callable function to replace sensitive data."""

    func: Callable[[str, list[Union[str, int]]], str]

    def __init__(self, func: Callable[[str, list[Union[str, int]]], str]):
        """Initialize the processor with a callable function."""
        self.func = func

    def mask_nodes(self, nodes: List[StringNode]) -> List[StringNode]:
        """Mask nodes using the callable function."""
        retval: list[StringNode] = []
        for node in nodes:
            candidate = self.func(node["value"], node["path"])
            if candidate != node["value"]:
                retval.append(StringNode(value=candidate, path=node["path"]))
        return retval


ReplacerType = Union[
    Callable[[str, list[Union[str, int]]], str],
    List[StringNodeRule],
    StringNodeProcessor,
]


def _get_node_processor(replacer: ReplacerType) -> StringNodeProcessor:
    if isinstance(replacer, list):
        return RuleNodeProcessor(rules=replacer)
    elif callable(replacer):
        return CallableNodeProcessor(func=replacer)
    else:
        return replacer


def replace_sensitive_data(
    data: Any, replacer: ReplacerType, options: Optional[ReplacerOptions] = None
) -> Any:
    """Replace sensitive data."""
    nodes = _extract_string_nodes(
        data, {"maxDepth": (options.get("maxDepth") if options else None) or 10}
    )
    mutate_value = copy.deepcopy(data) if options and options["deepClone"] else data

    to_update = _get_node_processor(replacer).mask_nodes(nodes)
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
