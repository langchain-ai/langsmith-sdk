"""Helpers and type definitions for sandbox run configuration."""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class SandboxRunConfig(TypedDict, total=False):
    """What a sandbox's commands run with.

    Mirrors ``docker run -u/-w/-e``: ``user`` and ``work_dir`` replace the
    value inherited from the layer below (the image, then the snapshot, then
    the sandbox), while ``env_vars`` merge over it key by key.
    """

    user: str
    work_dir: str
    env_vars: dict[str, str]


_RUN_CONFIG_KEYS = frozenset({"user", "work_dir", "env_vars"})


def validate_run_config(
    run_config: Optional[SandboxRunConfig], field: str = "run_config"
) -> Optional[SandboxRunConfig]:
    """Check a run config client-side and return it unchanged.

    Args:
        run_config: Run config to check. ``None`` passes.
        field: Name to use in error messages.

    Returns:
        The run config as given.

    Raises:
        ValueError: If the shape, ``work_dir`` or ``env_vars`` are invalid.
    """
    if run_config is None:
        return None
    if not isinstance(run_config, dict):
        raise ValueError(f"{field} must be a mapping")
    unknown = sorted(set(run_config) - _RUN_CONFIG_KEYS)
    if unknown:
        raise ValueError(
            f"{field} has unsupported keys: {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(_RUN_CONFIG_KEYS))}"
        )
    user = run_config.get("user")
    if user is not None and (not isinstance(user, str) or not user.strip()):
        raise ValueError(f"{field}['user'] must be a non-empty string")
    work_dir = run_config.get("work_dir")
    if work_dir is not None:
        if not isinstance(work_dir, str) or not work_dir.strip():
            raise ValueError(f"{field}['work_dir'] must be a non-empty string")
        if not work_dir.startswith("/"):
            raise ValueError(f"{field}['work_dir'] must be an absolute path")
    env_vars: Any = run_config.get("env_vars")
    if env_vars is not None:
        if not isinstance(env_vars, dict):
            raise ValueError(f"{field}['env_vars'] must be a mapping")
        for name, value in env_vars.items():
            if not isinstance(name, str) or not name:
                raise ValueError(f"{field}['env_vars'] names must be strings")
            if not isinstance(value, str):
                raise ValueError(f"{field}['env_vars'][{name!r}] must be a string")
    return run_config


def validate_command_run_config(
    run_config: Optional[SandboxRunConfig],
    env: Optional[dict[str, str]],
    cwd: Optional[str],
) -> Optional[SandboxRunConfig]:
    """Check a per-command run config against the deprecated ``env``/``cwd``.

    The server rejects a request carrying both spellings, so reject it here
    with a message that names the replacement.

    Args:
        run_config: Per-command run config.
        env: Deprecated per-command environment.
        cwd: Deprecated per-command working directory.

    Returns:
        The run config as given.

    Raises:
        ValueError: If ``run_config`` is combined with ``env`` or ``cwd``, or
            if the run config itself is invalid.
    """
    if run_config is not None and (env is not None or cwd is not None):
        combined = " and ".join(
            name for name, value in (("env", env), ("cwd", cwd)) if value is not None
        )
        raise ValueError(
            f"run_config cannot be combined with {combined}; "
            "env is deprecated in favour of run_config['env_vars'] and "
            "cwd in favour of run_config['work_dir']"
        )
    return validate_run_config(run_config)
