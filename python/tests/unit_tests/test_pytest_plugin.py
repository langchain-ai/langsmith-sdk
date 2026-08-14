"""Tests for the LangSmith pytest output plugin."""

import os
from unittest import mock

import pytest
from pluggy import Result

from langsmith.pytest_plugin import (
    LangSmithPlugin,
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


def test_unrun_tests_count_against_the_pass_rate() -> None:
    """Skipped and errored tests must not drop out of the denominator."""
    plugin = _make_plugin()
    for i in range(3):
        _add_executed(plugin, f"test_f.py::test_pass{i}", "passed")
    # Skipped by a marker and errored in a fixture: neither reaches the suite.
    for i in range(4):
        plugin.collected_by_suite[SUITE].add(f"test_f.py::test_skip{i}")
        plugin.unrun_statuses[f"test_f.py::test_skip{i}"] = "skipped"
    for i in range(3):
        plugin.collected_by_suite[SUITE].add(f"test_f.py::test_err{i}")
        plugin.unrun_statuses[f"test_f.py::test_err{i}"] = "error"

    output = _render(plugin)

    assert "30% (3/10)" in output
    assert "100%" not in output


def test_unrun_tests_get_their_own_rows() -> None:
    """A test that never ran should still be visible in the table."""
    plugin = _make_plugin()
    _add_executed(plugin, "test_f.py::test_ok", "passed")
    plugin.collected_by_suite[SUITE].add("test_f.py::test_broken")
    plugin.unrun_statuses["test_f.py::test_broken"] = "error"
    plugin.collected_by_suite[SUITE].add("test_f.py::test_never_started")

    output = _render(plugin)

    assert "test_broken" in output
    assert "error" in output
    # Collected but not reported on yet — still owed a result.
    assert "test_never_started" in output
    assert "queued" in output


def test_all_passing_suite_is_green() -> None:
    plugin = _make_plugin()
    for i in range(3):
        _add_executed(plugin, f"test_f.py::test_pass{i}", "passed")

    table = plugin._generate_table(SUITE)
    output = _render(plugin)

    assert "100% (3/3)" in output
    assert any("green" in str(cell) for cell in table.columns[4]._cells)


def test_failures_keep_the_suite_red() -> None:
    plugin = _make_plugin()
    _add_executed(plugin, "test_f.py::test_pass", "passed")
    _add_executed(plugin, "test_f.py::test_fail", "failed")

    table = plugin._generate_table(SUITE)

    assert "50% (2" not in str(table.columns[4]._cells)
    assert any(
        "red" in str(cell) and "50%" in str(cell) for cell in table.columns[4]._cells
    )


def test_feedback_average_reports_how_many_tests_it_covers() -> None:
    """A mean over 2 of 5 tests should not read like a mean over all 5."""
    plugin = _make_plugin()
    _add_executed(plugin, "test_f.py::test_a", "passed", feedback={"correctness": 1})
    _add_executed(plugin, "test_f.py::test_b", "passed", feedback={"correctness": 0})
    for i in range(3):
        plugin.collected_by_suite[SUITE].add(f"test_f.py::test_skip{i}")
        plugin.unrun_statuses[f"test_f.py::test_skip{i}"] = "skipped"

    output = _render(plugin)

    assert "correctness: 0.5 (2/5)" in output


def test_empty_suite_reports_no_rate() -> None:
    plugin = _make_plugin()
    plugin.test_suites[SUITE] = []

    assert "Passed: --" in _render(plugin)


@pytest.mark.parametrize(
    "status",
    [("error", "E", "ERROR"), ("skipped", "s", "SKIPPED"), ("passed", ".", "PASSED")],
)
def test_teststatus_blanks_the_letter_but_keeps_the_category(status) -> None:
    """Blanking the category would drop these tests from pytest's own counts."""
    config = mock.Mock()
    config.getoption.return_value = True

    gen = pytest_report_teststatus(mock.Mock(), config)
    next(gen)
    result = Result(status, None)
    with pytest.raises(StopIteration):
        gen.send(result)

    category, letter, verbose_word = result.get_result()
    assert category == status[0]
    assert letter == ""
    assert verbose_word == status[2]


def test_teststatus_left_alone_without_the_flag() -> None:
    config = mock.Mock()
    config.getoption.return_value = False

    gen = pytest_report_teststatus(mock.Mock(), config)
    next(gen)
    result = Result(("passed", ".", "PASSED"), None)
    with pytest.raises(StopIteration):
        gen.send(result)

    assert result.get_result() == ("passed", ".", "PASSED")


def test_output_args_keep_pytest_counts() -> None:
    """-qq would hide the end-of-run counts the table cannot replace."""
    args = ["--langsmith-output"]
    _handle_output_args(args)

    assert "-q" in args
    assert "-qq" not in args


def test_output_args_respect_an_explicit_quiet_flag() -> None:
    args = ["--langsmith-output", "-qq"]
    _handle_output_args(args)

    assert args.count("-q") == 0


COLLECTION_SAMPLE = """
import pytest

@pytest.mark.langsmith
def test_marked(): pass

@pytest.mark.langsmith(test_suite_name="explicit-suite")
def test_marked_with_suite(): pass

@pytest.mark.langsmith
@pytest.mark.parametrize("x", [1, 2])
def test_parametrized(x): pass

def test_unmarked(): pass
"""

COLLECTION_CONFTEST = """
import json, os
from langsmith.pytest_plugin import _collected_test_suite_name

def pytest_collection_finish(session):
    resolved = {i.nodeid: _collected_test_suite_name(i) for i in session.items}
    with open(os.environ["RESOLVED_OUT"], "w") as f:
        json.dump(resolved, f)
"""


def test_collection_resolves_the_suite_for_marked_tests(tmp_path) -> None:
    """The denominator depends on naming suites the same way the decorator does."""
    import json
    import pathlib
    import subprocess
    import sys

    import langsmith

    (tmp_path / "test_collect_sample.py").write_text(COLLECTION_SAMPLE)
    (tmp_path / "conftest.py").write_text(COLLECTION_CONFTEST)
    out = tmp_path / "resolved.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            # Collection runs outside the source tree, so point at the copy of
            # langsmith under test rather than whatever is installed.
            "PYTHONPATH": str(pathlib.Path(langsmith.__file__).parents[1]),
            "RESOLVED_OUT": str(out),
            "LANGSMITH_TEST_SUITE": "env-suite",
        },
        check=True,
        capture_output=True,
    )
    resolved = json.loads(out.read_text())

    # Unmarked tests belong to no suite and must not inflate any denominator.
    assert resolved["test_collect_sample.py::test_unmarked"] is None
    assert resolved["test_collect_sample.py::test_marked"] == "env-suite"
    # An explicit suite on the marker wins, exactly as the decorator resolves it.
    assert resolved["test_collect_sample.py::test_marked_with_suite"] == (
        "explicit-suite"
    )
    # Parametrized cases are separate rows, keyed by their full node id.
    assert resolved["test_collect_sample.py::test_parametrized[1]"] == "env-suite"
    assert resolved["test_collect_sample.py::test_parametrized[2]"] == "env-suite"
