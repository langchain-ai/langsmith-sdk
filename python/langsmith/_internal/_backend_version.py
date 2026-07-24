import logging
from typing import Any, Optional
from urllib import parse as urllib_parse

import packaging.version

from langsmith._internal._constants import _MIN_BACKEND_VERSION
from langsmith._internal._package_version import get_package_version

logger = logging.getLogger(__name__)

_max_sdk_version_checked = False


def _check_backend_version(version: str) -> None:
    try:
        _parsed = packaging.version.parse(version)
        _supported = packaging.version.parse(_MIN_BACKEND_VERSION)
        if _parsed < _supported:
            logger.warning(
                "Backend version %r is older than the minimum version required by "
                "this SDK (%r). Some features may not work as expected.",
                version,
                _MIN_BACKEND_VERSION,
            )
    except packaging.version.InvalidVersion:
        logger.warning(
            "Could not parse backend version %r for compatibility check.",
            version,
        )


def _is_self_hosted(api_url: str) -> bool:
    try:
        netloc = urllib_parse.urlsplit(api_url).netloc.split(":")[0]
        return not (netloc == "langchain.com" or netloc.endswith(".langchain.com"))
    except Exception:
        return False


def _check_max_sdk_version(
    sdk_versions: Optional[dict[str, Any]], api_url: str
) -> None:
    global _max_sdk_version_checked
    if _max_sdk_version_checked:
        return
    _max_sdk_version_checked = True

    if not _is_self_hosted(api_url):
        return

    if not sdk_versions:
        return

    max_version_str = sdk_versions.get("max_python_sdk_version")
    if not max_version_str:
        return

    current_version_str = get_package_version("langsmith")
    if not current_version_str:
        return

    try:
        current = packaging.version.parse(current_version_str)
        max_version = packaging.version.parse(max_version_str)
        if current > max_version:
            logger.warning(
                "LangSmith SDK version %r is newer than the maximum version "
                "supported by this backend (%r). Consider using version %r.",
                current_version_str,
                max_version_str,
                max_version_str,
            )
    except packaging.version.InvalidVersion:
        logger.warning(
            "Could not parse SDK version for max version compatibility check.",
        )
