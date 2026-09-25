"""Tests for sandbox user-token and proxy-callback verification."""

import asyncio
import base64
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.algorithms import OKPAlgorithm
from pytest_httpx import HTTPXMock

from langsmith import utils as ls_utils
from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox import (
    SandboxTokenVerificationError,
    SandboxTokenVerifier,
)

API_URL = "https://api.example.com/api/v1"
JWKS_URL = "https://api.example.com/.well-known/jwks.json"
APP_URL = "https://app.example.com"
SERVICE_HOST = "0190aaaa-0000-7000-8000-000000000001--8080.svc.example.com"
CALLBACK_URL = "https://integrator.example.com/sandbox-callback"
KID = "test-kid"


@pytest.fixture(autouse=True)
def _fresh_env_cache():
    ls_utils.get_env_var.cache_clear()
    yield
    ls_utils.get_env_var.cache_clear()


def _jwk(key: Ed25519PrivateKey, kid: str) -> dict:
    public = json.loads(OKPAlgorithm.to_jwk(key.public_key()))
    return {
        **public,
        "kid": kid,
        "alg": "EdDSA",
        "use": "sig",
        "key_ops": ["verify"],
        "ext": True,
    }


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def jwks(httpx_mock: HTTPXMock, key):
    httpx_mock.add_response(
        url=JWKS_URL, json={"keys": [_jwk(key, KID)]}, is_reusable=True
    )


def _sign(key, claims: dict, kid: str = KID, headers: dict | None = None) -> str:
    return jwt.encode(
        claims, key, algorithm="EdDSA", headers={"kid": kid, **(headers or {})}
    )


def _user_claims(**overrides) -> dict:
    now = int(time.time())
    return {
        "iss": APP_URL,
        "sub": "user-123",
        "aud": [SERVICE_HOST],
        "exp": now + 600,
        "iat": now,
        "email": "ada@example.com",
        "name": "Ada",
        **overrides,
    }


def _callback_body(**overrides) -> bytes:
    payload = {
        "host": "api.github.com",
        "port": 443,
        "identity": {
            "tenant_id": str(uuid.uuid4()),
            "sandbox_id": str(uuid.uuid4()),
            "organization_id": str(uuid.uuid4()),
            "ls_user_id": str(uuid.uuid4()),
        },
        **overrides,
    }
    return json.dumps(payload).encode()


def _callback_claims(body: bytes, **overrides) -> dict:
    now = int(time.time())
    return {
        "iss": APP_URL,
        "sub": "langsmith-sandbox-callback",
        "aud": [CALLBACK_URL],
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        **overrides,
    }


@pytest.fixture
def verifier():
    return SandboxTokenVerifier(api_url=API_URL)


