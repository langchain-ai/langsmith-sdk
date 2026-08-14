import logging

from packaging.version import InvalidVersion, parse

logger = logging.getLogger(__name__)


def _check_backend_version(backend_version: str, *, min_version: str) -> None:
    if not backend_version:
        # /info was unreachable (or skipped): nothing to compare against.
        return
    try:
        if parse(backend_version) < parse(min_version):
            logger.warning(
                "Backend version %r is older than the minimum version required by "
                "this SDK (%r). Some features may not work as expected. See "
                "https://docs.langchain.com/langsmith/smithdb-sdk-migration",
                backend_version,
                min_version,
            )
    except InvalidVersion:
        logger.warning(
            "Could not parse backend version %r for compatibility check.",
            backend_version,
        )
