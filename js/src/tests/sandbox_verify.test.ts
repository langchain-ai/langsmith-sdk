import {
  jest,
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
} from "@jest/globals";
import { createHash, randomUUID } from "node:crypto";
import { SandboxTokenVerifier } from "../sandbox/verify.js";
import { LangSmithSandboxTokenVerificationError } from "../sandbox/errors.js";

const API_URL = "https://api.example.com/api/v1";
const JWKS_URL = "https://api.example.com/.well-known/jwks.json";
const APP_URL = "https://app.example.com";
const SERVICE_HOST =
  "0190aaaa-0000-7000-8000-000000000001--8080.svc.example.com";
const CALLBACK_URL = "https://integrator.example.com/sandbox-callback";
const KID = "test-kid";

const b64url = (data: string | Uint8Array) =>
  Buffer.from(data).toString("base64url");

async function newKey(): Promise<CryptoKeyPair> {
  return (await crypto.subtle.generateKey({ name: "Ed25519" }, true, [
    "sign",
    "verify",
  ])) as CryptoKeyPair;
}

async function jwk(pair: CryptoKeyPair, kid: string) {
  return {
    ...(await crypto.subtle.exportKey("jwk", pair.publicKey)),
    kid,
    alg: "EdDSA",
    use: "sig",
  };
}

async function sign(
  pair: CryptoKeyPair,
  claims: Record<string, unknown>,
  header: Record<string, unknown> = { alg: "EdDSA", kid: KID },
): Promise<string> {
  const input = `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(claims))}`;
  const sig = await crypto.subtle.sign(
    { name: "Ed25519" },
    pair.privateKey,
    new TextEncoder().encode(input),
  );
  return `${input}.${b64url(new Uint8Array(sig))}`;
}

const now = () => Math.floor(Date.now() / 1000);

const userClaims = (overrides: Record<string, unknown> = {}) => ({
  iss: APP_URL,
  sub: "user-123",
  aud: [SERVICE_HOST],
  exp: now() + 600,
  iat: now(),
  email: "ada@example.com",
  name: "Ada",
  ...overrides,
});

const callbackBody = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    host: "api.github.com",
    port: 443,
    identity: {
      tenant_id: randomUUID(),
      sandbox_id: randomUUID(),
      organization_id: randomUUID(),
      ls_user_id: randomUUID(),
    },
    ...overrides,
  });

const callbackClaims = (
  body: string,
  overrides: Record<string, unknown> = {},
) => ({
  iss: APP_URL,
  sub: "langsmith-sandbox-callback",
  aud: [CALLBACK_URL],
  iat: now(),
  nbf: now(),
  exp: now() + 300,
  jti: randomUUID(),
  body_sha256: createHash("sha256").update(body).digest("hex"),
  ...overrides,
});

