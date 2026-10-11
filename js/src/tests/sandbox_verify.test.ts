import {
  jest,
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
} from "@jest/globals";
import {
  constants,
  createHash,
  createHmac,
  generateKeyPairSync,
  randomUUID,
  sign as nodeSign,
  type KeyObject,
} from "node:crypto";
import { SandboxTokenVerifier } from "../sandbox/verify.js";
import { LangSmithSandboxTokenVerificationError } from "../sandbox/errors.js";

const API_URL = "https://api.example.com/api/v1";
const JWKS_URL = "https://api.example.com/.well-known/jwks.json";
const APP_URL = "https://app.example.com";
const SERVICE_HOST =
  "0190aaaa-0000-7000-8000-000000000001--8080.svc.example.com";
const CALLBACK_URL = "https://integrator.example.com/sandbox-callback";
const KID = "test-kid";
const RSA_KID = "rsa-kid";

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

type RsaPair = { publicKey: KeyObject; privateKey: KeyObject };

const newRsaKey = (modulusLength = 2048): RsaPair =>
  generateKeyPairSync("rsa", { modulusLength });

const rsaJwk = (
  pair: RsaPair,
  kid: string,
  overrides: Record<string, unknown> = {},
) => ({
  ...pair.publicKey.export({ format: "jwk" }),
  kid,
  alg: "RS256",
  use: "sig",
  ...overrides,
});

function signWith(
  header: Record<string, unknown>,
  claims: Record<string, unknown>,
  signer: (input: Buffer) => Uint8Array,
): string {
  const input = `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(claims))}`;
  return `${input}.${b64url(signer(Buffer.from(input)))}`;
}

