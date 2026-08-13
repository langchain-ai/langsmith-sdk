from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from langsmith import pytest_plugin


@pytest.mark.parametrize(
    ("statuses", "expected_count", "formatted"),
    [
        (
            [{"status": "passed"}, {"status": "passed"}],
            2,
            "[green]100% passed (2/2 reported)[/green]",
        ),
        (
            [{"status": "passed"}] * 3 + [{}] * 7,
            10,
            "[yellow]30% passed (3/10 reported)[/yellow]",
        ),
        (
            [{"status": "passed"}, {"status": "failed"}],
            2,
            "[red]50% passed (2/2 reported)[/red]",
        ),
        (
            [{"status": "passed"}, {"status": "skipped"}],
            2,
            "[yellow]50% passed (2/2 reported)[/yellow]",
        ),
        ([], 0, "Passed: --"),
    ],
)
def test_format_aggregate_status(statuses, expected_count, formatted):
    assert pytest_plugin._format_aggregate_status(statuses, expected_count) == formatted


def test_collection_groups_langsmith_tests_by_suite(monkeypatch):
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = defaultdict(list)
    explicit_marker = SimpleNamespace(kwargs={"test_suite_name": "explicit-suite"})
    default_marker = SimpleNamespace(kwargs={})
    explicit_item = SimpleNamespace(
        nodeid="test_example.py::test_explicit",
        obj=object(),
        get_closest_marker=lambda name: explicit_marker,
    )
    default_item = SimpleNamespace(
        nodeid="test_example.py::test_default",
        obj=object(),
        get_closest_marker=lambda name: default_marker,
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
        SimpleNamespace(items=[explicit_item, default_item, regular_item])
    )
    plugin.add_process_to_test_suite("explicit-suite", explicit_item.nodeid)

    assert plugin.collected_nodeids == {
        explicit_item.nodeid,
        default_item.nodeid,
        regular_item.nodeid,
    }
    assert plugin.langsmith_nodeids == {explicit_item.nodeid, default_item.nodeid}
    assert plugin.test_suites == {
        "explicit-suite": [explicit_item.nodeid],
        "default-suite": [default_item.nodeid],
    }


def test_table_includes_expected_tests_without_results():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = {"suite": ["test_example.py::test_missing"]}
    plugin.test_suite_urls = {}
    plugin.process_status = {}
    plugin.console = Console(width=300, record=True)

    plugin.console.print(plugin._generate_table("suite"))

    output = " ".join(plugin.console.export_text().split())
    assert "LangSmith URL: --" in output
    assert "test_example.py::test_missing" in output
    assert "queued" in output
    assert "0% passed (0/1 reported)" in output


def test_terminal_langsmith_status_is_marked_reported():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.process_status = {}
    plugin.status_lock = pytest_plugin.Lock()
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.update_process_status("test_example.py::test_passed", {"status": "passed"})

    assert plugin.process_status == {
        "test_example.py::test_passed": {"status": "passed", "_reported": True}
    }


def test_call_failure_keeps_langsmith_failed_status():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    nodeid = "test_example.py::test_failed"
    plugin.langsmith_nodeids = {nodeid}
    plugin.completed_nodeids = set()
    plugin.process_status = {nodeid: {"status": "failed", "_reported": True}}
    plugin.status_lock = pytest_plugin.Lock()
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.pytest_runtest_logreport(
        SimpleNamespace(nodeid=nodeid, failed=True, skipped=False, when="call")
    )

    assert plugin.process_status[nodeid] == {
        "status": "failed",
        "_reported": True,
    }
    plugin.live.update.assert_not_called()


def test_skipped_teardown_invalidates_reported_pass():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    nodeid = "test_example.py::test_teardown_skip"
    plugin.langsmith_nodeids = {nodeid}
    plugin.completed_nodeids = set()
    plugin.process_status = {nodeid: {"status": "passed", "_reported": True}}
    plugin.status_lock = pytest_plugin.Lock()
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.pytest_runtest_logreport(
        SimpleNamespace(nodeid=nodeid, failed=False, skipped=True, when="teardown")
    )

    status = plugin.process_status[nodeid]
    assert status == {"status": "skipped", "_reported": True}
    assert pytest_plugin._format_aggregate_status([status], 1) == (
        "[yellow]0% passed (1/1 reported)[/yellow]"
    )
    assert plugin.completed_nodeids == {nodeid}
    plugin.live.update.assert_called_once_with("tables")


def test_pytest_failure_overrides_reported_pass():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.langsmith_nodeids = {"test_example.py::test_error"}
    plugin.completed_nodeids = set()
    plugin.process_status = {
        "test_example.py::test_error": {"status": "passed", "_reported": True}
    }
    plugin.status_lock = pytest_plugin.Lock()
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid="test_example.py::test_error", failed=True, when="teardown"
        )
    )

    status = plugin.process_status["test_example.py::test_error"]
    assert status == {"status": "error", "_reported": True}
    assert plugin.completed_nodeids == {"test_example.py::test_error"}
    assert pytest_plugin._format_aggregate_status([status], 1) == (
        "[red]0% passed (1/1 reported)[/red]"
    )
    plugin.live.update.assert_called_once_with("tables")


def test_session_finish_invalidates_pass_without_teardown():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = {"suite": ["test_example.py::test_incomplete"]}
    plugin.process_status = {
        "test_example.py::test_incomplete": {
            "status": "passed",
            "_reported": True,
        }
    }
    plugin.status_lock = pytest_plugin.Lock()
    plugin.completed_nodeids = set()
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.pytest_sessionfinish(SimpleNamespace())

    status = plugin.process_status["test_example.py::test_incomplete"]
    assert status == {"status": "unreported", "_reported": True}
    assert pytest_plugin._format_aggregate_status([status], 1) == (
        "[yellow]0% passed (1/1 reported)[/yellow]"
    )


def test_session_finish_marks_incomplete_tests_unreported():
    plugin = object.__new__(pytest_plugin.LangSmithPlugin)
    plugin.test_suites = {"suite": ["passed", "running", "missing"]}
    plugin.process_status = {
        "passed": {"status": "passed"},
        "running": {"status": "running"},
    }
    plugin.status_lock = pytest_plugin.Lock()
    plugin.completed_nodeids = {"passed", "running", "missing"}
    plugin.generate_tables = Mock(return_value="tables")
    plugin.live = Mock()

    plugin.pytest_sessionfinish(SimpleNamespace())

    assert plugin.process_status == {
        "passed": {"status": "passed"},
        "running": {"status": "unreported"},
        "missing": {"status": "unreported"},
    }
    plugin.live.update.assert_called_once_with("tables")
    plugin.live.stop.assert_called_once_with()
