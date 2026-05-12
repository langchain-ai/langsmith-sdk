"""LangSmith profile configuration and auth helpers."""

from __future__ import annotations

import base64
import binascii
import datetime
import errno
import json
import os
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple, Optional, TypedDict, cast

import requests

_OAUTH_CLIENT_ID = "langsmith-cli"
_TOKEN_REFRESH_LEEWAY = datetime.timedelta(minutes=1)
_TOKEN_REFRESH_TIMEOUT = 10
_X_USER_ID_HEADER = "x-user-id"
_OAUTH_USER_ID_CLAIM = "sub"
_REFRESH_LOCK_POLL_SECONDS = 0.05
_REFRESH_LOCK_STALE_SECONDS = _TOKEN_REFRESH_TIMEOUT + 30
_REFRESH_LOCK_TIMEOUT_SECONDS = _REFRESH_LOCK_STALE_SECONDS + _TOKEN_REFRESH_TIMEOUT
_REFRESH_LOCKS_LOCK = threading.Lock()
_REFRESH_LOCKS: dict[tuple[Path, str], threading.Lock] = {}


class ProfileOAuth(TypedDict, total=False):
    access_token: str
    refresh_token: str
    expires_at: str


class ProfileConfig(TypedDict, total=False):
    api_key: str
    api_url: str
    workspace_id: str
    oauth: ProfileOAuth


class ProfileConfigFile(TypedDict, total=False):
    current_profile: str
    profiles: dict[str, ProfileConfig]


class ProfileState(NamedTuple):
    path: Path
    config: ProfileConfigFile
    profile_name: str


class ProfileClientConfig(NamedTuple):
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    workspace_id: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    oauth_expires_at: Optional[str] = None
    profile_state: Optional[ProfileState] = None

    @property
    def has_oauth(self) -> bool:
        return bool(self.oauth_access_token or self.oauth_refresh_token)


def trim_auth_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    trimmed = value.strip().strip('"').strip("'")
    return trimmed or None


def _profile_config_path() -> Optional[Path]:
    if config_file := os.environ.get("LANGSMITH_CONFIG_FILE"):
        return Path(config_file)
    try:
        return Path.home() / ".langsmith" / "config.json"
    except RuntimeError:
        return None


def _load_profile_state() -> Optional[ProfileState]:
    path = _profile_config_path()
    if path is None or not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return None
    profile_name = os.environ.get("LANGSMITH_PROFILE")
    if not profile_name:
        current_profile = raw.get("current_profile")
        if isinstance(current_profile, str) and current_profile:
            profile_name = current_profile
        elif "default" in profiles:
            profile_name = "default"
    if not profile_name or not isinstance(profiles.get(profile_name), dict):
        return None
    return ProfileState(path, cast(ProfileConfigFile, raw), profile_name)


def _profile_from_state(state: ProfileState) -> Optional[ProfileConfig]:
    profiles = state.config.get("profiles") or {}
    profile = profiles.get(state.profile_name)
    if not isinstance(profile, dict):
        return None
    return cast(ProfileConfig, profile)


