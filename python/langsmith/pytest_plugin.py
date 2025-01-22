"""LangSmith Pytest hooks."""

import importlib.util
import json
import os
import time
from collections import defaultdict
from threading import Lock

import pytest

from langsmith import utils as ls_utils
from langsmith.testing._internal import test as ls_test


def pytest_addoption(parser):
    """Set CLI options for choosing output format."""
    group = parser.getgroup("langsmith", "LangSmith")
    group.addoption(
        "--output",
        action="store",
        default="pytest",
        choices=["langsmith", "ls", "pytest"],
        help=(
            "Choose output format: 'langsmith' | 'ls' "
            "(rich custom LangSmith output) or 'pytest' "
            "(standard pytest). Defaults to 'pytest'."
        ),
    )


def _handle_output_args(args):
    """Handle output arguments."""
    if any(opt in args for opt in ["--output=langsmith", "--output=ls"]):
        # Only add --quiet if it's not already there
        if not any(a in args for a in ["-q", "--quiet"]):
            args.insert(0, "--quiet")
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
        # Wrap the test function with our test decorator
        original_func = item.obj
        item.obj = ls_test(**kwargs)(original_func)
        request_obj = getattr(item, "_request", None)
        if request_obj is not None and "request" not in item.funcargs:
            item.funcargs["request"] = request_obj
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
    if config.getoption("--output") in ("langsmith", "ls"):
        return "", "", ""


class LangSmithPlugin:
    """Plugin for rendering LangSmith results."""

    def __init__(self):
        """Initialize."""
        from rich.console import Console  # type: ignore[import-not-found]
        from rich.live import Live  # type: ignore[import-not-found]

        self.test_suites = defaultdict(list)
        self.test_suite_urls = {}

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
            if status.get("feedback"):
                current_status["feedback"] = {
                    **current_status.get("feedback", {}),
                    **status.pop("feedback"),
                }
            if status.get("inputs"):
                current_status["inputs"] = {
                    **current_status.get("inputs", {}),
                    **status.pop("inputs"),
                }
            if status.get("reference_outputs"):
                current_status["reference_outputs"] = {
                    **current_status.get("reference_outputs", {}),
                    **status.pop("reference_outputs"),
                }
            if status.get("outputs"):
                current_status["outputs"] = {
                    **current_status.get("outputs", {}),
                    **status.pop("outputs"),
                }
            self.process_status[process_id] = {**current_status, **status}
        self.live.update(self.generate_tables())

    def pytest_runtest_logstart(self, nodeid):
        """Initialize live display when first test starts."""
        self.update_process_status(nodeid, {"status": "running"})

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
LangSmith link: [bright_cyan][link={self.test_suite_urls[suite_name]}]⌘ + click here[/link][/bright_cyan]"""  # noqa: E501
        table = Table(title=title, title_justify="left")
        table.add_column("Test")
        table.add_column("Inputs")
        table.add_column("Ref outputs")
        table.add_column("Outputs")
        table.add_column("Status")
        table.add_column("Feedback")
        table.add_column("Duration")
        table.add_column("Logged")

        # Test, inputs, ref outputs, outputs col width
        max_status = len("status")
        max_duration = len("duration")
        now = time.time()
        durations = []
        numeric_feedbacks = defaultdict(list)
        # Gather data only for this suite
        suite_statuses = {pid: self.process_status[pid] for pid in process_ids}
        for pid, status in suite_statuses.items():
            duration = status.get("end_time", now) - status.get("start_time", now)
            durations.append(duration)
            for k, v in status.get("feedback", {}).items():
                if isinstance(v, (float, int, bool)):
                    numeric_feedbacks[k].append(v)
            max_duration = max(len(f"{duration:.2f}s"), max_duration)
            max_status = max(len(status.get("status", "queued")), max_status)

        passed_count = sum(s.get("status") == "passed" for s in suite_statuses.values())
        failed_count = sum(s.get("status") == "failed" for s in suite_statuses.values())

        # You could arrange a row to show the aggregated data—here, in the last column:
        if passed_count + failed_count:
            rate = passed_count / (passed_count + failed_count)
            color = "green" if rate == 1 else "red"
            aggregate_status = f"[{color}]{rate:.0%}[/{color}]"
        else:
            aggregate_status = "Passed: --"
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
        max_dynamic_col_width = (
            self.console.width - (max_status + max_duration + len("Logged"))
        ) // 5
        max_dynamic_col_width = max(max_dynamic_col_width, 8)

        for pid, status in suite_statuses.items():
            status_color = {
                "running": "yellow",
                "passed": "green",
                "failed": "red",
                "skipped": "cyan",
            }.get(status.get("status", "queued"), "white")

            duration = status.get("end_time", now) - status.get("start_time", now)
            feedback = "\n".join(
                f"{_abbreviate(k, max_len=max_dynamic_col_width)}: {int(v) if isinstance(v, bool) else v}"  # noqa: E501
                for k, v in status.get("feedback", {}).items()
            )
            inputs = json.dumps(status.get("inputs", {}))
            reference_outputs = json.dumps(status.get("reference_outputs", {}))
            outputs = json.dumps(status.get("outputs", {}))
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
                "x" if status.get("logged") else "",
            )

        if suite_statuses:
            logged = sum(s.get("logged", False) for s in suite_statuses.values()) / len(
                suite_statuses
            )
            aggregate_logged = f"{logged:.0%}"
        else:
            aggregate_logged = "--"

        # Add a blank row or a section separator if you like:
        table.add_row("", "", "", "", "", "", "")
        # Finally, our “footer” row:
        table.add_row(
            "[bold]Summary[/bold]",
            "",
            "",
            "",
            aggregate_status,
            aggregate_feedback,
            aggregate_duration,
            aggregate_logged,
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
        self.live.stop()


def pytest_configure(config):
    """Register the 'langsmith' marker."""
    config.addinivalue_line(
        "markers", "langsmith: mark test to be tracked in LangSmith"
    )
    if config.getoption("--output") in ("langsmith", "ls"):
        if not importlib.util.find_spec("rich"):
            msg = (
                "Must have 'rich' installed to use --output='langsmith' | 'ls'. "
                "Please install with: `pip install -U 'langsmith[pytest]'`"
            )
            raise ValueError(msg)
        if os.environ.get("PYTEST_XDIST_TESTRUNUID"):
            msg = (
                "--output='langsmith' | 'ls' not supported with pytest-xdist. "
                "Please remove the '--output' option or '-n' option."
            )
            raise ValueError(msg)
        if ls_utils.test_tracking_is_disabled():
            msg = (
                "--output='langsmith' | 'ls' not supported when env var"
                "LANGSMITH_TEST_TRACKING='false'. Please remove the '--output' option "
                "or enable test tracking."
            )
            raise ValueError(msg)
        config.pluginmanager.register(LangSmithPlugin(), "langsmith_output_plugin")
        # Suppress warnings summary
        config.option.showwarnings = False


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
