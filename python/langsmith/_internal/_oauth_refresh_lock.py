"""Cross-process filesystem lock for OAuth token refresh.

Mirrors langsmith-go: ``fcntl.flock`` on POSIX, an atomic-``mkdir`` directory
lock with a stale-break heuristic and owner-checked unlock elsewhere. The lock
serializes refresh across processes sharing one profile config file.
"""

from __future__ import annotations

import contextlib
import datetime
import errno
import os
import secrets
import shutil
import time
from collections.abc import Iterator
from typing import Optional

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore

_LOCK_POLL_INTERVAL = 0.01
_LOCK_STALE_AFTER = 10.0
_LOCK_METADATA_FILE = "created_at"


def _now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )


def _force_remove(path: str) -> None:
    try:
        shutil.rmtree(path)
    except OSError:
        pass


def _write_lock_metadata(lock_dir: str, owner: str) -> None:
    meta = os.path.join(lock_dir, _LOCK_METADATA_FILE)
    with open(meta, "w", encoding="utf-8") as f:
        f.write(_now_iso() + "\n" + owner + "\n")
    os.chmod(meta, 0o600)


def _lock_metadata_lines(lock_dir: str) -> Optional[list[str]]:
    try:
        with open(os.path.join(lock_dir, _LOCK_METADATA_FILE), encoding="utf-8") as f:
            return f.read().split("\n")
    except OSError:
        return None


def _lock_created_at(lock_dir: str) -> Optional[float]:
    lines = _lock_metadata_lines(lock_dir)
    if lines and lines[0].strip():
        try:
            parsed = datetime.datetime.fromisoformat(
                lines[0].strip().replace("Z", "+00:00")
            )
            return parsed.timestamp()
        except ValueError:
            pass
    try:
        return os.stat(lock_dir).st_mtime
    except OSError:
        return None


def _lock_owner(lock_dir: str) -> Optional[str]:
    lines = _lock_metadata_lines(lock_dir)
    if lines and len(lines) >= 2 and lines[1].strip():
        return lines[1].strip()
    return None


def _remove_stale_lock(lock_dir: str) -> bool:
    created_at = _lock_created_at(lock_dir)
    if created_at is None or time.time() - created_at <= _LOCK_STALE_AFTER:
        return False
    _force_remove(lock_dir)
    return True


def _release_dir_lock(lock_dir: str, owner: str) -> None:
    if _lock_owner(lock_dir) != owner:
        return
    _force_remove(lock_dir)


@contextlib.contextmanager
def _dir_lock(lock_dir: str, deadline: float) -> Iterator[None]:
    owner = secrets.token_hex(16)
    while True:
        try:
            os.mkdir(lock_dir, 0o700)
        except FileExistsError:
            if not _remove_stale_lock(lock_dir):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out acquiring OAuth refresh lock")
                time.sleep(min(_LOCK_POLL_INTERVAL, remaining))
            continue
        try:
            _write_lock_metadata(lock_dir, owner)
        except OSError:
            _force_remove(lock_dir)
            raise
        break
    try:
        yield
    finally:
        _release_dir_lock(lock_dir, owner)


@contextlib.contextmanager
def _flock_lock(lock_path: str, deadline: float) -> Iterator[None]:
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out acquiring OAuth refresh lock")
            time.sleep(min(_LOCK_POLL_INTERVAL, remaining))
        try:
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(fd)


def oauth_refresh_lock(config_path, *, deadline: float):
    """Acquire an exclusive cross-process lock for refreshing OAuth tokens.

    ``config_path`` is the profile config file path; the lock lives beside it.
    ``deadline`` is a ``time.monotonic()`` value; acquisition raises
    ``TimeoutError`` if it cannot be obtained before then. The caller treats any
    ``OSError`` (incl. ``TimeoutError``) as "skip refresh, use current token".
    """
    lock_path = f"{os.fspath(config_path)}.oauth.lock"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    if fcntl is not None:
        return _flock_lock(lock_path, deadline)
    return _dir_lock(f"{lock_path}.lock", deadline)
