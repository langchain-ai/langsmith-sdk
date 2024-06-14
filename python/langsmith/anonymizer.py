import copy
import re
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Callable, List, Optional, Tuple, TypedDict, Union


class ExtractOptions(TypedDict):
    maxDepth: Optional[int]
    """
    Maximum depth to traverse to to extract string nodes
    """


class StringNode(TypedDict):
    value: str
    path: tuple[str | int]


def _extract_string_nodes(data: Any, options: ExtractOptions) -> List[StringNode]:
    parsed_options = {**options, "maxDepth": options.get("maxDepth", 10)}

    queue: List[Tuple[Any, int, tuple[str | int]]] = [(data, 0, tuple())]
    result: List[StringNode] = []

    while queue:
        task = queue.pop(0)
        if task is None:
            continue
        value, depth, path = task

        if isinstance(value, dict) or isinstance(value, defaultdict):
            if depth >= parsed_options["maxDepth"]:
                continue
            for key, nested_value in value.items():
                queue.append((nested_value, depth + 1, path + (key,)))
        elif isinstance(value, list):
            if depth >= parsed_options["maxDepth"]:
                continue
            for i, item in enumerate(value):
                queue.append((item, depth + 1, path + (i,)))
        elif isinstance(value, str):
            result.append(StringNode(value, path))

    return result


class StringNodeProcessor:
    @abstractmethod
    def mask_nodes(self, nodes: List[StringNode]) -> List[StringNode]:
        """Mask node."""


class ReplacerOptions(TypedDict):
    maxDepth: Optional[int]
    deepClone: Optional[bool]


class StringNodeRule(TypedDict):
    pattern: Union[str, re.Pattern]
    replace: Optional[str] = "[redacted]"


ReplacerType = Union[
    Callable[[str, Optional[str]], str], List[StringNodeRule], StringNodeProcessor
]


def replace_sensitive_data(
    data: Any, replacer: ReplacerType, options: Optional[ReplacerOptions] = None
) -> Any:
    nodes = _extract_string_nodes(data, options)
    mutate_value = copy.deepcopy(data) if options and options["deepClone"] else data

    if isinstance(replacer, list):

        def mask_nodes(nodes: List[StringNode]) -> List[StringNode]:
            result = []
            for item in nodes:
                new_value = item.value
                for rule in replacer:
                    new_value = rule["pattern"].sub(rule["replace"], new_value)
                if new_value != item.value:
                    result.append(StringNode(new_value, item.path))
            return result

        processor = StringNodeProcessor()
        processor.mask_nodes = mask_nodes
    elif callable(replacer):

        def mask_nodes(nodes: List[StringNode]) -> List[StringNode]:
            return [
                StringNode(replacer(node.value, node.path), node.path)
                for node in nodes
                if replacer(node.value, node.path) != node.value
            ]

        processor = StringNodeProcessor()
        processor.mask_nodes = mask_nodes
    else:
        processor = replacer

    to_update = processor.mask_nodes(nodes)
    for node in to_update:
        if not node.path:
            mutate_value = node.value
        else:
            temp = mutate_value
            for part in node.path[:-1]:
                temp = temp[part]

            last_part = node.path[-1]
            temp[last_part] = node.value

    return mutate_value