class TestUserToken:
    def test_valid(self, jwks, key, verifier):
        user = verifier.verify_user_token(
            _sign(key, _user_claims()), audience=SERVICE_HOST, issuer=APP_URL
        )
        assert user.subject == "user-123"
        assert user.email == "ada@example.com"
        assert user.name == "Ada"

    def test_accepts_service_url_as_audience(self, jwks, key, verifier):
        user = verifier.verify_user_token(
            _sign(key, _user_claims()), audience=f"https://{SERVICE_HOST}/path"
        )
        assert user.subject == "user-123"

    @pytest.mark.parametrize(
        ("claims", "kwargs"),
        [
            pytest.param(
                {"aud": ["other--8080.svc.example.com"]}, {}, id="wrong audience"
            ),
            pytest.param({"exp": int(time.time()) - 120}, {}, id="expired"),
            pytest.param({}, {"issuer": "https://evil.example.com"}, id="bad issuer"),
            pytest.param({"sub": ""}, {}, id="empty subject"),
        ],
    )
    def test_rejects(self, jwks, key, verifier, claims, kwargs):
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_user_token(
                _sign(key, _user_claims(**claims)), audience=SERVICE_HOST, **kwargs
            )

    def test_rejects_missing_subject(self, jwks, key, verifier):
        claims = _user_claims()
        del claims["sub"]
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_user_token(_sign(key, claims), audience=SERVICE_HOST)

    def test_rejects_other_key(self, jwks, verifier):
        token = _sign(Ed25519PrivateKey.generate(), _user_claims())
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_user_token(token, audience=SERVICE_HOST)

    def test_rejects_hs256(self, verifier):
        token = jwt.encode(
            _user_claims(), "secret" * 6, algorithm="HS256", headers={"kid": KID}
        )
        with pytest.raises(SandboxTokenVerificationError, match="algorithm"):
            verifier.verify_user_token(token, audience=SERVICE_HOST)

    def test_rejects_callback_signature(self, jwks, key, verifier):
        body = _callback_body()
        token = _sign(key, _callback_claims(body, aud=[SERVICE_HOST]))
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_user_token(token, audience=SERVICE_HOST, issuer=APP_URL)

    def test_caches_jwks(self, httpx_mock: HTTPXMock, jwks, key, verifier):
        for _ in range(3):
            verifier.verify_user_token(
                _sign(key, _user_claims()), audience=SERVICE_HOST
            )
        assert len(httpx_mock.get_requests()) == 1

    def test_refetches_on_rotated_key(self, httpx_mock: HTTPXMock, key, verifier):
        rotated = Ed25519PrivateKey.generate()
        httpx_mock.add_response(url=JWKS_URL, json={"keys": [_jwk(key, KID)]})
        httpx_mock.add_response(
            url=JWKS_URL, json={"keys": [_jwk(key, KID), _jwk(rotated, "new")]}
        )
        verifier.verify_user_token(_sign(key, _user_claims()), audience=SERVICE_HOST)
        verifier._fetched_at -= 60
        user = verifier.verify_user_token(
            _sign(rotated, _user_claims(), kid="new"), audience=SERVICE_HOST
        )
        assert user.subject == "user-123"

    async def test_async(self, jwks, key, verifier):
        user = await verifier.averify_user_token(
            _sign(key, _user_claims()), audience=SERVICE_HOST
        )
        assert user.subject == "user-123"


class TestJWKSFetch:
    def test_concurrent_misses_share_one_fetch(
        self, httpx_mock: HTTPXMock, key, verifier
    ):
        def slow_jwks(request):
            time.sleep(0.2)
            return httpx.Response(200, json={"keys": [_jwk(key, KID)]})

        httpx_mock.add_callback(slow_jwks, url=JWKS_URL, is_reusable=True)
        token = _sign(key, _user_claims())
        with ThreadPoolExecutor(8) as pool:
            users = list(
                pool.map(
                    lambda _: verifier.verify_user_token(token, audience=SERVICE_HOST),
                    range(8),
                )
            )
        assert {u.subject for u in users} == {"user-123"}
        assert len(httpx_mock.get_requests()) == 1

    async def test_concurrent_async_misses_share_one_fetch(
        self, httpx_mock: HTTPXMock, key, verifier
    ):
        async def slow_jwks(request):
            await asyncio.sleep(0.2)
            return httpx.Response(200, json={"keys": [_jwk(key, KID)]})

        httpx_mock.add_callback(slow_jwks, url=JWKS_URL, is_reusable=True)
        token = _sign(key, _user_claims(), kid="unknown")
        results = await asyncio.gather(
            *(
                verifier.averify_user_token(token, audience=SERVICE_HOST)
                for _ in range(8)
            ),
            return_exceptions=True,
        )
        assert all(isinstance(r, SandboxTokenVerificationError) for r in results)
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.parametrize(
        "body", [None, {"keys": {}}, {"keys": [None, 1]}, [], "keys"]
    )
    def test_malformed_jwks(self, httpx_mock: HTTPXMock, key, verifier, body):
        httpx_mock.add_response(url=JWKS_URL, json=body)
        with pytest.raises(SandboxTokenVerificationError, match="JWKS"):
            verifier.verify_user_token(
                _sign(key, _user_claims()), audience=SERVICE_HOST
            )


