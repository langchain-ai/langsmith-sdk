import copy  # noqa
import re
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Callable, List, Optional, Tuple, TypedDict, TypeVar, Union


class _ExtractOptions(TypedDict):
    maxDepth: Optional[int]
    """
    Maximum depth to traverse to to extract string nodes
    """


class StringNode(TypedDict):
    """String node extracted from the data."""

    value: str
    """String value."""

    path: tuple[str | int]
    """Path to the string node in the data."""


def _extract_string_nodes(data: Any, options: _ExtractOptions) -> List[StringNode]:
    max_depth = options.get("maxDepth", 10)

    queue: List[Tuple[Any, int, tuple[str | int]]] = [(data, 0, tuple())]
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
                queue.append((nested_value, depth + 1, path + (key,)))
        elif isinstance(value, list):
            if depth >= max_depth:
                continue
            for i, item in enumerate(value):
                queue.append((item, depth + 1, path + (i,)))
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

    pattern: Union[str, re.Pattern]
    """Regex pattern to match."""

    replace: Optional[str] = "[redacted]"
    """Replacement value. Defaults to `[redacted]` if not specified."""


ReplacerType = Union[
    Callable[[str, tuple[str | int]], str], List[StringNodeRule], StringNodeProcessor
]

T = TypeVar("T", str, dict)


def replace_sensitive_data(
    data: T, replacer: ReplacerType, options: Optional[ReplacerOptions] = None
) -> T:
    """Replace sensitive data."""
    nodes = _extract_string_nodes(
        data, {"maxDepth": (options or {}).get("maxDepth", 10)}
    )
    mutate_value = copy.deepcopy(data) if options and options["deepClone"] else data

    if isinstance(replacer, list):

        def mask_nodes(nodes: List[StringNode]) -> List[StringNode]:
            result = []
            for item in nodes:
                new_value = item["value"]
                for rule in replacer:
                    new_value = rule["pattern"].sub(rule["replace"], new_value)
                if new_value != item["value"]:
                    result.append(StringNode(value=new_value, path=item["path"]))
            return result

        processor = StringNodeProcessor()
        processor.mask_nodes = mask_nodes
    elif callable(replacer):

        def mask_nodes(nodes: List[StringNode]) -> List[StringNode]:
            retval: list[StringNode] = []
            for node in nodes:
                candidate = replacer(node["value"], node["path"])
                if candidate != node["value"]:
                    retval.append(StringNode(value=candidate, path=node["path"]))
            return retval

        processor = StringNodeProcessor()
        processor.mask_nodes = mask_nodes
    else:
        processor = replacer

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