def _reload_profile_state(state: ProfileState) -> ProfileState:
    try:
        raw = json.loads(state.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state
    if not isinstance(raw, dict):
        return state
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return state
    if not isinstance(profiles.get(state.profile_name), dict):
        return state
    return ProfileState(state.path, cast(ProfileConfigFile, raw), state.profile_name)


def _refresh_lock_for_state(state: ProfileState) -> threading.Lock:
    key = (state.path, state.profile_name)
    with _REFRESH_LOCKS_LOCK:
        lock = _REFRESH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _REFRESH_LOCKS[key] = lock
        return lock


def _refresh_lock_path(state: ProfileState) -> Path:
    return state.path.with_name(f"{state.path.name}.oauth-refresh.lock")


def _is_refresh_lock_stale(lock_path: Path) -> bool:
    try:
        modified_at = lock_path.stat().st_mtime
    except OSError:
        return False
    return time.time() - modified_at > _REFRESH_LOCK_STALE_SECONDS


def _acquire_filesystem_refresh_lock(state: ProfileState) -> Optional[Path]:
    lock_path = _refresh_lock_path(state)
    deadline = time.monotonic() + _REFRESH_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if _is_refresh_lock_stale(lock_path):
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                return None
            time.sleep(_REFRESH_LOCK_POLL_SECONDS)
            continue
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                try:
                    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                except OSError:
                    return None
                continue
            return None
        try:
            os.write(fd, str(os.getpid()).encode())
        finally:
            os.close(fd)
        return lock_path


def _release_filesystem_refresh_lock(lock_path: Optional[Path]) -> None:
    if lock_path is None:
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


def load_profile_client_config() -> ProfileClientConfig:
    state = _load_profile_state()
    if state is None:
        return ProfileClientConfig()
    profile = _profile_from_state(state)
    if profile is None:
        return ProfileClientConfig()
    oauth = profile.get("oauth") or {}
    return ProfileClientConfig(
        api_url=profile.get("api_url"),
        api_key=trim_auth_value(profile.get("api_key")),
        workspace_id=profile.get("workspace_id"),
        oauth_access_token=trim_auth_value(oauth.get("access_token")),
        oauth_refresh_token=trim_auth_value(oauth.get("refresh_token")),
        oauth_expires_at=oauth.get("expires_at"),
        profile_state=state,
    )


def _normalize_profile_api_url(api_url: str) -> str:
    while api_url.endswith("/"):
        api_url = api_url[:-1]
    suffix = "/api/v1"
    if api_url.endswith(suffix):
        return api_url[: -len(suffix)]
    return api_url


def _parse_profile_expires_at(expires_at: str) -> Optional[datetime.datetime]:
    try:
        parsed = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def should_refresh_profile_token(profile: ProfileConfig) -> bool:
    oauth = profile.get("oauth") or {}
    if not oauth.get("refresh_token"):
        return False
    if not oauth.get("access_token"):
        return True
    expires_at = oauth.get("expires_at")
    if not expires_at:
        return False
    parsed = _parse_profile_expires_at(expires_at)
    if parsed is None:
        return False
    return (
        parsed <= datetime.datetime.now(datetime.timezone.utc) + _TOKEN_REFRESH_LEEWAY
    )


def _refresh_profile_oauth_token(
    api_url: Optional[str], refresh_token: str
) -> Optional[dict[str, Any]]:
    refresh_url = _normalize_profile_api_url(
        api_url or "https://api.smith.langchain.com"
    )
    try:
        response = requests.post(
            f"{refresh_url}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": _OAUTH_CLIENT_ID,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TOKEN_REFRESH_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if response.status_code < 200 or response.status_code >= 300:
        return None
    try:
        token = response.json()
    except ValueError:
        return None
    if not isinstance(token, dict) or not token.get("access_token"):
        return None
    return token


def _apply_profile_token_response(
    profile: ProfileConfig, token: Mapping[str, Any]
) -> None:
    oauth = profile.setdefault("oauth", {})
    access_token = token.get("access_token")
    if isinstance(access_token, str) and access_token:
        oauth["access_token"] = access_token
    refresh_token = token.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        oauth["refresh_token"] = refresh_token
    expires_in = token.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=expires_in
        )
        oauth["expires_at"] = expires_at.isoformat().replace("+00:00", "Z")


def _save_profile_config(path: Path, config: ProfileConfigFile) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    except OSError:
        return


class ProfileAuth:
    def __init__(
        self,
        config: ProfileClientConfig,
        *,
        api_key_header: str,
    ) -> None:
        self._state = config.profile_state
        self._api_key_header = api_key_header
        self._managed_auth_headers: set[tuple[str, str]] = set()
        self._remember_auth_headers(self._auth_headers(refresh=False))

    @property
    def has_auth(self) -> bool:
        profile = self._profile()
        if profile is None:
            return False
        oauth = profile.get("oauth") or {}
        return bool(
            trim_auth_value(oauth.get("access_token"))
            or trim_auth_value(oauth.get("refresh_token"))
            or trim_auth_value(profile.get("api_key"))
        )

    @property
    def oauth_access_token(self) -> Optional[str]:
        profile = self._profile()
        if profile is None:
            return None
        return trim_auth_value((profile.get("oauth") or {}).get("access_token"))

    def needs_refresh(self) -> bool:
        profile = self._profile()
        return profile is not None and should_refresh_profile_token(profile)

    def current_auth_headers(self) -> dict[str, str]:
        headers = self._auth_headers(refresh=False)
        self._remember_auth_headers(headers)
        return headers

    def get_auth_headers(self) -> dict[str, str]:
        headers = self._auth_headers(refresh=True)
        self._remember_auth_headers(headers)
        return headers

    def prepare_request_headers(self, headers: Mapping[str, str]) -> dict[str, str]:
        """Replace stale profile-managed auth while preserving explicit auth."""
        request_headers = dict(headers)
        for key, value in list(request_headers.items()):
            if self._is_profile_auth_header(key, value):
                del request_headers[key]
        if not self._has_auth_header(request_headers):
            request_headers.update(self.current_auth_headers())
        return request_headers

    def _profile(self) -> Optional[ProfileConfig]:
        if self._state is None:
            return None
        return _profile_from_state(self._state)

    def _auth_headers(self, *, refresh: bool) -> dict[str, str]:
        profile = self._profile()
        if profile is None:
            return {}
        if refresh and should_refresh_profile_token(profile):
            if self._state is None:
                return self._headers_from_profile(profile)
            with _refresh_lock_for_state(self._state):
                lock_path = _acquire_filesystem_refresh_lock(self._state)
                try:
                    self._state = _reload_profile_state(self._state)
                    profile = self._profile()
                    if profile is not None and should_refresh_profile_token(profile):
                        self._refresh(profile)
                    profile = self._profile()
                finally:
                    _release_filesystem_refresh_lock(lock_path)
        return self._headers_from_profile(profile)

    def _refresh(self, profile: ProfileConfig) -> None:
        refresh_token = trim_auth_value(
            (profile.get("oauth") or {}).get("refresh_token")
        )
        if refresh_token is None or self._state is None:
            return
        api_url = profile.get("api_url")
        token = _refresh_profile_oauth_token(api_url, refresh_token)
        if token is None:
            return
        _apply_profile_token_response(profile, token)
        profiles = self._state.config.get("profiles") or {}
        profiles[self._state.profile_name] = profile
        self._state.config["profiles"] = profiles
        _save_profile_config(self._state.path, self._state.config)

    def _headers_from_profile(self, profile: Optional[ProfileConfig]) -> dict[str, str]:
        if profile is None:
            return {}
        oauth_access_token = trim_auth_value(
            (profile.get("oauth") or {}).get("access_token")
        )
        if oauth_access_token:
            headers = {"Authorization": f"Bearer {oauth_access_token}"}
            user_id = _oauth_user_id_from_access_token(oauth_access_token)
            if user_id:
                headers[_X_USER_ID_HEADER] = user_id
            return headers
        api_key = trim_auth_value(profile.get("api_key"))
        if api_key:
            return {self._api_key_header: api_key}
        return {}

    def _remember_auth_headers(self, headers: Mapping[str, str]) -> None:
        for name, value in headers.items():
            if self._is_managed_header_name(name) and value:
                self._managed_auth_headers.add((name.lower(), value))

    def _is_profile_auth_header(self, name: str, value: str) -> bool:
        return (name.lower(), value) in self._managed_auth_headers

    def _has_auth_header(self, headers: Mapping[str, str]) -> bool:
        return any(
            self._is_auth_header_name(name) and bool(value)
            for name, value in headers.items()
        )

    def _is_auth_header_name(self, name: str) -> bool:
        return name.lower() in {"authorization", self._api_key_header.lower()}

    def _is_managed_header_name(self, name: str) -> bool:
        return self._is_auth_header_name(name) or name.lower() == _X_USER_ID_HEADER


def _oauth_user_id_from_access_token(access_token: str) -> Optional[str]:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    try:
        payload = json.loads(_decode_base64_url(parts[1]))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get(_OAUTH_USER_ID_CLAIM)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _decode_base64_url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
