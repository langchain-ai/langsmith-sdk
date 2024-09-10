"""Script for auto-generating api_reference.rst."""

import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, List, Literal, Sequence, TypedDict, Union
from enum import Enum

import toml
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).parents[1].absolute()
HERE = Path(__file__).parent
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../"))

PACKAGE_DIR = ROOT_DIR / "langsmith"
ClassKind = Literal["TypedDict", "Regular", "Pydantic", "enum"]


class ClassInfo(TypedDict):
    name: str
    qualified_name: str
    kind: ClassKind
    is_public: bool
    is_deprecated: bool


class FunctionInfo(TypedDict):
    name: str
    qualified_name: str
    is_public: bool
    is_deprecated: bool


class ModuleMembers(TypedDict):
    classes_: Sequence[ClassInfo]
    functions: Sequence[FunctionInfo]


_EXCLUDED_NAMES = {
    "close_session",
    "convert_prompt_to_anthropic_format",
    "convert_prompt_to_openai_format",
    "TracingQueueItem",
    "filter_logs",
    "StringEvaluator",
    "LLMEvaluator",
    "ensure_traceable",
    "is_traceable_function",
    "is_async",
    "get_run_tree_context",
    "as_runnable",
    "SupportsLangsmithExtra",
    "get_tracing_context",
}

_EXCLUDED_MODULES = {"cli"}

_INCLUDED_UTILS = {
    "ContextThreadPoolExecutor",
    "LangSmithAPIError",
    "LangSmithAuthError",
    "LangSmithConflictError",
    "LangSmithConnectionError",
    "LangSmithError",
    "LangSmithMissingAPIKeyWarning",
    "LangSmithNotFoundError",
    "LangSmithRateLimitError",
    "LangSmithRetry",
    "LangSmithUserError",
    "LangSmithWarning",
}


def _load_module_members(module_path: str, namespace: str) -> ModuleMembers:
    classes_: List[ClassInfo] = []
    functions: List[FunctionInfo] = []
    module = importlib.import_module(module_path)
    for name, type_ in inspect.getmembers(module):
        if (
            not hasattr(type_, "__module__")
            or type_.__module__ != module_path
            or name in _EXCLUDED_NAMES
            or (module_path.endswith("utils") and name not in _INCLUDED_UTILS)
        ):
            logger.info(f"Excluding {module_path}.{name}")
            continue

        if inspect.isclass(type_):
            kind: ClassKind = (
                "TypedDict"
                if type(type_).__name__ in ("_TypedDictMeta", "_TypedDictMeta")
                else (
                    "enum"
                    if issubclass(type_, Enum)
                    else "Pydantic" if issubclass(type_, BaseModel) else "Regular"
                )
            )
            classes_.append(
                ClassInfo(
                    name=name,
                    qualified_name=f"{namespace}.{name}",
                    kind=kind,
                    is_public=not name.startswith("_"),
                    is_deprecated=".. deprecated::" in (type_.__doc__ or ""),
                )
            )
        elif inspect.isfunction(type_):
            functions.append(
                FunctionInfo(
                    name=name,
                    qualified_name=f"{namespace}.{name}",
                    is_public=not name.startswith("_"),
                    is_deprecated=".. deprecated::" in (type_.__doc__ or ""),
                )
            )

    return ModuleMembers(classes_=classes_, functions=functions)


def _load_package_modules(
    package_directory: Union[str, Path]
) -> Dict[str, ModuleMembers]:
    package_path = Path(package_directory)
    modules_by_namespace = {}
    package_name = package_path.name

    for file_path in package_path.rglob("*.py"):
        if file_path.name.startswith("_") or any(
            part.startswith("_") for part in file_path.relative_to(package_path).parts
        ):
            continue

        namespace = (
            str(file_path.relative_to(package_path))
            .replace(".py", "")
            .replace("/", ".")
        )
        top_namespace = namespace.split(".")[0]
        if top_namespace in _EXCLUDED_MODULES:
            logger.info(f"Excluding module {top_namespace}")
            continue

        try:
            module_members = _load_module_members(
                f"{package_name}.{namespace}", namespace
            )
            if top_namespace in modules_by_namespace:
                existing = modules_by_namespace[top_namespace]
                modules_by_namespace[top_namespace] = ModuleMembers(
                    classes_=existing["classes_"] + module_members["classes_"],
                    functions=existing["functions"] + module_members["functions"],
                )
            else:
                modules_by_namespace[top_namespace] = module_members
        except ImportError as e:
            print(f"Error: Unable to import module '{namespace}' with error: {e}")

    return modules_by_namespace


