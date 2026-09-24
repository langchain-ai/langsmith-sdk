import { getLangSmithEnvironmentVariable } from "../utils/env.js";
import { LangSmithSandboxTokenVerificationError } from "./errors.js";

/** Header carrying the signed identity of a LangSmith-login service URL request. */
export const USER_TOKEN_HEADER = "X-Langsmith-User-Token";

/** Header carrying the signature of a proxy callback request. */
export const CALLBACK_SIGNATURE_HEADER = "X-LangSmith-Signature-JWT";

const CALLBACK_SUBJECT = "langsmith-sandbox-callback";
const JWKS_PATH = "/.well-known/jwks.json";
const JWKS_TTL_MS = 300_000;
// Bounds refetches when a token names a kid the cached set lacks.
const JWKS_MIN_REFRESH_MS = 30_000;
const LEEWAY_SECONDS = 30;

/** The LangSmith user a service URL request was made by. */
export interface SandboxUser {
  subject: string;
  email?: string;
  name?: string;
  expiresAt: Date;
}

/** The sandbox whose outbound request triggered a proxy callback. */
export interface SandboxCallbackIdentity {
  tenant_id: string;
  sandbox_id: string;
  organization_id?: string;
  ls_user_id?: string;
}

/** Snapshot of the outbound request, sent for `full_request` callbacks. */
export interface SandboxCallbackRequest {
  method: string;
  url: string;
  scheme: string;
  host: string;
  path: string;
  query?: string;
  headers: Record<string, string[]>;
  body_base64: string;
  body_truncated: boolean;
}

/** A verified proxy callback payload. */
export interface SandboxCallback {
  host: string;
  port: number;
  identity: SandboxCallbackIdentity;
  request?: SandboxCallbackRequest;
}

export interface SandboxTokenVerifierConfig {
  /** LangSmith API URL whose origin serves the JWKS. Defaults to LANGSMITH_ENDPOINT. */
  apiUrl?: string;
  /** Full JWKS URL; overrides `apiUrl`. */
  jwksUrl?: string;
  /** Timeout in milliseconds for fetching the JWKS. */
  timeoutMs?: number;
}

export interface VerifyUserTokenOptions {
  /**
   * The service URL host the request was sent to, such as the request's
   * `Host` header. A full service URL is also accepted.
   */
  audience: string;
  /** If set, the LangSmith app URL the token must be issued by. */
  issuer?: string;
}

export interface VerifyCallbackOptions {
  /** The raw request body, exactly as received. */
  body: string | Uint8Array | ArrayBuffer;
  /** The `X-LangSmith-Signature-JWT` header value. */
  signature: string;
  /** The callback URL exactly as configured in the proxy config. */
  url: string;
  /** If set, the LangSmith OAuth issuer the signature must be issued by. */
  issuer?: string;
}

type Claims = Record<string, unknown>;

interface Jwk {
  kty?: string;
  crv?: string;
  kid?: string;
  x?: string;
}

function fail(message: string): never {
  throw new LangSmithSandboxTokenVerificationError(message);
}

function subtle(): SubtleCrypto {
  const s = globalThis.crypto?.subtle;
  if (!s) fail("Web Crypto is not available in this runtime");
  return s;
}

function base64UrlDecode(value: string): Uint8Array<ArrayBuffer> {
  const b64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function decodeJson(segment: string): Claims {
  const value = JSON.parse(new TextDecoder().decode(base64UrlDecode(segment)));
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("not a JSON object");
  }
  return value as Claims;
}

function jwksUrlFrom(apiUrl: string): string {
  return new URL(JWKS_PATH, new URL(apiUrl).origin).toString();
}

function serviceHost(audience: string): string {
  return audience.includes("://") ? new URL(audience).host : audience;
}

function toBytes(
  body: string | Uint8Array | ArrayBuffer,
): Uint8Array<ArrayBuffer> {
  if (typeof body === "string") return new TextEncoder().encode(body);
  if (body instanceof ArrayBuffer) return new Uint8Array(body);
  return new Uint8Array(body);
}

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/**
 * Verifies tokens LangSmith signs for code running in or behind a sandbox.
 *
 * Keys are fetched from LangSmith's JWKS endpoint and cached. Requires Web
 * Crypto Ed25519 support (Node.js 20+, Deno, Bun, Cloudflare Workers).
 *
 * @example
 * ```typescript
 * const verifier = new SandboxTokenVerifier();
 *
 * // In an app served from a LangSmith-login service URL:
 * const user = await verifier.verifyUserToken(
 *   req.headers.get(USER_TOKEN_HEADER)!,
 *   { audience: req.headers.get("host")! }
 * );
 *
 * // In a proxy callback endpoint:
 * const callback = await verifier.verifyCallback({
 *   body: await req.text(),
 *   signature: req.headers.get(CALLBACK_SIGNATURE_HEADER)!,
 *   url: "https://example.com/sandbox-callback",
 * });
 * ```
 */
export class SandboxTokenVerifier {
  private readonly jwksUrl: string;
  private readonly timeoutMs: number;
  private keys = new Map<string, Promise<CryptoKey>>();
  private fetchedAt = 0;
  private inflight?: Promise<void>;

  constructor(config: SandboxTokenVerifierConfig = {}) {
    this.jwksUrl =
      config.jwksUrl ??
      jwksUrlFrom(
        config.apiUrl ??
          getLangSmithEnvironmentVariable("ENDPOINT") ??
          "https://api.smith.langchain.com",
      );
    this.timeoutMs = config.timeoutMs ?? 10_000;
  }

