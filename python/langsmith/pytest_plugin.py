"""LangSmith Pytest hooks."""

import pytest

from langsmith.testing._internal import test as ls_test


def pytest_configure(config):
    """Register the 'langsmith' marker."""
    config.addinivalue_line(
        "markers", "langsmith: mark test to be tracked in LangSmith"
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Apply LangSmith tracking to tests marked with @pytest.mark.langsmith."""
    marker = item.get_closest_marker("langsmith")
    if marker:
        # Get marker kwargs if any (e.g.,
        # @pytest.mark.langsmith(output_keys=["expected"]))
        kwargs = marker.kwargs if marker else {}
        # Wrap the test function with our test decorator
        original_func = item.obj
        item.obj = ls_test(**kwargs)(original_func)

    yield
