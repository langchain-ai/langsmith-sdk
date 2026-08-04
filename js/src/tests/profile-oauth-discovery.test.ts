import * as http from "node:http";
import { resolveTokenEndpoint } from "../utils/profiles.js";

type Doc = Record<string, unknown> | string | null;

/** Start a server whose handler maps (path, base) to JSON, HTML, or a 404. */
async function serve(
  handler: (path: string, base: string) => Doc,
): Promise<{ base: string; close: () => Promise<void> }> {
  let base = "";
  const server = http.createServer((req, res) => {
    const result = handler(req.url ?? "", base);
    if (result === null) {
      res.writeHead(404);
      res.end();
      return;
    }
    if (typeof result === "string") {
      res.writeHead(200, { "Content-Type": "text/html" });
      res.end(result);
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(result));
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("failed to bind test server");
  }
  base = `http://127.0.0.1:${address.port}`;
  return {
    base,
    close: () =>
      new Promise<void>((resolve) => {
        server.close(() => resolve());
      }),
  };
}

/** Metadata under /api plus an HTML 200 at the root, like the self-hosted SPA. */
function selfHostedHandler(path: string, base: string): Doc {
  if (path === "/api/.well-known/oauth-authorization-server") {
    return {
      issuer: `${base}/api`,
      device_authorization_endpoint: `${base}/api/oauth/device/code`,
      token_endpoint: `${base}/api/oauth/token`,
    };
  }
  if (path === "/.well-known/oauth-authorization-server") {
    return "<!doctype html><html><body>app</body></html>";
  }
  return null;
}

describe("resolveTokenEndpoint", () => {
  it("resolves the self-hosted AS from a bare origin", async () => {
    const { base, close } = await serve(selfHostedHandler);
    try {
      expect(await resolveTokenEndpoint(base, fetch)).toBe(
        `${base}/api/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  it("resolves the self-hosted AS from an /api url", async () => {
    const { base, close } = await serve(selfHostedHandler);
    try {
      expect(await resolveTokenEndpoint(`${base}/api`, fetch)).toBe(
        `${base}/api/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  it("resolves SaaS at the root", async () => {
    const { base, close } = await serve((path, b) =>
      path === "/.well-known/oauth-authorization-server"
        ? {
            issuer: b,
            device_authorization_endpoint: `${b}/oauth/device/code`,
            token_endpoint: `${b}/oauth/token`,
          }
        : null,
    );
    try {
      expect(await resolveTokenEndpoint(base, fetch)).toBe(
        `${base}/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  it("keeps the /api mount when no metadata is served", async () => {
    const { base, close } = await serve(() => null);
    try {
      expect(await resolveTokenEndpoint(`${base}/api`, fetch)).toBe(
        `${base}/api/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  it("strips /api/v1 in the fallback", async () => {
    const { base, close } = await serve(() => null);
    try {
      expect(await resolveTokenEndpoint(`${base}/api/v1`, fetch)).toBe(
        `${base}/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  // Refresh tokens are posted to this endpoint, so untrusted documents must be
  // ignored in favour of the fallback.
  it("ignores a document whose issuer does not match", async () => {
    const { base, close } = await serve((path, b) =>
      path === "/.well-known/oauth-authorization-server"
        ? {
            issuer: "https://evil.example.com",
            device_authorization_endpoint: `${b}/oauth/device/code`,
            token_endpoint: `${b}/oauth/token`,
          }
        : null,
    );
    try {
      expect(await resolveTokenEndpoint(base, fetch)).toBe(
        `${base}/oauth/token`,
      );
    } finally {
      await close();
    }
  });

  it("ignores an endpoint on another origin", async () => {
    const { base, close } = await serve((path, b) =>
      path === "/.well-known/oauth-authorization-server"
        ? {
            issuer: b,
            device_authorization_endpoint: `${b}/oauth/device/code`,
            token_endpoint: "https://evil.example.com/oauth/token",
          }
        : null,
    );
    try {
      expect(await resolveTokenEndpoint(base, fetch)).toBe(
        `${base}/oauth/token`,
      );
    } finally {
      await close();
    }
  });
});
