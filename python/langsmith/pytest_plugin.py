"""LangSmith Pytest hooks."""

import importlib.util
import json
import logging
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Optional

import pytest

from langsmith import utils as ls_utils
from langsmith.testing._internal import _get_test_suite_name
from langsmith.testing._internal import test as ls_test

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
        # Only add --quiet if it's not already there. Use -q rather than -qq so
        # pytest still prints its end-of-run counts; the live table only covers
        # tests that reached a test suite, so it can't stand in for them.
        if not any(a in args for a in ["-q", "-qq", "--quiet"]):
            args.insert(0, "-q")
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


@pytest.hookimpl(hookwrapper=True)
def pytest_report_teststatus(report, config):
    """Remove the short test-status character outputs ("./F")."""
    # The hook returns a 3-tuple: (category, short_letter, verbose_word). Blanking
    # the short letter stops the progress characters from corrupting the live
    # table. The category has to be left alone: pytest tallies its end-of-run
    # counts by category, so blanking it files every test under "" and silently
    # drops passed/failed/skipped/error counts from the summary.
    outcome = yield
    if not config.getoption("--langsmith-output"):
        return
    status = outcome.get_result()
    if status is None:
        return
    category, _, verbose_word = status
    outcome.force_result((category, "", verbose_word))


class LangSmithPlugin:
    """Plugin for rendering LangSmith results."""

    def __init__(self):
        """Initialize."""
        from rich.console import Console  # type: ignore[import-not-found]
        from rich.live import Live  # type: ignore[import-not-found]

        self.test_suites = defaultdict(list)
        self.test_suite_urls = {}
        # Tests that collection assigned to each suite, including ones that never
        # run. A test only reaches self.test_suites once its body starts
        # executing, so anything that errors or skips before then is missing
        # there and would otherwise vanish from the results table entirely.
        self.collected_by_suite = defaultdict(set)
        self.collected_nodeids = set()
        # Outcomes for tests that never got far enough to report their own status.
        self.unrun_statuses = {}

        self.process_status = {}  # Track process status
        self.status_lock = Lock()  # Thread-safe updates
        self.console = Console()

        self.live = Live(
            self.generate_tables(), console=self.console, refresh_per_second=10
        )
        self.live.start()
        self.live.console.print("Collecting tests...")

    def pytest_collection_finish(self, session):
        """Call after collection phase is completed and session.items is populated."""
        self.collected_nodeids = set()
        for item in session.items:
            self.collected_nodeids.add(item.nodeid)
            suite_name = _collected_test_suite_name(item)
            if suite_name is not None:
                self.collected_by_suite[suite_name].add(item.nodeid)

    def add_process_to_test_suite(self, test_suite, process_id):
        """Group a test case with its test suite."""
        self.test_suites[test_suite].append(process_id)

    def update_process_status(self, process_id, status):
        """Update test results."""
        # First update
        if not self.process_status:
            self.live.console.print("Running tests...")

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
        """Record outcomes for tests that never reach their suite.

        A test only registers itself with a suite once its body starts running,
        so one that errors or skips during setup reports nothing of its own.
        """
        if report.when in ("setup", "teardown"):
            if report.outcome == "failed":
                self.unrun_statuses[report.nodeid] = "error"
            elif report.outcome == "skipped":
                self.unrun_statuses[report.nodeid] = "skipped"

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

        executed_ids = self.test_suites[suite_name]
        # Collected tests that never reached the suite: errored in setup, skipped
        # before the body ran, or not started yet. Without these the pass rate
        # would be computed over only the tests that got far enough to report.
        unrun_ids = self.collected_by_suite.get(suite_name, set()) - set(executed_ids)

        title = f"""Test Suite: [bold]{suite_name}[/bold]
LangSmith URL: [bright_cyan]{self.test_suite_urls[suite_name]}[/bright_cyan]"""  # noqa: E501
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
        suite_statuses = {pid: self.process_status[pid] for pid in executed_ids}
        for pid in sorted(unrun_ids):
            suite_statuses[pid] = {"status": self.unrun_statuses.get(pid, "queued")}
        for pid, status in suite_statuses.items():
            if pid not in unrun_ids:
                duration = status.get("end_time", now) - status.get("start_time", now)
                durations.append(duration)
                max_duration = max(len(f"{duration:.2f}s"), max_duration)
            for k, v in status.get("feedback", {}).items():
                if isinstance(v, (float, int, bool)):
                    numeric_feedbacks[k].append(v)
            max_status = max(len(status.get("status", "queued")), max_status)

        total_count = len(suite_statuses)
        passed_count = sum(s.get("status") == "passed" for s in suite_statuses.values())

        # You could arrange a row to show the aggregated data—here, in the last column:
        if total_count:
            rate = passed_count / total_count
            # Anything that did not pass — failed, skipped, errored, never
            # started — keeps this red, so a suite only reads green when every
            # collected test actually passed.
            color = "green" if passed_count == total_count else "red"
            aggregate_status = (
                f"[{color}]{rate:.0%} ({passed_count}/{total_count})[/{color}]"
            )
        else:
            aggregate_status = "Passed: --"
        if durations:
            aggregate_duration = f"{sum(durations) / len(durations):.2f}s"
        else:
            aggregate_duration = "--s"
        if numeric_feedbacks:
            # Show how many tests each score covers: a mean over 3 of 10 tests
            # is not the same claim as a mean over all 10.
            aggregate_feedback = "\n".join(
                f"{k}: {sum(v) / len(v)} ({len(v)}/{total_count})"
                for k, v in numeric_feedbacks.items()
            )
        else:
            aggregate_feedback = "--"

        max_duration = max(max_duration, len(aggregate_duration))
        max_dynamic_col_width = (self.console.width - (max_status + max_duration)) // 5
        max_dynamic_col_width = max(max_dynamic_col_width, 8)

        for pid, status in suite_statuses.items():
            status_color = {
                "running": "yellow",
                "passed": "green",
                "failed": "red",
                "error": "red",
                "skipped": "cyan",
            }.get(status.get("status", "queued"), "white")

            if pid in unrun_ids:
                duration_cell = "--s"
            else:
                duration = status.get("end_time", now) - status.get("start_time", now)
                duration_cell = f"{duration:.2f}s"
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
                duration_cell,
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
        """Stop Rich Live rendering at the end of the session."""
        # Tests that errored or skipped in setup never trigger a status update,
        # so render once more to make sure their rows are in the final table.
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


def _collected_test_suite_name(item) -> Optional[str]:
    """Resolve which suite a collected test belongs to, before it runs.

    Mirrors how the test decorator names a suite so the results table can show a
    denominator that includes tests which never made it to their suite.
    """
    marker = item.get_closest_marker("langsmith")
    if marker is None:
        return None
    if test_suite_name := marker.kwargs.get("test_suite_name"):
        return test_suite_name
    try:
        return _get_test_suite_name(item.obj)
    except BaseException:
        logger.debug("Could not determine test suite name for %s.", item.nodeid)
        return None


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
