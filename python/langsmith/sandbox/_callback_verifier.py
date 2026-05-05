"""Verify signed LangSmith sandbox callback requests."""

from __future__ import annotations

import base64
import binascii
import dataclasses
import hashlib
import json
import threading
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional, Union
from urllib.parse import urlparse

import httpx

from langsmith import utils as ls_utils

SANDBOX_CALLBACK_SIGNATURE_HEADER = "X-LangSmith-Signature-JWT"
SANDBOX_CALLBACK_SUBJECT = "langsmith-sandbox-callback"

_JWKS_PATH = "/.well-known/jwks.json"
_HeaderValue = Union[str, bytes]
_Headers = Union[
    Mapping[str, _HeaderValue], Sequence[tuple[_HeaderValue, _HeaderValue]]
]


class SandboxCallbackVerificationError(ValueError):
    """Raised when a sandbox callback signature cannot be verified."""


@dataclasses.dataclass(frozen=True)
class SandboxCallbackIdentity:
    """Verified LangSmith sandbox callback body identity."""

    tenant_id: str
    organization_id: str
    sandbox_id: str
    ls_user_id: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SandboxCallbackClaims:
    """Verified LangSmith sandbox callback JWT claims and body identity."""

    issuer: str
    audience: Union[str, tuple[str, ...]]
    subject: str
    identity: SandboxCallbackIdentity
    body_sha256: str
    jti: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime

    @property
    def tenant_id(self) -> str:
        return self.identity.tenant_id

    @property
    def organization_id(self) -> str:
        return self.identity.organization_id

    @property
    def sandbox_id(self) -> str:
        return self.identity.sandbox_id

    @property
    def ls_user_id(self) -> Optional[str]:
        return self.identity.ls_user_id


