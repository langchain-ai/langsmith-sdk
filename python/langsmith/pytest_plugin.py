"""LangSmith Pytest hooks."""

import importlib.util
import json
import logging
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Any

import pytest

from langsmith import utils as ls_utils
from langsmith.testing._internal import _get_test_suite_name
from langsmith.testing._internal import test as ls_test

_REPORTED_STATUSES = {"passed", "failed", "skipped"}

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Set a boolean flag for LangSmith output.

    Skip if --langsmith-output is already defined.
    """
    try:
        # Try to add the option, will raise if it already exists
        group = parser.getgroup("langsmith", "LangSmith")
        group.addoption(
            "--langsmith-output",
            action="store_true",
            default=False,
            help="Use LangSmith output (requires 'rich').",
        )
    except ValueError:
        # Option already exists
        logger.warning(
            "LangSmith output flag cannot be added because it's already defined."
        )


def _handle_output_args(args):
    """Handle output arguments."""
    if any(opt in args for opt in ["--langsmith-output"]):
        # Only add --quiet if it's not already there
        if not any(a in args for a in ["-qq"]):
            args.insert(0, "-qq")
        # Disable built-in output capturing
        if not any(a in args for a in ["-s", "--capture=no"]):
            args.insert(0, "-s")


if pytest.__version__.startswith("7."):

    def pytest_cmdline_preparse(config, args):
        """Call immediately after command line options are parsed (pytest v7)."""
        _handle_output_args(args)

else:

    def pytest_load_initial_conftests(args):
        """Handle args in pytest v8+."""
        _handle_output_args(args)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Apply LangSmith tracking to tests marked with @pytest.mark.langsmith."""
    marker = item.get_closest_marker("langsmith")
    if marker:
        # Get marker kwargs if any (e.g.,
        # @pytest.mark.langsmith(output_keys=["expected"]))
        kwargs = marker.kwargs if marker else {}
        # Inject experiment_metadata from session-scoped fixture if available
        # and not already explicitly set in the marker kwargs
        request_obj = getattr(item, "_request", None)
        if "experiment_metadata" not in kwargs and request_obj is not None:
            try:
                experiment_metadata = request_obj.getfixturevalue(
                    "langsmith_experiment_metadata"
                )
                if experiment_metadata is not None:
                    kwargs = {**kwargs, "experiment_metadata": experiment_metadata}
            except pytest.FixtureLookupError:
                pass
        # Wrap the test function with our test decorator
        original_func = item.obj
        item.obj = ls_test(**kwargs)(original_func)
        if request_obj is not None and "request" not in item.funcargs:
            item.funcargs["request"] = request_obj
        if request_obj is not None and "request" not in item._fixtureinfo.argnames:
            # Create a new FuncFixtureInfo instance with updated argnames
            item._fixtureinfo = type(item._fixtureinfo)(
                argnames=item._fixtureinfo.argnames + ("request",),
                initialnames=item._fixtureinfo.initialnames,
                names_closure=item._fixtureinfo.names_closure,
                name2fixturedefs=item._fixtureinfo.name2fixturedefs,
            )
    yield


@pytest.hookimpl
def pytest_report_teststatus(report, config):
    """Remove the short test-status character outputs ("./F")."""
    # The hook normally returns a 3-tuple: (short_letter, verbose_word, color)
    # By returning empty strings, the progress characters won't show.
    if config.getoption("--langsmith-output"):
        return "", "", ""