function signRsa(
  pair: RsaPair,
  claims: Record<string, unknown>,
  header: Record<string, unknown> = { alg: "RS256", kid: RSA_KID },
): string {
  return signWith(header, claims, (input) => {
    switch (header.alg) {
      case "RS512":
        return nodeSign("sha512", input, pair.privateKey);
      case "PS256":
        return nodeSign("sha256", input, {
          key: pair.privateKey,
          padding: constants.RSA_PKCS1_PSS_PADDING,
          saltLength: 32,
        });
      default:
        return nodeSign("sha256", input, pair.privateKey);
    }
  });
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

  describe("RS256", () => {
    let rsa: RsaPair;

    beforeEach(async () => {
      rsa = newRsaKey();
      serveKeys(await jwk(pair, KID), rsaJwk(rsa, RSA_KID));
    });

    // Fills the key cache first, so rejections are not just a side effect of
    // never fetching the JWKS.
    const primed = async () => {
      const v = verifier();
      await v.verifyUserToken(await sign(pair, userClaims()), {
        audience: SERVICE_HOST,
      });
      await v.verifyUserToken(signRsa(rsa, userClaims()), {
        audience: SERVICE_HOST,
      });
      return v;
    };

    it("verifies an RS256 token", async () => {
      serveKeys(rsaJwk(rsa, RSA_KID));
      const user = await verifier().verifyUserToken(
        signRsa(rsa, userClaims()),
        { audience: SERVICE_HOST, issuer: APP_URL },
      );
      expect(user.subject).toBe("user-123");
      expect(user.email).toBe("ada@example.com");
    });

    it("verifies an RS256 token under a JWK without alg or use", async () => {
      const { alg: _alg, use: _use, ...bare } = rsaJwk(rsa, RSA_KID);
      serveKeys(bare);
      const user = await verifier().verifyUserToken(
        signRsa(rsa, userClaims()),
        { audience: SERVICE_HOST },
      );
      expect(user.subject).toBe("user-123");
    });

    it("verifies tokens under each kid of a mixed JWKS", async () => {
      const v = verifier();
      for (const token of [
        await sign(pair, userClaims()),
        signRsa(rsa, userClaims()),
      ]) {
        const user = await v.verifyUserToken(token, { audience: SERVICE_HOST });
        expect(user.subject).toBe("user-123");
      }
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("rejects an RS256 token signed by another key", async () => {
      await expect(
        verifier().verifyUserToken(signRsa(newRsaKey(), userClaims()), {
          audience: SERVICE_HOST,
        }),
      ).rejects.toThrow("invalid signature");
    });

    it("rejects an EdDSA header under an RSA kid", async () => {
      const token = await sign(pair, userClaims(), {
        alg: "EdDSA",
        kid: RSA_KID,
      });
      await expect(
        (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("algorithm");
    });

    it("rejects an RS256 header under an Ed25519 kid", async () => {
      const token = signRsa(rsa, userClaims(), { alg: "RS256", kid: KID });
      await expect(
        (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("algorithm");
    });

    it.each([RSA_KID, KID])("rejects alg none under %s", async (kid) => {
      const token = signWith(
        { alg: "none", kid },
        userClaims(),
        () => new Uint8Array(),
      );
      await expect(
        (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("algorithm");
    });

    it.each(["pem", "jwk"])(
      "rejects HS256 keyed with the RSA public key (%s)",
      async (encoding) => {
        const secret =
          encoding === "pem"
            ? rsa.publicKey.export({ type: "spki", format: "pem" })
            : JSON.stringify(rsaJwk(rsa, RSA_KID));
        const token = signWith(
          { alg: "HS256", typ: "JWT", kid: RSA_KID },
          userClaims(),
          (input) => createHmac("sha256", secret).update(input).digest(),
        );
        await expect(
          (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
        ).rejects.toThrow("algorithm");
      },
    );

    it.each(["RS512", "PS256"])(
      "rejects a %s header under an RSA kid",
      async (alg) => {
        const token = signRsa(rsa, userClaims(), { alg, kid: RSA_KID });
        await expect(
          (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
        ).rejects.toThrow("algorithm");
      },
    );

    it("rejects an ES256 header under an RSA kid", async () => {
      const token = signWith(
        { alg: "ES256", kid: RSA_KID },
        userClaims(),
        () => new Uint8Array(64),
      );
      await expect(
        (await primed()).verifyUserToken(token, { audience: SERVICE_HOST }),
      ).rejects.toThrow("algorithm");
    });

    it("skips an RSA-1024 key and keeps the others", async () => {
      const weak = newRsaKey(1024);
      serveKeys(rsaJwk(weak, "weak"), await jwk(pair, KID));
      const v = verifier();
      const user = await v.verifyUserToken(await sign(pair, userClaims()), {
        audience: SERVICE_HOST,
      });
      expect(user.subject).toBe("user-123");
      await expect(
        v.verifyUserToken(
          signRsa(weak, userClaims(), { alg: "RS256", kid: "weak" }),
          { audience: SERVICE_HOST },
        ),
      ).rejects.toThrow("unknown signing key");
    });

    it.each([
      ["alg RS512", { alg: "RS512" }],
      ["alg EdDSA", { alg: "EdDSA" }],
      ["use enc", { use: "enc" }],
    ])("skips an RSA JWK with %s", async (_name, overrides) => {
      serveKeys(rsaJwk(rsa, RSA_KID, overrides), await jwk(pair, KID));
      const v = verifier();
      const user = await v.verifyUserToken(await sign(pair, userClaims()), {
        audience: SERVICE_HOST,
      });
      expect(user.subject).toBe("user-123");
      await expect(
        v.verifyUserToken(signRsa(rsa, userClaims()), {
          audience: SERVICE_HOST,
        }),
      ).rejects.toThrow("unknown signing key");
    });

    it("skips an Ed25519 JWK with alg RS256", async () => {
      serveKeys(
        { ...(await jwk(pair, KID)), alg: "RS256" },
        rsaJwk(rsa, RSA_KID),
      );
      await expect(
        verifier().verifyUserToken(await sign(pair, userClaims()), {
          audience: SERVICE_HOST,
        }),
      ).rejects.toThrow("unknown signing key");
    });

    it("keeps proxy callbacks EdDSA-only", async () => {
      const body = callbackBody();
      await expect(
        (await primed()).verifyCallback({
          body,
          signature: signRsa(rsa, callbackClaims(body)),
          aud: CALLBACK_URL,
        }),
      ).rejects.toThrow("algorithm");
    });

    it("rejects a callback EdDSA header under an RSA kid", async () => {
      const body = callbackBody();
      await expect(
        (await primed()).verifyCallback({
          body,
          signature: await sign(pair, callbackClaims(body), {
            alg: "EdDSA",
            kid: RSA_KID,
          }),
          aud: CALLBACK_URL,
        }),
      ).rejects.toThrow("algorithm");
    });
  });

  describe("JWKS URL", () => {
    it.each([
      "http://localhost:1984/.well-known/jwks.json",
      "http://127.0.0.1:1984/.well-known/jwks.json",
      "http://[::1]:1984/.well-known/jwks.json",
    ])("allows http loopback %s", (jwksUrl) => {
      expect(() => new SandboxTokenVerifier({ jwksUrl })).not.toThrow();
    });

    it.each([
      [{ jwksUrl: "http://langsmith.internal/.well-known/jwks.json" }],
      [{ apiUrl: "http://langsmith.internal/api/v1" }],
      [{ jwksUrl: "http://127.example.com/.well-known/jwks.json" }],
      [{ jwksUrl: "ftp://langsmith.internal/jwks.json" }],
    ])("rejects insecure %j", (config) => {
      expect(() => new SandboxTokenVerifier(config)).toThrow("https");
    });

    it("allows plain http with allowInsecureJwks", () => {
      expect(
        () =>
          new SandboxTokenVerifier({
            jwksUrl: "http://langsmith.internal/.well-known/jwks.json",
            allowInsecureJwks: true,
          }),
      ).not.toThrow();
    });
  });

  describe("JWKS fetch", () => {
    it("shares one fetch across concurrent misses", async () => {
      const v = verifier();
      const token = await sign(pair, userClaims());
      const users = await Promise.all(
        Array.from({ length: 8 }, () =>
          v.verifyUserToken(token, { audience: SERVICE_HOST }),
        ),
      );
      expect(users.every((u) => u.subject === "user-123")).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it.each([
      ["null", null],
      ["keys object", { keys: {} }],
      ["array", []],
    ])("rejects a malformed JWKS (%s)", async (_name, body) => {
      fetchMock.mockImplementation(async () => Response.json(body));
      await expect(
        verifier().verifyUserToken(await sign(pair, userClaims()), {
          audience: SERVICE_HOST,
        }),
      ).rejects.toThrow(LangSmithSandboxTokenVerificationError);
    });

    it("skips non-object JWKS entries", async () => {
      fetchMock.mockImplementation(async () =>
        Response.json({ keys: [null, 1, await jwk(pair, KID)] }),
      );
      const user = await verifier().verifyUserToken(
        await sign(pair, userClaims()),
        { audience: SERVICE_HOST },
      );
      expect(user.subject).toBe("user-123");
    });
  });

  describe("verifyCallback", () => {
    it("returns the payload for a valid callback", async () => {
      const body = callbackBody();
      const cb = await verifier().verifyCallback({
        body,
        signature: await sign(pair, callbackClaims(body)),
        aud: CALLBACK_URL,
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
        aud: CALLBACK_URL,
      });
      expect(cb.port).toBe(443);
    });

    it("accepts an aud predicate", async () => {
      const body = callbackBody();
      const signature = await sign(pair, callbackClaims(body));
      const cb = await verifier().verifyCallback({
        body,
        signature,
        aud: (a) => a.startsWith("https://integrator.example.com/"),
      });
      expect(cb.port).toBe(443);
      await expect(
        verifier().verifyCallback({
          body,
          signature,
          aud: (a) => a === "https://x/cb",
        }),
      ).rejects.toThrow("audience");
    });

    it("skips the audience check without aud", async () => {
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
          aud: CALLBACK_URL,
        }),
      ).rejects.toThrow("body does not match");
    });

    it.each([
      ["wrong aud", { aud: ["https://other.example.com/cb"] }],
      ["wrong subject", { sub: "user-123" }],
      ["expired", { exp: now() - 120 }],
      ["missing body hash", { body_sha256: undefined }],
    ])("rejects %s", async (_name, claims) => {
      const body = callbackBody();
      await expect(
        verifier().verifyCallback({
          body,
          signature: await sign(pair, callbackClaims(body, claims)),
          aud: CALLBACK_URL,
        }),
      ).rejects.toThrow(LangSmithSandboxTokenVerificationError);
    });
  });
});