class SandboxCallbackVerifier:
    """Verifier for LangSmith sandbox callback requests."""

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        workspace_id: Optional[str] = None,
        expected_tenant_id: Optional[str] = None,
        expected_organization_id: Optional[str] = None,
        leeway_seconds: float = 60,
        jwks_cache_ttl_seconds: float = 300,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the verifier using normal LangSmith SDK endpoint defaults."""
        self.api_url = ls_utils.get_api_url(api_url)
        self.api_key = ls_utils.get_api_key(api_key)
        self.workspace_id = ls_utils.get_workspace_id(workspace_id)
        self.issuer_url = _origin_url(self.api_url)
        self.expected_organization_id = _clean_optional(expected_organization_id)
        self.leeway_seconds = leeway_seconds
        self.jwks_cache_ttl_seconds = jwks_cache_ttl_seconds
        self.timeout = timeout

        self._expected_tenant_id = _clean_optional(expected_tenant_id)
        self._jwks: Optional[Mapping[str, Any]] = None
        self._jwks_expires_at = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_client(
        cls,
        client: Any,
        *,
        expected_tenant_id: Optional[str] = None,
        expected_organization_id: Optional[str] = None,
        leeway_seconds: float = 60,
        jwks_cache_ttl_seconds: float = 300,
        timeout: float = 5.0,
    ) -> SandboxCallbackVerifier:
        """Create a verifier from an existing LangSmith client."""
        return cls(
            api_url=getattr(client, "api_url", None),
            api_key=getattr(client, "api_key", None),
            workspace_id=getattr(client, "workspace_id", None),
            expected_tenant_id=expected_tenant_id,
            expected_organization_id=expected_organization_id,
            leeway_seconds=leeway_seconds,
            jwks_cache_ttl_seconds=jwks_cache_ttl_seconds,
            timeout=timeout,
        )

    def verify(
        self,
        headers: _Headers,
        body: Union[bytes, bytearray, memoryview, str],
        *,
        expected_sandbox_id: Optional[str] = None,
        unsafely_allow_any_sandbox_id: bool = False,
    ) -> SandboxCallbackClaims:
        """Verify a sandbox callback request.

        Args:
            headers: Incoming callback request headers.
            body: Exact raw callback request body bytes.
            expected_sandbox_id: Sandbox ID the callback is expected to be for.
            unsafely_allow_any_sandbox_id: Skip sandbox ID matching. This is only
                safe if the caller verifies ``claims.identity.sandbox_id`` before
                trusting the callback.
        """
        expected_sandbox_id = _clean_optional(expected_sandbox_id)
        if expected_sandbox_id and unsafely_allow_any_sandbox_id:
            raise SandboxCallbackVerificationError(
                "Pass expected_sandbox_id or unsafely_allow_any_sandbox_id=True, "
                "not both"
            )
        if not expected_sandbox_id and not unsafely_allow_any_sandbox_id:
            raise SandboxCallbackVerificationError(
                "expected_sandbox_id is required unless "
                "unsafely_allow_any_sandbox_id=True"
            )

        signature_jwt = _get_header(headers, SANDBOX_CALLBACK_SIGNATURE_HEADER)
        if not signature_jwt:
            raise SandboxCallbackVerificationError(
                f"Missing {SANDBOX_CALLBACK_SIGNATURE_HEADER} header"
            )

        header, claims, signing_input, signature = _decode_jwt(signature_jwt)
        if header.get("alg") != "EdDSA":
            raise SandboxCallbackVerificationError(
                "Sandbox callback JWT must use EdDSA"
            )
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise SandboxCallbackVerificationError(
                "Sandbox callback JWT is missing kid"
            )

        key = self._find_key(kid)
        _verify_eddsa_signature(key, signing_input, signature)

        body_bytes = _body_bytes(body)
        expected_body_hash = hashlib.sha256(body_bytes).hexdigest()
        body_sha256 = claims.get("body_sha256")
        if body_sha256 != expected_body_hash:
            raise SandboxCallbackVerificationError(
                "Sandbox callback body hash mismatch"
            )

        identity = _identity_from_body(body_bytes)
        expected_tenant_id = self._get_expected_tenant_id()
        _validate_claims(
            claims,
            issuer_url=self.issuer_url,
            leeway_seconds=self.leeway_seconds,
        )
        _validate_identity(
            identity,
            expected_tenant_id=expected_tenant_id,
            expected_organization_id=self.expected_organization_id,
            expected_sandbox_id=expected_sandbox_id,
        )

        return _claims_to_result(claims, identity)

    def _find_key(self, kid: str) -> Mapping[str, Any]:
        try:
            return _find_jwk(self._get_jwks(), kid)
        except SandboxCallbackVerificationError:
            return _find_jwk(self._get_jwks(force=True), kid)

    def _get_jwks(self, *, force: bool = False) -> Mapping[str, Any]:
        now = time.time()
        with self._lock:
            if not force and self._jwks is not None and self._jwks_expires_at > now:
                return self._jwks
            url = self.issuer_url + _JWKS_PATH
            try:
                response = httpx.get(url, timeout=self.timeout, follow_redirects=False)
                response.raise_for_status()
                jwks = response.json()
            except Exception as exc:
                msg = f"Failed to fetch LangSmith sandbox callback JWKS from {url!r}"
                raise SandboxCallbackVerificationError(msg) from exc
            if not isinstance(jwks, Mapping):
                raise SandboxCallbackVerificationError(
                    "JWKS response must be a JSON object"
                )
            self._jwks = jwks
            self._jwks_expires_at = time.time() + self.jwks_cache_ttl_seconds
            return jwks

    def _get_expected_tenant_id(self) -> str:
        with self._lock:
            if self._expected_tenant_id:
                return self._expected_tenant_id
            url = self.api_url.rstrip("/") + "/sessions"
            try:
                response = httpx.get(
                    url,
                    params={"limit": 1},
                    headers=self._auth_headers(),
                    timeout=self.timeout,
                    follow_redirects=False,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise SandboxCallbackVerificationError(
                    "Failed to fetch LangSmith tenant ID"
                ) from exc
            if not isinstance(data, list) or not data:
                raise SandboxCallbackVerificationError("No LangSmith tenant ID found")
            tenant_id = (
                data[0].get("tenant_id") if isinstance(data[0], Mapping) else None
            )
            if not isinstance(tenant_id, str) or not tenant_id:
                raise SandboxCallbackVerificationError("No LangSmith tenant ID found")
            self._expected_tenant_id = tenant_id
            return tenant_id

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        if self.workspace_id:
            headers["X-Tenant-Id"] = self.workspace_id
        return headers


def _decode_jwt(
    token: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise SandboxCallbackVerificationError("Sandbox callback JWT is malformed")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SandboxCallbackVerificationError(
            "Sandbox callback JWT is malformed"
        ) from exc
    if not isinstance(header, Mapping) or not isinstance(claims, Mapping):
        raise SandboxCallbackVerificationError("Sandbox callback JWT is malformed")
    return header, claims, f"{parts[0]}.{parts[1]}".encode(), signature


def _find_jwk(jwks: Mapping[str, Any], kid: str) -> Mapping[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
        raise SandboxCallbackVerificationError("JWKS must contain a keys array")
    for key in keys:
        if isinstance(key, Mapping) and key.get("kid") == kid:
            return key
    raise SandboxCallbackVerificationError("No matching JWK for sandbox callback JWT")


def _verify_eddsa_signature(
    jwk: Mapping[str, Any],
    signing_input: bytes,
    signature: bytes,
) -> None:
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise SandboxCallbackVerificationError("Sandbox callback JWK must be Ed25519")
    x = jwk.get("x")
    if not isinstance(x, str) or not x:
        raise SandboxCallbackVerificationError("Sandbox callback JWK is missing x")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise SandboxCallbackVerificationError(
            "Install cryptography to verify sandbox callback signatures"
        ) from exc
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(x))
        public_key.verify(signature, signing_input)
    except InvalidSignature as exc:
        raise SandboxCallbackVerificationError(
            "Sandbox callback JWT signature is invalid"
        ) from exc
    except Exception as exc:
        raise SandboxCallbackVerificationError(
            "Sandbox callback JWK is invalid"
        ) from exc


def _validate_claims(
    claims: Mapping[str, Any],
    *,
    issuer_url: str,
    leeway_seconds: float,
) -> None:
    now = time.time()
    if claims.get("iss") != issuer_url:
        raise SandboxCallbackVerificationError("Sandbox callback issuer mismatch")
    if claims.get("sub") != SANDBOX_CALLBACK_SUBJECT:
        raise SandboxCallbackVerificationError("Sandbox callback subject mismatch")
    if not _non_empty_audience(claims.get("aud")):
        raise SandboxCallbackVerificationError("Sandbox callback JWT is missing aud")
    exp = _numeric_claim(claims, "exp")
    nbf = _numeric_claim(claims, "nbf")
    _numeric_claim(claims, "iat")
    if exp + leeway_seconds < now:
        raise SandboxCallbackVerificationError("Sandbox callback JWT is expired")
    if nbf - leeway_seconds > now:
        raise SandboxCallbackVerificationError("Sandbox callback JWT is not yet valid")
    for name in ("jti", "body_sha256"):
        value = claims.get(name)
        if not isinstance(value, str) or not value:
            raise SandboxCallbackVerificationError(
                f"Sandbox callback JWT is missing {name}"
            )


def _validate_identity(
    identity: SandboxCallbackIdentity,
    *,
    expected_tenant_id: str,
    expected_organization_id: Optional[str],
    expected_sandbox_id: Optional[str],
) -> None:
    if identity.tenant_id != expected_tenant_id:
        raise SandboxCallbackVerificationError("Sandbox callback tenant_id mismatch")
    if (
        expected_organization_id is not None
        and identity.organization_id != expected_organization_id
    ):
        raise SandboxCallbackVerificationError(
            "Sandbox callback organization_id mismatch"
        )
    if expected_sandbox_id is not None and identity.sandbox_id != expected_sandbox_id:
        raise SandboxCallbackVerificationError("Sandbox callback sandbox_id mismatch")


def _claims_to_result(
    claims: Mapping[str, Any],
    identity: SandboxCallbackIdentity,
) -> SandboxCallbackClaims:
    return SandboxCallbackClaims(
        issuer=str(claims["iss"]),
        audience=_audience_result(claims["aud"]),
        subject=str(claims["sub"]),
        identity=identity,
        body_sha256=str(claims["body_sha256"]),
        jti=str(claims["jti"]),
        issued_at=_datetime_from_timestamp(_numeric_claim(claims, "iat")),
        not_before=_datetime_from_timestamp(_numeric_claim(claims, "nbf")),
        expires_at=_datetime_from_timestamp(_numeric_claim(claims, "exp")),
    )


def _identity_from_body(body: bytes) -> SandboxCallbackIdentity:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SandboxCallbackVerificationError(
            "Sandbox callback body is malformed"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SandboxCallbackVerificationError("Sandbox callback body is malformed")
    identity = payload.get("identity")
    if not isinstance(identity, Mapping):
        raise SandboxCallbackVerificationError(
            "Sandbox callback body is missing identity"
        )
    values: dict[str, str] = {}
    for name in ("tenant_id", "organization_id", "sandbox_id"):
        value = identity.get(name)
        if not isinstance(value, str) or not value:
            raise SandboxCallbackVerificationError(
                f"Sandbox callback body identity is missing {name}"
            )
        values[name] = value
    raw_ls_user_id = identity.get("ls_user_id")
    if raw_ls_user_id is not None and (
        not isinstance(raw_ls_user_id, str) or not raw_ls_user_id
    ):
        raise SandboxCallbackVerificationError(
            "Sandbox callback body identity has invalid ls_user_id"
        )
    ls_user_id = raw_ls_user_id if isinstance(raw_ls_user_id, str) else None
    return SandboxCallbackIdentity(
        tenant_id=values["tenant_id"],
        organization_id=values["organization_id"],
        sandbox_id=values["sandbox_id"],
        ls_user_id=ls_user_id,
    )


def _non_empty_audience(audience: Any) -> bool:
    if isinstance(audience, str):
        return bool(audience)
    if isinstance(audience, Sequence) and not isinstance(audience, (bytes, bytearray)):
        return any(isinstance(item, str) and item for item in audience)
    return False


def _audience_result(audience: Any) -> Union[str, tuple[str, ...]]:
    if isinstance(audience, str):
        return audience
    return tuple(item for item in audience if isinstance(item, str))


def _numeric_claim(claims: Mapping[str, Any], name: str) -> float:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SandboxCallbackVerificationError(
            f"Sandbox callback JWT is missing numeric {name}"
        )
    return float(value)


def _datetime_from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _get_header(headers: _Headers, name: str) -> Optional[str]:
    needle = name.lower()
    items = headers.items() if isinstance(headers, Mapping) else headers
    for key, value in items:
        key_str = key.decode() if isinstance(key, bytes) else key
        if key_str.lower() == needle:
            return value.decode() if isinstance(value, bytes) else value
    return None


def _body_bytes(body: Union[bytes, bytearray, memoryview, str]) -> bytes:
    if isinstance(body, str):
        return body.encode()
    return bytes(body)


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _origin_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise SandboxCallbackVerificationError("LangSmith API URL must be absolute")
    return f"{parsed.scheme}://{parsed.netloc}"


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip().strip('"').strip("'")
    return value or None