  /**
   * Verify the `X-Langsmith-User-Token` header of a service URL request.
   *
   * LangSmith sets this header only for service URLs that use LangSmith login.
   * The unsigned `X-Langsmith-User-Id` and `X-Langsmith-User-Email` headers
   * carry the same identity but must not be relied on for access control.
   */
  async verifyUserToken(
    token: string,
    options: VerifyUserTokenOptions,
  ): Promise<SandboxUser> {
    const claims = await this.verify(
      token,
      serviceHost(options.audience),
      options.issuer,
    );
    const sub = claims.sub;
    if (typeof sub !== "string" || !sub || sub === CALLBACK_SUBJECT) {
      fail("token is not a user token");
    }
    return {
      subject: sub,
      email:
        typeof claims.email === "string" && claims.email
          ? claims.email
          : undefined,
      name:
        typeof claims.name === "string" && claims.name
          ? claims.name
          : undefined,
      expiresAt: new Date((claims.exp as number) * 1000),
    };
  }

  /** Verify a proxy callback request and return its parsed payload. */
  async verifyCallback(
    options: VerifyCallbackOptions,
  ): Promise<SandboxCallback> {
    const claims = await this.verify(
      options.signature,
      options.url,
      options.issuer,
    );
    if (claims.sub !== CALLBACK_SUBJECT) {
      fail("signature is not a callback signature");
    }
    const expected = claims.body_sha256;
    if (typeof expected !== "string") fail("signature has no body hash");
    const raw = toBytes(options.body);
    const digest = hex(await subtle().digest("SHA-256", raw));
    if (!timingSafeEqual(expected, digest))
      fail("body does not match signature");

    let payload: SandboxCallback;
    try {
      payload = JSON.parse(new TextDecoder().decode(raw));
    } catch (e) {
      fail(`malformed callback body: ${(e as Error).message}`);
    }
    const id = payload?.identity;
    if (
      typeof payload?.host !== "string" ||
      typeof payload.port !== "number" ||
      typeof id?.tenant_id !== "string" ||
      typeof id.sandbox_id !== "string"
    ) {
      fail("malformed callback body");
    }
    return payload;
  }

  private async verify(
    token: string,
    audience: string,
    issuer: string | undefined,
  ): Promise<Claims> {
    const parts = token ? token.split(".") : [];
    if (parts.length !== 3) fail("malformed token");
    let header: Claims;
    let claims: Claims;
    let signature: Uint8Array<ArrayBuffer>;
    try {
      header = decodeJson(parts[0]);
      claims = decodeJson(parts[1]);
      signature = base64UrlDecode(parts[2]);
    } catch (e) {
      fail(`malformed token: ${(e as Error).message}`);
    }
    if (header.alg !== "EdDSA") {
      fail(`unexpected signing algorithm: ${JSON.stringify(header.alg)}`);
    }
    if (typeof header.kid !== "string" || !header.kid) fail("token has no kid");

    const key = await this.key(header.kid);
    const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
    if (!(await subtle().verify({ name: "Ed25519" }, key, signature, signed))) {
      fail("invalid signature");
    }

    const now = Date.now() / 1000;
    const { exp, iat, nbf, iss, aud } = claims;
    if (typeof exp !== "number") fail("token has no exp");
    if (now > exp + LEEWAY_SECONDS) fail("token is expired");
    if (typeof iat !== "number") fail("token has no iat");
    if (iat > now + LEEWAY_SECONDS) fail("token is not yet valid");
    if (
      nbf !== undefined &&
      (typeof nbf !== "number" || nbf > now + LEEWAY_SECONDS)
    ) {
      fail("token is not yet valid");
    }
    if (typeof iss !== "string") fail("token has no iss");
    if (issuer !== undefined && iss !== issuer.replace(/\/+$/, "")) {
      fail("token has the wrong issuer");
    }
    const audiences =
      typeof aud === "string" ? [aud] : Array.isArray(aud) ? aud : [];
    if (!audiences.includes(audience)) fail("token has the wrong audience");
    return claims;
  }

  private async key(kid: string): Promise<CryptoKey> {
    const age = Date.now() - this.fetchedAt;
    const fresh = this.keys.has(kid) && age < JWKS_TTL_MS;
    if (!fresh && (this.fetchedAt === 0 || age >= JWKS_MIN_REFRESH_MS)) {
      this.inflight ??= this.refresh().finally(() => {
        this.inflight = undefined;
      });
      await this.inflight;
    }
    const key = this.keys.get(kid);
    if (!key) fail(`unknown signing key: ${kid}`);
    try {
      return await key;
    } catch (e) {
      fail(
        `signing key ${kid} is not a usable Ed25519 key: ${(e as Error).message}`,
      );
    }
  }

  private async refresh(): Promise<void> {
    let body: { keys?: Jwk[] };
    try {
      const resp = await fetch(this.jwksUrl, {
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      body = await resp.json();
    } catch (e) {
      fail(
        `failed to fetch JWKS from ${this.jwksUrl}: ${(e as Error).message}`,
      );
    }
    const keys = new Map<string, Promise<CryptoKey>>();
    for (const jwk of body.keys ?? []) {
      if (jwk.kty !== "OKP" || jwk.crv !== "Ed25519" || !jwk.kid || !jwk.x)
        continue;
      const imported = subtle().importKey(
        "jwk",
        { kty: "OKP", crv: "Ed25519", x: jwk.x },
        { name: "Ed25519" },
        false,
        ["verify"],
      );
      imported.catch(() => undefined);
      keys.set(jwk.kid, imported);
    }
    this.keys = keys;
    this.fetchedAt = Date.now();
  }
}
