from collections import defaultdict
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from langsmith import pytest_plugin


def test_collection_groups_langsmith_tests_by_suite(monkeypatch):
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = defaultdict(list)
    marker = SimpleNamespace(kwargs={})
    langsmith_item = SimpleNamespace(
        nodeid="test_example.py::test_tracked",
        obj=object(),
        get_closest_marker=lambda name: marker,
    )
    regular_item = SimpleNamespace(
        nodeid="test_example.py::test_regular",
        obj=object(),
        get_closest_marker=lambda name: None,
    )
    monkeypatch.setattr(
        pytest_plugin, "_get_test_suite_name", lambda obj: "default-suite"
    )

    plugin.pytest_collection_finish(
        SimpleNamespace(items=[langsmith_item, regular_item])
    )
    plugin.add_process_to_test_suite("default-suite", langsmith_item.nodeid)

    assert plugin.test_suites == {"default-suite": [langsmith_item.nodeid]}


@pytest.mark.parametrize(
    ("failed", "skipped", "expected_status"),
    [(True, False, "failed"), (False, True, "skipped")],
)
def test_setup_outcome_replaces_running_status(failed, skipped, expected_status):
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    nodeid = "test_example.py::test_setup_outcome"
    plugin.langsmith_nodeids = {nodeid}
    plugin.process_status = {}
    plugin.status_lock = Lock()
    plugin.live = Mock()
    plugin.generate_tables = Mock(return_value="tables")

    plugin.pytest_runtest_logstart(nodeid)
    plugin.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid=nodeid,
            when="setup",
            failed=failed,
            skipped=skipped,
        )
    )

    assert plugin.process_status[nodeid]["status"] == expected_status


def test_table_counts_collected_tests_without_results():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = {
        "suite": ["test_example.py::test_passed", "test_example.py::test_missing"]
    }
    plugin.test_suite_urls = {}
    plugin.process_status = {
        "test_example.py::test_passed": {"status": "passed"},
    }
    plugin.console = Console(width=300, record=True)

    plugin.console.print(plugin._generate_table("suite"))

    output = " ".join(plugin.console.export_text().split())
    assert "LangSmith URL: --" in output
    assert "test_example.py::test_missing" in output
    assert "queued" in output
    assert "50%" in output
