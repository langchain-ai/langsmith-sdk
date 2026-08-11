"""Unit tests for experiment-level metadata in the pytest integration."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

import langsmith.env._git as git_env
from langsmith.evaluation._runner import _ExperimentManager
from langsmith.testing._internal import (
    _end_tests,
    _get_test_suite,
    _LangSmithTestSuite,
    _start_experiment,
)


def _make_dataset(name: str = "my-suite") -> MagicMock:
    dataset = MagicMock()
    dataset.id = uuid.uuid4()
    dataset.name = name
    dataset.modified_at = None
    dataset.metadata = {"runtime": {"sdk_version": "0.4.33"}}
    dataset.url = "https://smith.langchain.com/datasets/fake"
    return dataset


def _make_experiment(name: str = "my-suite:abc123") -> MagicMock:
    experiment = MagicMock()
    experiment.id = uuid.uuid4()
    experiment.name = name
    experiment.start_time = None
    return experiment


def _make_client(dataset: MagicMock, experiment: MagicMock) -> MagicMock:
    client = MagicMock()
    client.api_url = "https://api.smith.langchain.com"
    client.has_dataset.return_value = True
    client.read_dataset.return_value = dataset
    client.create_project.return_value = experiment
    return client


def _patch_git_remote(monkeypatch: pytest.MonkeyPatch, remote_url: str) -> None:
    outputs = {
        ("rev-parse", "--is-inside-work-tree"): "true",
        ("remote", "get-url", "origin"): remote_url,
        ("rev-parse", "HEAD"): "abc123",
        ("log", "-1", "--format=%ct"): "1720000000",
        ("rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("describe", "--tags", "--exact-match", "--always", "--dirty"): "abc123",
        ("status", "--porcelain"): "",
        ("log", "-1", "--format=%an"): "LangSmith",
        ("log", "-1", "--format=%ae"): "langsmith@example.com",
        ("rev-parse", "--show-toplevel"): "/workspace/langsmith-sdk",
    }

    def fake_exec_git(command: list[str]) -> str | None:
        return outputs.get(tuple(command))

    monkeypatch.setattr(git_env, "exec_git", fake_exec_git)
    git_env.get_git_info.cache_clear()


# ---------------------------------------------------------------------------
# _start_experiment
# ---------------------------------------------------------------------------


def test_start_experiment_no_user_metadata():
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    with patch("langsmith.testing._internal.ls_env") as mock_env:
        mock_env.get_langchain_env_var_metadata.return_value = {"revision_id": "abc"}
        mock_env.get_git_info.return_value = {}
        _start_experiment(client, dataset, experiment_metadata=None)

    client.create_project.assert_called_once()
    _, create_kwargs = client.create_project.call_args
    metadata = create_kwargs["metadata"]
    assert metadata["__ls_runner"] == "pytest"
    assert metadata["revision_id"] == "abc"
    # No extra user keys
    assert set(metadata.keys()) == {"__ls_runner", "revision_id"}


def test_start_experiment_with_user_metadata():
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    user_meta = {"model": "gpt-4o", "team": "ml"}

    with patch("langsmith.testing._internal.ls_env") as mock_env:
        mock_env.get_langchain_env_var_metadata.return_value = {"revision_id": "abc"}
        mock_env.get_git_info.return_value = {}
        _start_experiment(client, dataset, experiment_metadata=user_meta)

    _, create_kwargs = client.create_project.call_args
    metadata = create_kwargs["metadata"]
    assert metadata["model"] == "gpt-4o"
    assert metadata["team"] == "ml"
    # System keys still present
    assert metadata["__ls_runner"] == "pytest"
    assert metadata["revision_id"] == "abc"


def test_start_experiment_system_keys_take_precedence():
    """User-provided keys must not overwrite system-managed keys."""
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    # User tries to override __ls_runner
    user_meta = {"__ls_runner": "custom", "model": "gpt-4o"}

    with patch("langsmith.testing._internal.ls_env") as mock_env:
        mock_env.get_langchain_env_var_metadata.return_value = {"revision_id": "abc"}
        mock_env.get_git_info.return_value = {}
        _start_experiment(client, dataset, experiment_metadata=user_meta)

    _, create_kwargs = client.create_project.call_args
    metadata = create_kwargs["metadata"]
    # System key wins
    assert metadata["__ls_runner"] == "pytest"
    assert metadata["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# _end_tests
# ---------------------------------------------------------------------------


def test_end_tests_includes_experiment_metadata():
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    user_meta = {"model": "gpt-4o", "env": "staging"}
    suite = _LangSmithTestSuite(
        client, experiment, dataset, experiment_metadata=user_meta
    )
    # Prevent the atexit handler registered in __init__ from running during the test
    suite._executor = MagicMock()
    suite._executor.shutdown = MagicMock()
    suite._dataset_version = None

    with patch("langsmith.testing._internal.ls_env") as mock_env:
        mock_env.get_git_info.return_value = {"commit": "abc123", "branch": "main"}
        mock_env.get_langchain_env_var_metadata.return_value = {"revision_id": "rev1"}
        _end_tests(suite)

    client.update_project.assert_called_once()
    _, update_kwargs = client.update_project.call_args
    metadata = update_kwargs["metadata"]
    assert metadata["model"] == "gpt-4o"
    assert metadata["env"] == "staging"
    assert metadata["__ls_runner"] == "pytest"
    assert metadata["commit"] == "abc123"


def test_end_tests_system_keys_take_precedence():
    """Even in the final update, system keys must win over user-provided ones."""
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    user_meta = {"__ls_runner": "custom", "revision_id": "user-rev"}
    suite = _LangSmithTestSuite(
        client, experiment, dataset, experiment_metadata=user_meta
    )
    suite._executor = MagicMock()
    suite._executor.shutdown = MagicMock()
    suite._dataset_version = None

    with patch("langsmith.testing._internal.ls_env") as mock_env:
        mock_env.get_git_info.return_value = {}
        mock_env.get_langchain_env_var_metadata.return_value = {
            "revision_id": "sys-rev"
        }
        _end_tests(suite)

    _, update_kwargs = client.update_project.call_args
    metadata = update_kwargs["metadata"]
    assert metadata["__ls_runner"] == "pytest"
    assert metadata["revision_id"] == "sys-rev"


def test_git_remote_sanitized_in_test_suite_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_remote_url = "https://user:token@github.com/langchain-ai/langsmith-sdk.git"
    sanitized_remote_url = "https://github.com/langchain-ai/langsmith-sdk.git"
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)
    client.has_dataset.return_value = False
    client.create_dataset.return_value = dataset
    _patch_git_remote(monkeypatch, raw_remote_url)
    try:
        assert _get_test_suite(client, "my-suite") is dataset
        _, create_kwargs = client.create_dataset.call_args
        assert raw_remote_url not in create_kwargs["description"]
        assert sanitized_remote_url in create_kwargs["description"]

        suite = _LangSmithTestSuite(client, experiment, dataset)
        suite._executor = MagicMock()
        suite._executor.shutdown = MagicMock()
        suite._dataset_version = None
        _end_tests(suite)

        _, update_kwargs = client.update_project.call_args
        metadata = update_kwargs["metadata"]
        assert metadata["remote_url"] == sanitized_remote_url
        assert raw_remote_url not in json.dumps(metadata, default=str)
    finally:
        git_env.get_git_info.cache_clear()


def test_git_remote_sanitized_in_evaluation_project_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_remote_url = "https://user:token@github.com/langchain-ai/langsmith-sdk.git"
    sanitized_remote_url = "https://github.com/langchain-ai/langsmith-sdk.git"
    dataset_id = uuid.uuid4()
    example = MagicMock()
    example.dataset_id = dataset_id
    example.modified_at = None
    example.metadata = {}
    experiment = _make_experiment()
    experiment.metadata = {}
    experiment.reference_dataset_id = dataset_id
    experiment.url = None
    client = MagicMock()
    client.create_project.return_value = experiment
    _patch_git_remote(monkeypatch, raw_remote_url)
    try:
        manager = _ExperimentManager(
            [example], experiment="my-experiment", client=client, num_examples=1
        )
        started_manager = manager.start()
        _, create_kwargs = client.create_project.call_args
        create_metadata = create_kwargs["metadata"]
        assert create_metadata["git"]["remote_url"] == sanitized_remote_url
        assert raw_remote_url not in json.dumps(create_metadata, default=str)

        started_manager._end()
        _, update_kwargs = client.update_project.call_args
        update_metadata = update_kwargs["metadata"]
        assert update_metadata["git"]["remote_url"] == sanitized_remote_url
        assert raw_remote_url not in json.dumps(update_metadata, default=str)
    finally:
        git_env.get_git_info.cache_clear()


# ---------------------------------------------------------------------------
# _LangSmithTestSuite.from_test – experiment_metadata forwarded correctly
# ---------------------------------------------------------------------------


def test_from_test_passes_experiment_metadata():
    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    user_meta = {"model": "gpt-4o"}

    def dummy_func():
        pass

    dummy_func.__module__ = "tests.my_module"

    with (
        patch("langsmith.testing._internal.rt.get_cached_client", return_value=client),
        patch(
            "langsmith.testing._internal._get_test_suite_name",
            return_value="my-suite",
        ),
        patch("langsmith.testing._internal._get_test_suite", return_value=dataset),
        patch(
            "langsmith.testing._internal._start_experiment", return_value=experiment
        ) as mock_start,
        patch.object(_LangSmithTestSuite, "_instances", {}),
    ):
        suite = _LangSmithTestSuite.from_test(
            client, dummy_func, experiment_metadata=user_meta
        )

    mock_start.assert_called_once_with(client, dataset, user_meta)
    assert suite.experiment_metadata == user_meta


# ---------------------------------------------------------------------------
# env var fallback: LANGSMITH_EXPERIMENT_METADATA
# ---------------------------------------------------------------------------


def test_env_var_experiment_metadata(monkeypatch):
    """LANGSMITH_EXPERIMENT_METADATA env var is parsed and forwarded."""
    import json

    from langsmith.testing._internal import _create_test_case

    monkeypatch.setenv("LANGSMITH_EXPERIMENT_METADATA", json.dumps({"env": "ci"}))

    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)
    client.read_example.side_effect = Exception("not found")

    def dummy_func():
        pass

    dummy_func.__module__ = "tests.my_module"

    langtest_extra = {
        "client": client,
        "id": None,
        "output_keys": None,
        "test_suite_name": "my-suite",
        "cache": None,
        "metadata": None,
        "experiment_metadata": None,  # Not set explicitly
        "repetitions": 1,
        "split": None,
        "cached_hosts": None,
    }

    with (
        patch("langsmith.testing._internal._get_test_suite", return_value=dataset),
        patch(
            "langsmith.testing._internal._start_experiment", return_value=experiment
        ) as mock_start,
        patch.object(_LangSmithTestSuite, "_instances", {}),
    ):
        _create_test_case(
            dummy_func,
            pytest_request=None,
            langtest_extra=langtest_extra,
        )

    mock_start.assert_called_once_with(client, dataset, {"env": "ci"})


def test_env_var_invalid_json_raises(monkeypatch):
    """Invalid JSON in LANGSMITH_EXPERIMENT_METADATA raises ValueError."""
    from langsmith.testing._internal import _create_test_case

    monkeypatch.setenv("LANGSMITH_EXPERIMENT_METADATA", "not-valid-json{")

    dataset = _make_dataset()
    experiment = _make_experiment()
    client = _make_client(dataset, experiment)

    def dummy_func():
        pass

    dummy_func.__module__ = "tests.my_module"

    langtest_extra = {
        "client": client,
        "id": None,
        "output_keys": None,
        "test_suite_name": "my-suite",
        "cache": None,
        "metadata": None,
        "experiment_metadata": None,
        "repetitions": 1,
        "split": None,
        "cached_hosts": None,
    }

    with (
        patch("langsmith.testing._internal._get_test_suite", return_value=dataset),
        patch("langsmith.testing._internal._start_experiment", return_value=experiment),
        patch.object(_LangSmithTestSuite, "_instances", {}),
        pytest.raises(ValueError, match="LANGSMITH_EXPERIMENT_METADATA"),
    ):
        _create_test_case(
            dummy_func,
            pytest_request=None,
            langtest_extra=langtest_extra,
        )
