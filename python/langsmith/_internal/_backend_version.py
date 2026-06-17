import logging

import packaging.version

from langsmith._internal._constants import _MIN_BACKEND_VERSION

logger = logging.getLogger(__name__)


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