class TestCallback:
    def test_valid(self, jwks, key, verifier):
        body = _callback_body()
        cb = verifier.verify_callback(
            body=body,
            signature=_sign(key, _callback_claims(body)),
            aud=CALLBACK_URL,
            issuer=APP_URL,
        )
        assert cb.host == "api.github.com"
        assert cb.port == 443
        assert cb.identity.sandbox_id == json.loads(body)["identity"]["sandbox_id"]
        assert cb.request is None

    def test_full_request(self, jwks, key, verifier):
        body = _callback_body(
            request={
                "method": "POST",
                "url": "https://api.github.com/repos?x=1",
                "scheme": "https",
                "host": "api.github.com",
                "path": "/repos",
                "query": "x=1",
                "headers": {"Accept": ["application/json"]},
                "body_base64": base64.b64encode(b"hello").decode(),
                "body_truncated": False,
            }
        )
        cb = verifier.verify_callback(
            body=body, signature=_sign(key, _callback_claims(body)), aud=CALLBACK_URL
        )
        assert cb.request is not None
        assert cb.request.body == b"hello"
        assert cb.request.headers == {"Accept": ["application/json"]}

    def test_rejects_tampered_body(self, jwks, key, verifier):
        body = _callback_body()
        signature = _sign(key, _callback_claims(body))
        with pytest.raises(SandboxTokenVerificationError, match="body"):
            verifier.verify_callback(
                body=_callback_body(host="evil.example.com"),
                signature=signature,
                aud=CALLBACK_URL,
            )

    @pytest.mark.parametrize(
        "claims",
        [
            pytest.param({"aud": ["https://other.example.com/cb"]}, id="wrong aud"),
            pytest.param({"sub": "user-123"}, id="wrong subject"),
            pytest.param({"exp": int(time.time()) - 120}, id="expired"),
        ],
    )
    def test_rejects(self, jwks, key, verifier, claims):
        body = _callback_body()
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_callback(
                body=body,
                signature=_sign(key, _callback_claims(body, **claims)),
                aud=CALLBACK_URL,
            )

    def test_rejects_missing_body_hash(self, jwks, key, verifier):
        body = _callback_body()
        claims = _callback_claims(body)
        del claims["body_sha256"]
        with pytest.raises(SandboxTokenVerificationError):
            verifier.verify_callback(
                body=body, signature=_sign(key, claims), aud=CALLBACK_URL
            )

    def test_aud_predicate(self, jwks, key, verifier):
        body = _callback_body()
        signature = _sign(key, _callback_claims(body))
        cb = verifier.verify_callback(
            body=body,
            signature=signature,
            aud=lambda a: a.startswith("https://integrator.example.com/"),
        )
        assert cb.port == 443
        with pytest.raises(SandboxTokenVerificationError, match="audience"):
            verifier.verify_callback(
                body=body, signature=signature, aud=lambda a: a == "https://x/cb"
            )

    def test_aud_optional(self, jwks, key, verifier):
        body = _callback_body()
        claims = _callback_claims(body, aud=["https://other.example.com/cb"])
        cb = verifier.verify_callback(body=body, signature=_sign(key, claims))
        assert cb.port == 443

    async def test_async(self, jwks, key, verifier):
        body = _callback_body()
        cb = await verifier.averify_callback(
            body=body, signature=_sign(key, _callback_claims(body)), aud=CALLBACK_URL
        )
        assert cb.port == 443


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:1984/.well-known/jwks.json",
        "http://127.0.0.1:1984/.well-known/jwks.json",
        "http://[::1]:1984/.well-known/jwks.json",
    ],
)
def test_allows_http_loopback_jwks(url):
    SandboxTokenVerifier(jwks_url=url)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"jwks_url": "http://langsmith.internal/.well-known/jwks.json"},
        {"api_url": "http://langsmith.internal/api/v1"},
        {"jwks_url": "ftp://langsmith.internal/jwks.json"},
    ],
)
def test_rejects_insecure_jwks(kwargs):
    with pytest.raises(ValueError, match="https"):
        SandboxTokenVerifier(**kwargs)


def test_rejects_insecure_default_endpoint(monkeypatch):
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "http://langsmith.internal/api/v1")
    with pytest.raises(ValueError, match="https"):
        SandboxTokenVerifier()


def test_allow_insecure_jwks_opt_out():
    SandboxTokenVerifier(
        jwks_url="http://langsmith.internal/.well-known/jwks.json",
        allow_insecure_jwks=True,
    )


def test_default_jwks_url_uses_endpoint_origin(httpx_mock: HTTPXMock, key, monkeypatch):
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.example.com/api/v1")
    httpx_mock.add_response(url=JWKS_URL, json={"keys": [_jwk(key, KID)]})
    user = SandboxTokenVerifier().verify_user_token(
        _sign(key, _user_claims()), audience=SERVICE_HOST
    )
    assert user.subject == "user-123"
