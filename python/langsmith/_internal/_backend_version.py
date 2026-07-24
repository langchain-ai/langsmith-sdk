import logging
from typing import TYPE_CHECKING, Any, Optional
from urllib import parse as urllib_parse

import packaging.version

from langsmith._internal._constants import _MIN_BACKEND_VERSION
from langsmith._internal._package_version import get_package_version

if TYPE_CHECKING:
    from langsmith.schemas import LangSmithInfo

logger = logging.getLogger(__name__)

_sdk_compat_checked = False


def _is_self_hosted(api_url: str) -> bool:
    try:
        netloc = urllib_parse.urlsplit(api_url).netloc.split(":")[0]
        return not (netloc == "langchain.com" or netloc.endswith(".langchain.com"))
    except Exception:
        return False


def _check_sdk_compat(info: "LangSmithInfo", api_url: str) -> None:
    """Check backend and SDK version compatibility, emitting a single warning.

    Only runs on self-hosted deployments (URL not under *.langchain.com).
    Warns if the backend is older than the minimum required version and/or
    the installed SDK is newer than what the backend supports.
    """
    global _sdk_compat_checked
    if _sdk_compat_checked:
        return
    _sdk_compat_checked = True

    if not _is_self_hosted(api_url):
        return

    issues: list[str] = []

    # Check backend version against SDK minimum requirement.
    backend_version_str = info.version
    if backend_version_str:
        try:
            backend_version = packaging.version.parse(backend_version_str)
            min_backend = packaging.version.parse(_MIN_BACKEND_VERSION)
            if backend_version < min_backend:
                issues.append(
                    f"backend version {backend_version_str!r} is older than the "
                    f"minimum required by this SDK ({_MIN_BACKEND_VERSION!r})"
                )
        except packaging.version.InvalidVersion:
            pass

    # Check SDK version against backend maximum.
    sdk_versions: Optional[dict[str, Any]] = info.sdk_versions
    if sdk_versions:
        max_sdk_str = sdk_versions.get("max_python_sdk_version")
        if max_sdk_str:
            current_sdk_str = get_package_version("langsmith")
            if current_sdk_str:
                try:
                    current_sdk = packaging.version.parse(current_sdk_str)
                    max_sdk = packaging.version.parse(max_sdk_str)
                    if current_sdk > max_sdk:
                        issues.append(
                            f"SDK version {current_sdk_str!r} is newer than the "
                            f"maximum supported by this backend ({max_sdk_str!r}); "
                            f"consider using SDK version {max_sdk_str!r}"
                        )
                except packaging.version.InvalidVersion:
                    pass

    if issues:
        logger.warning(
            "LangSmith compatibility issue(s) detected: %s. "
            "Some features may not work as expected.",
            "; ".join(issues),
        )