class LangSmithPlugin:
    """Plugin for rendering LangSmith results."""

    def __init__(self):
        """Initialize."""
        from rich.console import Console  # type: ignore[import-not-found]
        from rich.live import Live  # type: ignore[import-not-found]

        self.test_suites = defaultdict(list)
        self.test_suite_urls = {}
        self.langsmith_nodeids = set()
        self.completed_nodeids = set()

        self.process_status = {}  # Track process status
        self.status_lock = Lock()  # Thread-safe updates
        self.console = Console()

        self.live = Live(
            self.generate_tables(), console=self.console, refresh_per_second=10
        )
        self.live.start()
        self.live.console.print("Collecting tests...")

    def pytest_collection_finish(self, session):
        """Group collected LangSmith tests by suite."""
        self.collected_nodeids = set()
        self.langsmith_nodeids = set()
        self.completed_nodeids = set()
        for item in session.items:
            self.collected_nodeids.add(item.nodeid)
            marker = item.get_closest_marker("langsmith")
            if marker:
                self.langsmith_nodeids.add(item.nodeid)
                test_suite = marker.kwargs.get("test_suite_name") or (
                    _get_test_suite_name(item.obj)
                )
                self.add_process_to_test_suite(test_suite, item.nodeid)

    def add_process_to_test_suite(self, test_suite, process_id):
        """Group a test case with its test suite."""
        if process_id not in self.test_suites[test_suite]:
            self.test_suites[test_suite].append(process_id)

    def update_process_status(self, process_id, status):
        """Update test results."""
        # First update
        if not self.process_status:
            self.live.console.print("Running tests...")

        if status.get("status") in _REPORTED_STATUSES:
            status = {**status, "_reported": True}
        with self.status_lock:
            current_status = self.process_status.get(process_id, {})
            self.process_status[process_id] = _merge_statuses(
                status,
                current_status,
                unpack=["feedback", "inputs", "reference_outputs", "outputs"],
            )
        self.live.update(self.generate_tables())

    def pytest_runtest_logstart(self, nodeid):
        """Initialize live display when first test starts."""
        self.update_process_status(nodeid, {"status": "running"})

    def pytest_runtest_logreport(self, report):
        """Track pytest completion and failures for LangSmith tests."""
        if report.nodeid not in self.langsmith_nodeids:
            return
        should_render = False
        with self.status_lock:
            current_status = self.process_status.get(report.nodeid, {})
            if report.failed and not (
                report.when == "call" and current_status.get("status") == "failed"
            ):
                self.process_status[report.nodeid] = {
                    **current_status,
                    "status": "error",
                }
                should_render = True
            elif (
                report.when == "teardown"
                and report.skipped
                and current_status.get("status") == "passed"
            ):
                self.process_status[report.nodeid] = {
                    **current_status,
                    "status": "skipped",
                }
                should_render = True
            if report.when == "teardown":
                self.completed_nodeids.add(report.nodeid)
        if should_render:
            self.live.update(self.generate_tables())

    def generate_tables(self):
        """Generate a collection of tables—one per suite.

        Returns a 'Group' object so it can be rendered simultaneously by Rich Live.
        """
        from rich.console import Group

        tables = []
        for suite_name in self.test_suites:
            table = self._generate_table(suite_name)
            tables.append(table)
        group = Group(*tables)
        return group

    def _generate_table(self, suite_name: str):
        """Generate results table."""
        from rich.table import Table  # type: ignore[import-not-found]

        process_ids = self.test_suites[suite_name]

        title = f"""Test Suite: [bold]{suite_name}[/bold]
LangSmith URL: [bright_cyan]{self.test_suite_urls.get(suite_name, "--")}[/bright_cyan]"""  # noqa: E501
        table = Table(title=title, title_justify="left")
        table.add_column("Test")
        table.add_column("Inputs")
        table.add_column("Ref outputs")
        table.add_column("Outputs")
        table.add_column("Status")
        table.add_column("Feedback")
        table.add_column("Duration")

        # Test, inputs, ref outputs, outputs col width
        max_status = len("status")
        max_duration = len("duration")
        now = time.time()
        durations = []
        numeric_feedbacks = defaultdict(list)
        # Gather data only for this suite
        suite_statuses = {pid: self.process_status.get(pid, {}) for pid in process_ids}
        for pid, status in suite_statuses.items():
            duration = status.get("end_time", now) - status.get("start_time", now)
            durations.append(duration)
            for k, v in status.get("feedback", {}).items():
                if isinstance(v, (float, int, bool)):
                    numeric_feedbacks[k].append(v)
            max_duration = max(len(f"{duration:.2f}s"), max_duration)
            max_status = max(len(status.get("status", "queued")), max_status)

        aggregate_status = _format_aggregate_status(
            suite_statuses.values(), len(process_ids)
        )
        if durations:
            aggregate_duration = f"{sum(durations) / len(durations):.2f}s"
        else:
            aggregate_duration = "--s"
        if numeric_feedbacks:
            aggregate_feedback = "\n".join(
                f"{k}: {sum(v) / len(v)}" for k, v in numeric_feedbacks.items()
            )
        else:
            aggregate_feedback = "--"

        max_duration = max(max_duration, len(aggregate_duration))
        max_dynamic_col_width = (self.console.width - (max_status + max_duration)) // 5
        max_dynamic_col_width = max(max_dynamic_col_width, 8)

        for pid, status in suite_statuses.items():
            status_color = {
                "running": "yellow",
                "unreported": "yellow",
                "passed": "green",
                "failed": "red",
                "error": "red",
                "skipped": "cyan",
            }.get(status.get("status", "queued"), "white")

            duration = status.get("end_time", now) - status.get("start_time", now)
            feedback = "\n".join(
                f"{_abbreviate(k, max_len=max_dynamic_col_width)}: {int(v) if isinstance(v, bool) else v}"  # noqa: E501
                for k, v in status.get("feedback", {}).items()
            )
            inputs = _dumps_with_fallback(status.get("inputs", {}))
            reference_outputs = _dumps_with_fallback(
                status.get("reference_outputs", {})
            )
            outputs = _dumps_with_fallback(status.get("outputs", {}))
            table.add_row(
                _abbreviate_test_name(str(pid), max_len=max_dynamic_col_width),
                _abbreviate(inputs, max_len=max_dynamic_col_width),
                _abbreviate(reference_outputs, max_len=max_dynamic_col_width),
                _abbreviate(outputs, max_len=max_dynamic_col_width)[
                    -max_dynamic_col_width:
                ],
                f"[{status_color}]{status.get('status', 'queued')}[/{status_color}]",
                feedback,
                f"{duration:.2f}s",
            )

        # Add a blank row or a section separator if you like:
        table.add_row("", "", "", "", "", "", "")
        # Finally, our “footer” row:
        table.add_row(
            "[bold]Averages[/bold]",
            "",
            "",
            "",
            aggregate_status,
            aggregate_feedback,
            aggregate_duration,
        )

        return table

    def pytest_configure(self, config):
        """Disable warning reporting and show no warnings in output."""
        # Disable general warning reporting
        config.option.showwarnings = False

        # Disable warning summary
        reporter = config.pluginmanager.get_plugin("warnings-plugin")
        if reporter:
            reporter.warning_summary = lambda *args, **kwargs: None

    def pytest_sessionfinish(self, session):
        """Finalize and stop Rich Live rendering."""
        with self.status_lock:
            for process_ids in self.test_suites.values():
                for process_id in process_ids:
                    status = self.process_status.get(process_id, {})
                    incomplete = process_id not in self.completed_nodeids
                    if status.get("status") != "error" and (
                        incomplete or status.get("status") not in _REPORTED_STATUSES
                    ):
                        self.process_status[process_id] = {
                            **status,
                            "status": "unreported",
                        }
        self.live.update(self.generate_tables())
        self.live.stop()
        self.live.console.print("\nFinishing up...")


