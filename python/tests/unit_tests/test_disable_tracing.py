import os
import warnings

from langsmith.client import Client


def test_disable_tracing():
    """Test enable_tracing."""
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ.pop("LANGSMITH_API_KEY", None)
    os.environ.pop("LANGSMITH_TRACING_V2", None)
    os.environ.pop("LANGCHAIN_TRACING", None)
    os.environ.pop("LANGCHAIN_TRACING_V2", None)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Client()
        assert len(w) == 0, (
            f"Expected no warnings, but got: {[str(warning.message) for warning in w]}"
        )
