"""Tests for the LangSmith pytest output plugin."""

from unittest import mock

import pytest
from pluggy import Result

from langsmith.pytest_plugin import (
    LangSmithPlugin,
    _collected_test_suite_name,
    _handle_output_args,
    pytest_report_teststatus,
)

SUITE = "repo.tests.test_things"


def _make_plugin() -> LangSmithPlugin:
    """Build a plugin with the live display stubbed out."""
    from rich.console import Console

    with mock.patch("rich.live.Live"):
        plugin = LangSmithPlugin()
    # Wide enough that the table renders test names without abbreviating them.
    plugin.console = Console(record=True, width=200)
    plugin.test_suite_urls[SUITE] = "https://smith.langchain.com/suite"
    return plugin


def _render(plugin: LangSmithPlugin, suite: str = SUITE) -> str:
    plugin.console.print(plugin._generate_table(suite))
    return plugin.console.export_text()


def _add_executed(plugin: LangSmithPlugin, nodeid: str, status: str, **extra) -> None:
    plugin.collected_by_suite[SUITE].add(nodeid)
    plugin.add_process_to_test_suite(SUITE, nodeid)
    plugin.process_status[nodeid] = {"status": status, **extra}


def _add_unrun(plugin: LangSmithPlugin, nodeid: str, status: str = "") -> None:
    """Collect a test that never reached its suite: skipped, errored, or queued."""
    plugin.collected_by_suite[SUITE].add(nodeid)
    if status:
        plugin.unrun_statuses[nodeid] = status


def test_unrun_tests_count_against_the_pass_rate() -> None:
    """Skipped and errored tests must not drop out of the denominator."""
    plugin = _make_plugin()
    for i in range(3):
        _add_executed(plugin, f"test_f.py::test_pass{i}", "passed")
    # Skipped by a marker and errored in a fixture: neither reaches the suite.
    for i in range(4):
        _add_unrun(plugin, f"test_f.py::test_skip{i}", "skipped")
    for i in range(3):
        _add_unrun(plugin, f"test_f.py::test_err{i}", "error")

    output = _render(plugin)

    assert "30% (3/10)" in output
    assert "100%" not in output


def test_unrun_tests_get_their_own_rows() -> None:
    """A test that never ran should still be visible in the table."""
    plugin = _make_plugin()
    _add_executed(plugin, "test_f.py::test_ok", "passed")
    _add_unrun(plugin, "test_f.py::test_broken", "error")
    _add_unrun(plugin, "test_f.py::test_never_started")

    output = _render(plugin)

    assert "test_broken" in output
    assert "error" in output
    # Collected but not reported on yet — still owed a result.
    assert "test_never_started" in output
    assert "queued" in output


@pytest.mark.parametrize(
    ("statuses", "rate", "color"),
    [
        (["passed", "passed"], "100% (2/2)", "green"),
        (["passed", "failed"], "50% (1/2)", "red"),
    ],
)
def test_suite_reads_green_only_when_every_test_passed(statuses, rate, color) -> None:
    plugin = _make_plugin()
    for i, status in enumerate(statuses):
        _add_executed(plugin, f"test_f.py::test_{i}", status)

    rate_cells = str(plugin._generate_table(SUITE).columns[4]._cells)

    assert rate in _render(plugin)
    assert color in rate_cells


def test_feedback_average_reports_how_many_tests_it_covers() -> None:
    """A mean over 2 of 5 tests should not read like a mean over all 5."""
    plugin = _make_plugin()
    _add_executed(plugin, "test_f.py::test_a", "passed", feedback={"correctness": 1})
    _add_executed(plugin, "test_f.py::test_b", "passed", feedback={"correctness": 0})
    for i in range(3):
        _add_unrun(plugin, f"test_f.py::test_skip{i}", "skipped")

    assert "correctness: 0.5 (2/5)" in _render(plugin)


def test_empty_suite_reports_no_rate() -> None:
    plugin = _make_plugin()
    plugin.test_suites[SUITE] = []

    assert "Passed: --" in _render(plugin)


@pytest.mark.parametrize("langsmith_output", [True, False])
def test_teststatus_blanks_the_letter_but_keeps_the_category(langsmith_output) -> None:
    """Blanking the category would drop these tests from pytest's own counts."""
    config = mock.Mock()
    config.getoption.return_value = langsmith_output

    gen = pytest_report_teststatus(mock.Mock(), config)
    next(gen)
    result = Result(("error", "E", "ERROR"), None)
    with pytest.raises(StopIteration):
        gen.send(result)

    letter = "" if langsmith_output else "E"
    assert result.get_result() == ("error", letter, "ERROR")


@pytest.mark.parametrize(
    ("args", "quiet_flags"),
    [
        # -qq would hide the end-of-run counts the table cannot replace.
        (["--langsmith-output"], ["-q"]),
        # An explicit quiet flag is left as the caller set it.
        (["--langsmith-output", "-qq"], ["-qq"]),
    ],
)
def test_output_args_keep_pytest_counts(args, quiet_flags) -> None:
    _handle_output_args(args)

    assert [a for a in args if a in ("-q", "-qq", "--quiet")] == quiet_flags


class _FakeItem:
    """Minimal stand-in for a collected pytest item."""

    nodeid = "test_f.py::test_x"

    def __init__(self, marker=None):
        self._marker = marker

    def obj(self):
        pass

    def get_closest_marker(self, name):
        return self._marker if name == "langsmith" else None


def test_unmarked_tests_belong_to_no_suite() -> None:
    """Unmarked tests must not inflate any suite's denominator."""
    assert _collected_test_suite_name(_FakeItem()) is None


def test_collection_names_suites_the_way_the_decorator_does(monkeypatch) -> None:
    """The denominator depends on resolving the same suite the decorator would."""
    monkeypatch.setenv("LANGSMITH_TEST_SUITE", "env-suite")

    assert _collected_test_suite_name(_FakeItem(mock.Mock(kwargs={}))) == "env-suite"
    # An explicit suite on the marker wins, exactly as the decorator resolves it.
    explicit = _FakeItem(mock.Mock(kwargs={"test_suite_name": "explicit-suite"}))
    assert _collected_test_suite_name(explicit) == "explicit-suite"
