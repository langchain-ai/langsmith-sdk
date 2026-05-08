import base64
import hashlib
import json
import time
from typing import Any, Mapping, Optional

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from langsmith import utils as ls_utils
from langsmith.sandbox import (
    SANDBOX_CALLBACK_SIGNATURE_HEADER,
    SANDBOX_CALLBACK_SUBJECT,
    SandboxCallbackClaims,
    SandboxCallbackVerificationError,
    SandboxCallbackVerifier,
)


def _callback_body(
    *,
    tenant_id: str = "tenant-1",
    organization_id: str = "org-1",
    sandbox_id: str = "sandbox-1",
    ls_user_id: Optional[str] = "user-1",
    host: str = "example.com",
    port: int = 80,
) -> bytes:
    identity = {
        "tenant_id": tenant_id,
        "organization_id": organization_id,
        "sandbox_id": sandbox_id,
    }
    if ls_user_id is not None:
        identity["ls_user_id"] = ls_user_id
    return json.dumps(
        {"host": host, "port": port, "identity": identity},
        separators=(",", ":"),
    ).encode()


def test_verifier_uses_sdk_defaults_and_caches_tenant_and_jwks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://smith.example/api")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    ls_utils.get_env_var.cache_clear()
    body = _callback_body()
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
    )
    calls = _install_fake_langsmith_get(
        monkeypatch,
        key,
        tenant_id="tenant-1",
        api_url="https://smith.example/api",
    )
    verifier = SandboxCallbackVerifier()

    for _ in range(2):
        claims = verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER.lower(): token},
            body,
            expected_sandbox_id="sandbox-1",
        )
        assert isinstance(claims, SandboxCallbackClaims)
        assert claims.issuer == "https://smith.example"
        assert claims.audience == "https://customer.example/callback"
        assert claims.subject == SANDBOX_CALLBACK_SUBJECT
        assert claims.tenant_id == "tenant-1"
        assert claims.organization_id == "org-1"
        assert claims.sandbox_id == "sandbox-1"
        assert claims.ls_user_id == "user-1"
        assert claims.identity.ls_user_id == "user-1"
        assert claims.body_sha256 == hashlib.sha256(body).hexdigest()

    assert [call["url"] for call in calls] == [
        "https://smith.example/.well-known/jwks.json",
        "https://smith.example/api/sessions",
    ]
    assert calls[1]["headers"]["X-Api-Key"] == "test-key"


def test_verifier_refreshes_jwks_once_for_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _callback_body()
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="new-kid",
        body=body,
        issuer_url="https://smith.example",
    )
    stale_key = Ed25519PrivateKey.generate()
    calls = _install_fake_langsmith_get(
        monkeypatch,
        stale_key,
        tenant_id="tenant-1",
        api_url="https://smith.example",
        jwks_sequence=[
            _jwks(stale_key, kid="old-kid"),
            _jwks(key, kid="new-kid"),
        ],
    )
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    claims = verifier.verify(
        {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
        body,
        expected_sandbox_id="sandbox-1",
    )

    assert claims.sandbox_id == "sandbox-1"
    assert [call["url"] for call in calls] == [
        "https://smith.example/.well-known/jwks.json",
        "https://smith.example/.well-known/jwks.json",
    ]


def test_verifier_accepts_raw_asgi_headers_and_default_clock_leeway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _callback_body()
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
        extra_claims={"exp": int(time.time()) - 30},
    )
    _install_fake_langsmith_get(monkeypatch, key, tenant_id="tenant-1")
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    claims = verifier.verify(
        [(SANDBOX_CALLBACK_SIGNATURE_HEADER.lower().encode(), token.encode())],
        body,
        expected_sandbox_id="sandbox-1",
    )

    assert claims.sandbox_id == "sandbox-1"


@pytest.mark.parametrize(
    ("mutate_claims", "message"),
    [
        ({"iss": "https://other.example"}, "issuer"),
        ({"sub": "other-subject"}, "subject"),
        ({"aud": ""}, "aud"),
        ({"exp": 1}, "expired"),
        ({"nbf": time.time() + 3600}, "not yet valid"),
    ],
)
def test_verifier_rejects_bad_claims(
    monkeypatch: pytest.MonkeyPatch,
    mutate_claims: Mapping[str, Any],
    message: str,
) -> None:
    body = _callback_body()
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
        extra_claims=mutate_claims,
    )
    _install_fake_langsmith_get(monkeypatch, key, tenant_id="tenant-1")
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
        expected_organization_id="org-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match=message):
        verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
            body,
            expected_sandbox_id="sandbox-1",
        )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (_callback_body(tenant_id="other-tenant"), "tenant_id"),
        (_callback_body(organization_id="other-org"), "organization_id"),
        (_callback_body(sandbox_id="other-sandbox"), "sandbox_id"),
        (b'{"host":"example.com","port":80}', "identity"),
    ],
)
def test_verifier_rejects_bad_body_identity(
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    message: str,
) -> None:
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
    )
    _install_fake_langsmith_get(monkeypatch, key, tenant_id="tenant-1")
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
        expected_organization_id="org-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match=message):
        verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
            body,
            expected_sandbox_id="sandbox-1",
        )


