import { raiseForStatus } from "../utils/error.js";

// Real `Response` bodies are single-use streams: these assertions fail if
// `raiseForStatus` reads the body more than once.
describe("raiseForStatus", () => {
  it("surfaces the server's message for a non-org-scoped 403", async () => {
    const response = new Response(
      JSON.stringify({ error: "usage_limit_exceeded", detail: "over quota" }),
      { status: 403, statusText: "Forbidden" },
    );

    await expect(
      raiseForStatus(response, "send multipart request"),
    ).rejects.toThrow(
      'Failed to send multipart request. Received status [403]: Forbidden. Message: {"error":"usage_limit_exceeded","detail":"over quota"}',
    );
  });

  it("maps the org-scoped key 403 to a workspace hint", async () => {
    const response = new Response(
      JSON.stringify({ error: "org_scoped_key_requires_workspace" }),
      { status: 403, statusText: "Forbidden" },
    );

    await expect(raiseForStatus(response, "create run")).rejects.toThrow(
      "This API key is org-scoped and requires workspace specification.",
    );
  });

  it("throws a bare status error for a non-JSON 403 body", async () => {
    const response = new Response("nginx denied this", {
      status: 403,
      statusText: "Forbidden",
    });

    await expect(raiseForStatus(response, "create run")).rejects.toThrow(
      "403 Forbidden",
    );
  });

  it("surfaces the body for other error statuses", async () => {
    const response = new Response("no such run", {
      status: 404,
      statusText: "Not Found",
    });

    await expect(raiseForStatus(response, "read run")).rejects.toThrow(
      "Failed to read run. Received status [404]: Not Found. Message: no such run",
    );
  });
});
