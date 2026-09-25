"""Verify tokens LangSmith signs for sandbox service URLs and proxy callbacks.

Requires the ``sandbox-auth`` extra: ``pip install "langsmith[sandbox-auth]"``.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import urlsplit

from langsmith import utils as ls_utils
from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._exceptions import SandboxClientError

if TYPE_CHECKING:
    from jwt import PyJWKSet

AudienceMatcher = Union[str, Callable[[str], bool]]

USER_TOKEN_HEADER = "X-Langsmith-User-Token"
CALLBACK_SIGNATURE_HEADER = "X-LangSmith-Signature-JWT"

_CALLBACK_SUBJECT = "langsmith-sandbox-callback"
_JWKS_PATH = "/.well-known/jwks.json"
_JWKS_TTL_SECONDS = 300.0
# Bounds refetches when a token names a kid the cached set lacks.
_JWKS_MIN_REFRESH_SECONDS = 30.0
_LEEWAY_SECONDS = 30


class SandboxTokenVerificationError(SandboxClientError):
    """Raised when a sandbox user token or callback signature fails verification."""


@dataclass(frozen=True)
class SandboxUser:
    """The LangSmith user a service URL request was made by."""

    subject: str
    email: Optional[str]
    name: Optional[str]
    expires_at: datetime


@dataclass(frozen=True)
class SandboxCallbackIdentity:
    """The sandbox whose outbound request triggered a proxy callback."""

    tenant_id: str
    sandbox_id: str
    organization_id: Optional[str]
    ls_user_id: Optional[str]


@dataclass(frozen=True)
class SandboxCallbackRequest:
    """Snapshot of the outbound request, sent for ``full_request`` callbacks."""

    method: str
    url: str
    scheme: str
    host: str
    path: str
    query: Optional[str]
    headers: dict[str, list[str]]
    body: bytes
    body_truncated: bool


@dataclass(frozen=True)
class SandboxCallback:
    """A verified proxy callback payload."""

    host: str
    port: int
    identity: SandboxCallbackIdentity
    request: Optional[SandboxCallbackRequest]


def _import_jwt() -> Any:
    try:
        import jwt
        from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Verifying sandbox tokens requires the sandbox-auth extra: "
            'pip install "langsmith[sandbox-auth]"'
        ) from e
    return jwt


def _default_jwks_url() -> str:
    base = ls_utils.get_env_var("ENDPOINT", default="https://api.smith.langchain.com")
    parts = urlsplit(base)
    return f"{parts.scheme}://{parts.netloc}{_JWKS_PATH}"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_jwks_url(url: str, allow_insecure: bool) -> None:
    parts = urlsplit(url)
    if parts.scheme == "https" or allow_insecure:
        return
    if parts.scheme == "http" and _is_loopback(parts.hostname or ""):
        return
    raise ValueError(
        f"JWKS URL must use https, got {url!r}; pass allow_insecure_jwks=True "
        "only if the network path to LangSmith is trusted"
    )


def _service_host(audience: str) -> str:
    if "://" in audience:
        host = urlsplit(audience).netloc
        if not host:
            raise ValueError(f"audience has no host: {audience!r}")
        return host
    return audience


class SandboxTokenVerifier:
    """Verifies tokens LangSmith signs for code running in or behind a sandbox.

    Keys are fetched from LangSmith's JWKS endpoint and cached.

    Example:
        verifier = SandboxTokenVerifier()

        # In an app served from a LangSmith-login service URL:
        user = verifier.verify_user_token(
            request.headers[USER_TOKEN_HEADER], audience=request.headers["Host"]
        )

        # In a proxy callback endpoint:
        callback = verifier.verify_callback(
            body=await request.body(),
            signature=request.headers[CALLBACK_SIGNATURE_HEADER],
            aud="https://example.com/sandbox-callback",
        )
    """

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        jwks_url: Optional[str] = None,
        timeout: float = 10.0,
        allow_insecure_jwks: bool = False,
    ) -> None:
        """Initialize the verifier.

        Args:
            api_url: LangSmith API URL whose origin serves the JWKS. Defaults to
                LANGSMITH_ENDPOINT.
            jwks_url: Full JWKS URL; overrides ``api_url``.
            timeout: HTTP timeout in seconds for fetching the JWKS.
            allow_insecure_jwks: Allow fetching the JWKS over plain HTTP from a
                non-loopback host. Anyone who can tamper with that traffic can
                forge tokens this verifier accepts.
        """
        self._jwt = _import_jwt()
        if jwks_url:
            self._jwks_url = jwks_url
        elif api_url:
            parts = urlsplit(api_url)
            self._jwks_url = f"{parts.scheme}://{parts.netloc}{_JWKS_PATH}"
        else:
            self._jwks_url = _default_jwks_url()
        _check_jwks_url(self._jwks_url, allow_insecure_jwks)
        self._timeout = timeout
        self._lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._afetch_lock: Optional[asyncio.Lock] = None
        self._afetch_loop: Optional[asyncio.AbstractEventLoop] = None
        self._keys: Optional[PyJWKSet] = None
        self._fetched_at = 0.0

    def verify_user_token(
        self, token: str, *, audience: str, issuer: Optional[str] = None
    ) -> SandboxUser:
        """Verify the ``X-Langsmith-User-Token`` header of a service URL request.

        LangSmith sets this header only for service URLs that use LangSmith
        login. Code that knows it is running in a sandbox can instead trust the
        unsigned ``X-Langsmith-User-Id`` and ``X-Langsmith-User-Email`` headers,
        which the sandbox runtime strips from inbound requests and sets itself;
        verify this token when that is not guaranteed.

        Args:
            token: The header value.
            audience: The service URL host the request was sent to, such as
                ``request.headers["Host"]``. A full service URL is also accepted.
            issuer: If set, the LangSmith app URL the token must be issued by.
        """
        kid = self._kid(token)
        return self._decode_user_token(token, self._key_sync(kid), audience, issuer)

    async def averify_user_token(
        self, token: str, *, audience: str, issuer: Optional[str] = None
    ) -> SandboxUser:
        """Async version of :meth:`verify_user_token`."""
        kid = self._kid(token)
        key = await self._key_async(kid)
        return self._decode_user_token(token, key, audience, issuer)

    def verify_callback(
        self,
        *,
        body: Union[bytes, str],
        signature: str,
        aud: Optional[AudienceMatcher] = None,
        issuer: Optional[str] = None,
    ) -> SandboxCallback:
        """Verify a proxy callback request and return its parsed payload.

        Args:
            body: The raw request body, exactly as received.
            signature: The ``X-LangSmith-Signature-JWT`` header value.
            aud: If set, checks the signature's audience, which is the callback
                URL as configured in the proxy config. A string must match
                exactly; a predicate is called with each audience and must
                return True for at least one.
            issuer: If set, the LangSmith OAuth issuer the signature must be
                issued by.
        """
        kid = self._kid(signature)
        return self._decode_callback(signature, self._key_sync(kid), body, aud, issuer)

    async def averify_callback(
        self,
        *,
        body: Union[bytes, str],
        signature: str,
        aud: Optional[AudienceMatcher] = None,
        issuer: Optional[str] = None,
    ) -> SandboxCallback:
        """Async version of :meth:`verify_callback`."""
        kid = self._kid(signature)
        key = await self._key_async(kid)
        return self._decode_callback(signature, key, body, aud, issuer)

    def _kid(self, token: str) -> str:
        if not token:
            raise SandboxTokenVerificationError("token is empty")
        try:
            header = self._jwt.get_unverified_header(token)
        except self._jwt.PyJWTError as e:
            raise SandboxTokenVerificationError(f"malformed token: {e}") from e
        if header.get("alg") != "EdDSA":
            raise SandboxTokenVerificationError(
                f"unexpected signing algorithm: {header.get('alg')!r}"
            )
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise SandboxTokenVerificationError("token has no kid")
        return kid

    def _decode(
        self,
        token: str,
        key: Any,
        audience: Optional[str],
        issuer: Optional[str],
        required: list[str],
    ) -> dict[str, Any]:
        try:
            return self._jwt.decode(
                token,
                key,
                algorithms=["EdDSA"],
                audience=audience,
                issuer=issuer.rstrip("/") if issuer else None,
                leeway=_LEEWAY_SECONDS,
                options={"require": required, "verify_aud": audience is not None},
            )
        except self._jwt.PyJWTError as e:
            raise SandboxTokenVerificationError(f"invalid token: {e}") from e

    def _decode_user_token(
        self, token: str, key: Any, audience: str, issuer: Optional[str]
    ) -> SandboxUser:
        claims = self._decode(
            token,
            key,
            _service_host(audience),
            issuer,
            ["exp", "iat", "iss", "aud", "sub"],
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or subject == _CALLBACK_SUBJECT:
            raise SandboxTokenVerificationError("token is not a user token")
        return SandboxUser(
            subject=subject,
            email=claims.get("email") or None,
            name=claims.get("name") or None,
            expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        )

    def _decode_callback(
        self,
        signature: str,
        key: Any,
        body: Union[bytes, str],
        aud: Optional[AudienceMatcher],
        issuer: Optional[str],
    ) -> SandboxCallback:
        claims = self._decode(
            signature,
            key,
            aud if isinstance(aud, str) else None,
            issuer,
            ["exp", "iat", "iss", "aud", "sub", "body_sha256"],
        )
        if callable(aud):
            audiences = claims["aud"]
            if isinstance(audiences, str):
                audiences = [audiences]
            if not any(isinstance(a, str) and aud(a) for a in audiences):
                raise SandboxTokenVerificationError("signature audience does not match")
        if claims["sub"] != _CALLBACK_SUBJECT:
            raise SandboxTokenVerificationError("signature is not a callback signature")
        raw = body.encode() if isinstance(body, str) else body
        digest = hashlib.sha256(raw).hexdigest()
        expected = claims["body_sha256"]
        if not isinstance(expected, str) or not hmac.compare_digest(expected, digest):
            raise SandboxTokenVerificationError("body does not match signature")
        return _parse_callback(raw)

    def _cached_key(self, kid: str, now: float) -> tuple[Any, bool]:
        with self._lock:
            keys = self._keys
            fresh = now - self._fetched_at < _JWKS_TTL_SECONDS
            may_refresh = now - self._fetched_at >= _JWKS_MIN_REFRESH_SECONDS
        key = _find_key(keys, kid) if keys is not None else None
        if key is not None and fresh:
            return key, False
        return key, keys is None or not fresh or may_refresh

    def _store(self, data: Any, now: float) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise SandboxTokenVerificationError(
                "invalid JWKS: expected an object with a keys array"
            )
        usable = [k for k in data["keys"] if isinstance(k, dict)]
        try:
            keys = self._jwt.PyJWKSet.from_dict({"keys": usable})
        except (self._jwt.PyJWTError, KeyError, TypeError, ValueError) as e:
            raise SandboxTokenVerificationError(f"invalid JWKS: {e}") from e
        with self._lock:
            self._keys = keys
            self._fetched_at = now
        return keys

    def _key_sync(self, kid: str) -> Any:
        key, refresh = self._cached_key(kid, time.monotonic())
        if refresh:
            # Serialized and re-checked so concurrent misses share one fetch.
            with self._fetch_lock:
                now = time.monotonic()
                key, refresh = self._cached_key(kid, now)
                if refresh:
                    try:
                        resp = httpx.get(self._jwks_url, timeout=self._timeout)
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPError, ValueError) as e:
                        raise SandboxTokenVerificationError(
                            f"failed to fetch JWKS from {self._jwks_url}: {e}"
                        ) from e
                    key = _find_key(self._store(data, now), kid)
        return _require_key(key, kid)

    def _async_fetch_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._afetch_lock is None or self._afetch_loop is not loop:
                self._afetch_lock = asyncio.Lock()
                self._afetch_loop = loop
            return self._afetch_lock

    async def _key_async(self, kid: str) -> Any:
        key, refresh = self._cached_key(kid, time.monotonic())
        if refresh:
            async with self._async_fetch_lock():
                now = time.monotonic()
                key, refresh = self._cached_key(kid, now)
                if refresh:
                    try:
                        async with httpx.AsyncClient(timeout=self._timeout) as client:
                            resp = await client.get(self._jwks_url)
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPError, ValueError) as e:
                        raise SandboxTokenVerificationError(
                            f"failed to fetch JWKS from {self._jwks_url}: {e}"
                        ) from e
                    key = _find_key(self._store(data, now), kid)
        return _require_key(key, kid)


def _find_key(keys: Any, kid: str) -> Any:
    for k in keys.keys:
        if k.key_id == kid:
            return k.key
    return None


def _require_key(key: Any, kid: str) -> Any:
    if key is None:
        raise SandboxTokenVerificationError(f"unknown signing key: {kid}")
    return key


def _parse_callback(raw: bytes) -> SandboxCallback:
    try:
        payload = json.loads(raw)
        identity = payload["identity"]
        request = payload.get("request")
        return SandboxCallback(
            host=payload["host"],
            port=int(payload["port"]),
            identity=SandboxCallbackIdentity(
                tenant_id=identity["tenant_id"],
                sandbox_id=identity["sandbox_id"],
                organization_id=identity.get("organization_id"),
                ls_user_id=identity.get("ls_user_id"),
            ),
            request=_parse_full_request(request) if request else None,
        )
    except (ValueError, KeyError, TypeError, binascii.Error) as e:
        raise SandboxTokenVerificationError(f"malformed callback body: {e}") from e


def _parse_full_request(r: Mapping[str, Any]) -> SandboxCallbackRequest:
    return SandboxCallbackRequest(
        method=r["method"],
        url=r["url"],
        scheme=r["scheme"],
        host=r["host"],
        path=r["path"],
        query=r.get("query") or None,
        headers={k: list(v) for k, v in (r.get("headers") or {}).items()},
        body=base64.b64decode(r.get("body_base64") or "", validate=True),
        body_truncated=bool(r.get("body_truncated")),
    )