module_order = [
    "client",
    "async_client",
    "evaluation",
    "run_helpers",
    "run_trees",
    "schemas",
    "utils",
]


def _construct_doc(
    package_namespace: str,
    members_by_namespace: Dict[str, ModuleMembers],
    package_version: str,
) -> List[tuple[str, str]]:
    docs = []
    index_doc = f"""\
:html_theme.sidebar_secondary.remove:

.. currentmodule:: {package_namespace}

.. _{package_namespace}:

{package_namespace.replace('_', '-')}: {package_version}
{'=' * (len(package_namespace) + len(package_version) + 2)}

.. automodule:: {package_namespace}
    :no-members:
    :no-inherited-members:

.. toctree::
    :maxdepth: 2
    
"""

    def _priority(mod: str):
        if mod in module_order:
            return module_order.index(mod)
        return len(module_order) + hash(mod)

    for module in sorted(members_by_namespace, key=lambda x: _priority(x)):
        index_doc += f"    {module}\n"
        module_doc = f"""\
.. currentmodule:: {package_namespace}

.. _{package_namespace}_{module}:

:mod:`{module}`
{'=' * (len(module) + 7)}

.. automodule:: {package_namespace}.{module}
    :no-members:
    :no-inherited-members:

"""
        _members = members_by_namespace[module]
        classes = [
            el
            for el in _members["classes_"]
            if el["is_public"] and not el["is_deprecated"]
        ]
        functions = [
            el
            for el in _members["functions"]
            if el["is_public"] and not el["is_deprecated"]
        ]
        deprecated_classes = [
            el for el in _members["classes_"] if el["is_public"] and el["is_deprecated"]
        ]
        deprecated_functions = [
            el
            for el in _members["functions"]
            if el["is_public"] and el["is_deprecated"]
        ]

        if classes:
            module_doc += f"""\
**Classes**

.. currentmodule:: {package_namespace}

.. autosummary::
    :toctree: {module}
"""
            for class_ in sorted(classes, key=lambda c: c["qualified_name"]):
                template = (
                    "typeddict.rst"
                    if class_["kind"] == "TypedDict"
                    else (
                        "enum.rst"
                        if class_["kind"] == "enum"
                        else (
                            "pydantic.rst"
                            if class_["kind"] == "Pydantic"
                            else "class.rst"
                        )
                    )
                )
                module_doc += f"""\
    :template: {template}
    
    {class_["qualified_name"]}
    
"""

        if functions:
            qualnames = "\n    ".join(sorted(f["qualified_name"] for f in functions))
            module_doc += f"""**Functions**

.. currentmodule:: {package_namespace}

.. autosummary::
    :toctree: {module}
    :template: function.rst

    {qualnames}

"""

        if deprecated_classes:
            module_doc += f"""**Deprecated classes**

.. currentmodule:: {package_namespace}

.. autosummary::
    :toctree: {module}
"""
            for class_ in sorted(deprecated_classes, key=lambda c: c["qualified_name"]):
                template = (
                    "typeddict.rst"
                    if class_["kind"] == "TypedDict"
                    else (
                        "enum.rst"
                        if class_["kind"] == "enum"
                        else (
                            "pydantic.rst"
                            if class_["kind"] == "Pydantic"
                            else "class.rst"
                        )
                    )
                )
                module_doc += f"""    :template: {template}

    {class_["qualified_name"]}

"""

        if deprecated_functions:
            qualnames = "\n    ".join(
                sorted(f["qualified_name"] for f in deprecated_functions)
            )
            module_doc += f"""**Deprecated functions**

.. currentmodule:: {package_namespace}

.. autosummary::
    :toctree: {module}
    :template: function.rst

    {qualnames}

"""
        docs.append((f"{module}.rst", module_doc))
    docs.append(("index.rst", index_doc))
    return docs


def _get_package_version(package_dir: Path) -> str:
    try:
        with open(package_dir.parent / "pyproject.toml", "r") as f:
            pyproject = toml.load(f)
        return pyproject["tool"]["poetry"]["version"]
    except FileNotFoundError:
        print(f"pyproject.toml not found in {package_dir.parent}. Aborting the build.")
        sys.exit(1)


def main() -> None:
    print("Starting to build API reference files.")
    package_members = _load_package_modules(PACKAGE_DIR)
    package_version = _get_package_version(PACKAGE_DIR)
    rsts = _construct_doc("langsmith", package_members, package_version)
    for name, rst in rsts:
        with open(HERE / name, "w") as f:
            f.write(rst)
    print("API reference files built.")


if __name__ == "__main__":
    main()
