"""LangSmith Pytest hooks."""

import importlib.util
import json
import os
import time
from threading import Lock

import pytest

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


def pytest_cmdline_preparse(config, args):
    """Call immediately after command line options are parsed."""
    if any(opt in args for opt in ["--output=langsmith", "--output=ls"]):
        # Only add --quiet if it's not already there
        if not any(a in args for a in ["-q", "--quiet"]):
            args.insert(0, "--quiet")


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
            item._fixtureinfo.argnames += ("request",)
    yield


def pytest_sessionstart(session):
    """Conditionally remove the terminalreporter plugin."""
    if session.config.getoption("--output") in ("langsmith", "ls"):
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        if tr:
            session.config.pluginmanager.unregister(tr)


class LangSmithPlugin:
    """Plugin for rendering LangSmith results."""

    def __init__(self):
        """Initialize."""
        from rich.console import Console  # type: ignore[import-not-found]
        from rich.live import Live  # type: ignore[import-not-found]

        self.process_status = {}  # Track process status
        self.status_lock = Lock()  # Thread-safe updates
        self.console = Console()

        self.live = Live(self.generate_table(), refresh_per_second=4)
        self.live.start()

    def update_process_status(self, process_id, status):
        """Update test results."""
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
        self.live.update(self.generate_table())

    def pytest_runtest_logstart(self, nodeid):
        """Initialize live display when first test starts."""
        self.update_process_status(nodeid, {"status": "running"})

    def generate_table(self):
        """Generate results table."""
        from rich.table import Table  # type: ignore[import-not-found]

        table = Table()
        table.add_column("Test")
        table.add_column("Inputs")
        table.add_column("Ref outputs")
        table.add_column("Outputs")
        table.add_column("Status")
        table.add_column("Feedback")
        table.add_column("Duration")

        # Test, inputs, ref outputs, outputs col width
        max_status = len("status")
        max_feedback = len("feedback")
        max_duration = len("duration")
        now = time.time()
        for pid, status in self.process_status.items():
            duration = status.get("end_time", now) - status.get("start_time", now)
            feedback = "\n".join(
                f"{k}: {v}" for k, v in status.get("feedback", {}).items()
            )
            max_duration = max(len(f"{duration:.2f}s"), max_duration)
            max_status = max(len(status.get("status", "queued")), max_status)
            max_feedback = max(len(feedback), max_feedback)

        max_dynamic_col_width = (
            self.console.width - (max_status + max_feedback + max_duration)
        ) // 4

        for pid, status in self.process_status.items():
            status_color = {
                "running": "yellow",
                "passed": "green",
                "failed": "red",
                "skipped": "cyan",
            }.get(status.get("status", "queued"), "white")

            duration = status.get("end_time", now) - status.get("start_time", now)
            feedback = "\n".join(
                f"{k}: {v}" for k, v in status.get("feedback", {}).items()
            )
            inputs = json.dumps(status.get("inputs", {}))
            reference_outputs = json.dumps(status.get("reference_outputs", {}))
            outputs = json.dumps(status.get("outputs", {}))
            table.add_row(
                _abbreviate_test_name(str(pid), max_len=max_dynamic_col_width),
                _abbreviate(inputs, max_len=max_dynamic_col_width),
                _abbreviate(reference_outputs, max_len=max_dynamic_col_width),
                _abbreviate(outputs, max_len=max_dynamic_col_width),
                f"[{status_color}]{status.get('status', 'queued')}[/{status_color}]",
                feedback,
                f"{duration:.2f}s",
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
        config.pluginmanager.register(LangSmithPlugin(), "langsmith_plugin")
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