describe("SandboxTokenVerifier", () => {
  let pair: CryptoKeyPair;
  let fetchMock: jest.SpiedFunction<typeof fetch>;

  const serveKeys = (...keys: unknown[]) =>
    fetchMock.mockImplementation(async () => Response.json({ keys }));

  beforeEach(async () => {
    pair = await newKey();
    fetchMock = jest.spyOn(globalThis, "fetch");
    serveKeys(await jwk(pair, KID));
  });

  afterEach(() => {
    fetchMock.mockRestore();
  });

  const verifier = () => new SandboxTokenVerifier({ apiUrl: API_URL });

  describe("verifyUserToken", () => {
    it("returns the user for a valid token", async () => {
      const user = await verifier().verifyUserToken(
        await sign(pair, userClaims()),
        {
          audience: SERVICE_HOST,
          issuer: APP_URL,
        },
      );
      expect(user.subject).toBe("user-123");
      expect(user.email).toBe("ada@example.com");
      expect(user.name).toBe("Ada");
      expect(fetchMock.mock.calls[0][0]).toBe(JWKS_URL);
    });

    it("accepts a service URL as the audience", async () => {
      const user = await verifier().verifyUserToken(
        await sign(pair, userClaims()),
        {
          audience: `https://${SERVICE_HOST}/path`,
        },
      );
      expect(user.subject).toBe("user-123");
    });

    it.each([
      ["wrong audience", { aud: ["other--8080.svc.example.com"] }, {}],
      ["expired", { exp: now() - 120 }, {}],
      ["bad issuer", {}, { issuer: "https://evil.example.com" }],
      ["empty subject", { sub: "" }, {}],
      ["missing subject", { sub: undefined }, {}],
      ["callback subject", { sub: "langsmith-sandbox-callback" }, {}],
      ["future iat", { iat: now() + 600 }, {}],
    ])("rejects %s", async (_name, claims, opts) => {
      const token = await sign(pair, userClaims(claims));
      await expect(
        verifier().verifyUserToken(token, { audience: SERVICE_HOST, ...opts }),
      ).rejects.toThrow(LangSmithSandboxTokenVerificationError);
    });

    it("rejects a token signed by another key", async () => {
      const token = await sign(await newKey(), userClaims());
      await expect(
        verifier().verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("invalid signature");
    });

    it("rejects non-EdDSA tokens", async () => {
      const token = await sign(pair, userClaims(), { alg: "HS256", kid: KID });
      await expect(
        verifier().verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("algorithm");
    });

    it("rejects a tampered payload", async () => {
      const [h, , s] = (await sign(pair, userClaims())).split(".");
      const forged = `${h}.${b64url(JSON.stringify(userClaims({ sub: "admin" })))}.${s}`;
      await expect(
        verifier().verifyUserToken(forged, { audience: SERVICE_HOST }),
      ).rejects.toThrow("invalid signature");
    });

    it("caches the JWKS", async () => {
      const v = verifier();
      for (let i = 0; i < 3; i++) {
        await v.verifyUserToken(await sign(pair, userClaims()), {
          audience: SERVICE_HOST,
        });
      }
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("refetches for a rotated key", async () => {
      const v = verifier();
      await v.verifyUserToken(await sign(pair, userClaims()), {
        audience: SERVICE_HOST,
      });
      const rotated = await newKey();
      serveKeys(await jwk(pair, KID), await jwk(rotated, "new"));
      (v as unknown as { fetchedAt: number }).fetchedAt -= 60_000;
      const user = await v.verifyUserToken(
        await sign(rotated, userClaims(), { alg: "EdDSA", kid: "new" }),
        { audience: SERVICE_HOST },
      );
      expect(user.subject).toBe("user-123");
    });

    it("rejects an unknown kid without refetching inside the throttle window", async () => {
      const v = verifier();
      await v.verifyUserToken(await sign(pair, userClaims()), {
        audience: SERVICE_HOST,
      });
      const token = await sign(pair, userClaims(), {
        alg: "EdDSA",
        kid: "nope",
      });
      await expect(
        v.verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("unknown signing key");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("verifyCallback", () => {
    it("returns the payload for a valid callback", async () => {
      const body = callbackBody();
      const cb = await verifier().verifyCallback({
        body,
        signature: await sign(pair, callbackClaims(body)),
        url: CALLBACK_URL,
        issuer: APP_URL,
      });
      expect(cb.host).toBe("api.github.com");
      expect(cb.port).toBe(443);
      expect(cb.identity.sandbox_id).toBe(JSON.parse(body).identity.sandbox_id);
    });

    it("accepts a byte body", async () => {
      const body = callbackBody();
      const cb = await verifier().verifyCallback({
        body: new TextEncoder().encode(body),
        signature: await sign(pair, callbackClaims(body)),
        url: CALLBACK_URL,
      });
      expect(cb.port).toBe(443);
    });

    it("skips the audience check without a url", async () => {
      const body = callbackBody();
      const cb = await verifier().verifyCallback({
        body,
        signature: await sign(
          pair,
          callbackClaims(body, { aud: ["https://other.example.com/cb"] }),
        ),
      });
      expect(cb.port).toBe(443);
    });

    it("rejects a tampered body", async () => {
      const body = callbackBody();
      const signature = await sign(pair, callbackClaims(body));
      await expect(
        verifier().verifyCallback({
          body: callbackBody({ host: "evil.example.com" }),
          signature,
          url: CALLBACK_URL,
        }),
      ).rejects.toThrow("body does not match");
    });

    it.each([
      ["wrong url", { aud: ["https://other.example.com/cb"] }],
      ["wrong subject", { sub: "user-123" }],
      ["expired", { exp: now() - 120 }],
      ["missing body hash", { body_sha256: undefined }],
    ])("rejects %s", async (_name, claims) => {
      const body = callbackBody();
      await expect(
        verifier().verifyCallback({
          body,
          signature: await sign(pair, callbackClaims(body, claims)),
          url: CALLBACK_URL,
        }),
      ).rejects.toThrow(LangSmithSandboxTokenVerificationError);
    });
  });
});