def pytest_configure(config):
    """Register the 'langsmith' marker."""
    config.addinivalue_line(
        "markers", "langsmith: mark test to be tracked in LangSmith"
    )
    if config.getoption("--langsmith-output"):
        if not importlib.util.find_spec("rich"):
            msg = (
                "Must have 'rich' installed to use --langsmith-output. "
                "Please install with: `pip install -U 'langsmith[pytest]'`"
            )
            raise ValueError(msg)
        if os.environ.get("PYTEST_XDIST_TESTRUNUID"):
            msg = (
                "--langsmith-output not supported with pytest-xdist. "
                "Please remove the '--langsmith-output' option or '-n' option."
            )
            raise ValueError(msg)
        if ls_utils.test_tracking_is_disabled():
            msg = (
                "--langsmith-output not supported when env var"
                "LANGSMITH_TEST_TRACKING='false'. Please remove the"
                "'--langsmith-output' option "
                "or enable test tracking."
            )
            raise ValueError(msg)
        config.pluginmanager.register(LangSmithPlugin(), "langsmith_output_plugin")
        # Suppress warnings summary
        config.option.showwarnings = False


def _format_aggregate_status(statuses, expected_count: int) -> str:
    """Format a suite's pass and reporting rates."""
    if not expected_count:
        return "Passed: --"
    statuses = list(statuses)
    passed_count = sum(s.get("status") == "passed" for s in statuses)
    failed_count = sum(s.get("status") in {"failed", "error"} for s in statuses)
    reported_count = sum(
        s.get("_reported", s.get("status") in _REPORTED_STATUSES) for s in statuses
    )
    rate = passed_count / expected_count
    if failed_count:
        color = "red"
    elif reported_count == expected_count and passed_count == expected_count:
        color = "green"
    else:
        color = "yellow"
    return (
        f"[{color}]{rate:.0%} passed "
        f"({reported_count}/{expected_count} reported)[/{color}]"
    )


def _abbreviate(x: str, max_len: int) -> str:
    if len(x) > max_len:
        return x[: max_len - 3] + "..."
    else:
        return x


def _abbreviate_test_name(test_name: str, max_len: int) -> str:
    if len(test_name) > max_len:
        file, test = test_name.split("::")
        if len(".py::" + test) > max_len:
            return "..." + test[-(max_len - 3) :]
        file_len = max_len - len("...::" + test)
        return "..." + file[-file_len:] + "::" + test
    else:
        return test_name


def _merge_statuses(update: dict, current: dict, *, unpack: list[str]) -> dict:
    for path in unpack:
        if path_update := update.pop(path, None):
            path_current = current.get(path, {})
            if isinstance(path_update, dict) and isinstance(path_current, dict):
                current[path] = {**path_current, **path_update}
            else:
                current[path] = path_update
    return {**current, **update}


def _dumps_with_fallback(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except Exception:
        return "unserializable"