def test_verifier_rejects_body_hash_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    signed_body = _callback_body(port=80)
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=signed_body,
        issuer_url="https://smith.example",
    )
    _install_fake_langsmith_get(monkeypatch, key, tenant_id="tenant-1")
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match="body hash"):
        verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
            _callback_body(port=443),
            expected_sandbox_id="sandbox-1",
        )


def test_verifier_rejects_wrong_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _callback_body()
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
    )
    _install_fake_langsmith_get(
        monkeypatch,
        Ed25519PrivateKey.generate(),
        tenant_id="tenant-1",
        jwks_kid="callback-kid",
    )
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match="signature"):
        verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
            body,
            expected_sandbox_id="sandbox-1",
        )


def test_verifier_requires_signature_header() -> None:
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match="Missing"):
        verifier.verify({}, b"{}", expected_sandbox_id="sandbox-1")


def test_verifier_requires_sandbox_id_unless_unsafe() -> None:
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    with pytest.raises(SandboxCallbackVerificationError, match="expected_sandbox_id"):
        verifier.verify({SANDBOX_CALLBACK_SIGNATURE_HEADER: "token"}, b"{}")
    with pytest.raises(SandboxCallbackVerificationError, match="not both"):
        verifier.verify(
            {SANDBOX_CALLBACK_SIGNATURE_HEADER: "token"},
            b"{}",
            expected_sandbox_id="sandbox-1",
            unsafely_allow_any_sandbox_id=True,
        )


def test_verifier_can_unsafely_allow_any_sandbox_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _callback_body(sandbox_id="sandbox-from-body")
    key = Ed25519PrivateKey.generate()
    token = _sign_callback_jwt(
        key,
        kid="callback-kid",
        body=body,
        issuer_url="https://smith.example",
    )
    _install_fake_langsmith_get(monkeypatch, key, tenant_id="tenant-1")
    verifier = SandboxCallbackVerifier(
        api_url="https://smith.example",
        expected_tenant_id="tenant-1",
    )

    claims = verifier.verify(
        {SANDBOX_CALLBACK_SIGNATURE_HEADER: token},
        body,
        unsafely_allow_any_sandbox_id=True,
    )

    assert claims.sandbox_id == "sandbox-from-body"


def _install_fake_langsmith_get(
    monkeypatch: pytest.MonkeyPatch,
    key: Ed25519PrivateKey,
    *,
    tenant_id: str,
    api_url: str = "https://smith.example",
    jwks_kid: str = "callback-kid",
    jwks_sequence: Optional[list[dict[str, list[dict[str, str]]]]] = None,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    jwks_responses = list(jwks_sequence or [_jwks(key, kid=jwks_kid)])

    def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        calls.append({"url": url, **kwargs})
        request = httpx.Request("GET", url)
        if url == "https://smith.example/.well-known/jwks.json":
            jwks = jwks_responses.pop(0) if jwks_responses else _jwks(key, kid=jwks_kid)
            return httpx.Response(200, json=jwks, request=request)
        if url == api_url.rstrip("/") + "/sessions":
            return httpx.Response(200, json=[{"tenant_id": tenant_id}], request=request)
        return httpx.Response(404, json={"error": "not found"}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


def _sign_callback_jwt(
    key: Ed25519PrivateKey,
    *,
    kid: str,
    body: bytes,
    issuer_url: str,
    audience: str = "https://customer.example/callback",
    extra_claims: Optional[Mapping[str, Any]] = None,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": issuer_url.rstrip("/"),
        "sub": SANDBOX_CALLBACK_SUBJECT,
        "aud": audience,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": "jti-1",
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }
    if extra_claims:
        claims.update(extra_claims)
    header = {"alg": "EdDSA", "typ": "JWT", "kid": kid}
    signing_input = b".".join(
        [
            _b64url_json(header),
            _b64url_json(claims),
        ]
    )
    return signing_input.decode() + "." + _b64url(key.sign(signing_input)).decode()


def _jwks(key: Ed25519PrivateKey, *, kid: str) -> dict[str, list[dict[str, str]]]:
    public_bytes = key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    return {
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "kid": kid,
                "use": "sig",
                "alg": "EdDSA",
                "x": _b64url(public_bytes).decode(),
            }
        ]
    }


def _b64url_json(value: Mapping[str, Any]) -> bytes:
    return _b64url(json.dumps(value, separators=(",", ":")).encode())


def _b64url(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")
