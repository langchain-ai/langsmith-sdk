"""Tests for the cross-process OAuth refresh lock."""

from __future__ import annotations

import datetime
import os
import time

import pytest

from langsmith._internal import _oauth_refresh_lock as lock_mod


def _write_meta(lock_dir: str, created_at: str, owner: str) -> None:
    os.makedirs(lock_dir, exist_ok=True)
    with open(
        os.path.join(lock_dir, lock_mod._LOCK_METADATA_FILE), "w", encoding="utf-8"
    ) as f:
        f.write(created_at + "\n" + owner + "\n")


def test_remove_stale_lock_breaks_expired_timestamp(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    stale = time.time() - lock_mod._LOCK_STALE_AFTER - 1
    iso = (
        datetime.datetime.fromtimestamp(stale, datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    _write_meta(lock_dir, iso, "someone-else")

    assert lock_mod._remove_stale_lock(lock_dir) is True
    assert not os.path.exists(lock_dir)


def test_remove_stale_lock_keeps_fresh_lock(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    iso = (
        datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )
    _write_meta(lock_dir, iso, "someone-else")

    assert lock_mod._remove_stale_lock(lock_dir) is False
    assert os.path.exists(lock_dir)


def test_remove_stale_lock_breaks_expired_via_mtime(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    os.mkdir(lock_dir)  # no metadata file
    stale = time.time() - lock_mod._LOCK_STALE_AFTER - 1
    os.utime(lock_dir, (stale, stale))

    assert lock_mod._remove_stale_lock(lock_dir) is True
    assert not os.path.exists(lock_dir)


def test_release_dir_lock_keeps_other_owner(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _write_meta(lock_dir, iso, "new-owner")

    lock_mod._release_dir_lock(lock_dir, "our-owner")  # owner mismatch
    assert os.path.exists(lock_dir)

    lock_mod._release_dir_lock(lock_dir, "new-owner")  # owner match
    assert not os.path.exists(lock_dir)


def test_dir_lock_acquires_and_releases(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    with lock_mod._dir_lock(lock_dir, time.monotonic() + 5):
        assert os.path.isdir(lock_dir)
    assert not os.path.exists(lock_dir)


def test_dir_lock_times_out_when_held(tmp_path):
    lock_dir = str(tmp_path / "config.json.oauth.lock.lock")
    with lock_mod._dir_lock(lock_dir, time.monotonic() + 5):
        with pytest.raises(TimeoutError):
            with lock_mod._dir_lock(lock_dir, time.monotonic() + 0.05):
                pass


def test_oauth_refresh_lock_acquires(tmp_path):
    config_path = tmp_path / "sub" / "config.json"
    with lock_mod.oauth_refresh_lock(config_path, deadline=time.monotonic() + 5):
        pass  # acquired and released without error


def test_oauth_refresh_lock_serializes_same_path(tmp_path):
    config_path = tmp_path / "config.json"
    with lock_mod.oauth_refresh_lock(config_path, deadline=time.monotonic() + 5):
        with pytest.raises((TimeoutError, OSError)):
            with lock_mod.oauth_refresh_lock(
                config_path, deadline=time.monotonic() + 0.05
            ):
                pass
