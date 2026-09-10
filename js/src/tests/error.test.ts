import { raiseForStatus } from "../utils/error.js";

// A real `Response` body is a single-use stream: once `raiseForStatus` reads it
// with `response.json()`, the fallback `response.text()` can no longer read it.
// These tests use real `Response` objects so the consumed-stream behaviour the
// 403 branch has to cope with is reproduced faithfully.
describe("raiseForStatus 403 handling", () => {
  it("includes the JSON error body for a non-org-scoped 403", async () => {
    const body = {
      error: "trace_project_forbidden",
      detail: "API key cannot write to the target project",
    };
    const response = new Response(JSON.stringify(body), {
      status: 403,
      statusText: "Forbidden",
      headers: { "content-type": "application/json" },
    });

    await expect(
      raiseForStatus(response, "send multipart request"),
    ).rejects.toThrow(/trace_project_forbidden/);
  });

  it("does not leave an empty Message when the body was valid JSON", async () => {
    // Regression guard for the bug where response.json() consumed the body and
    // the response.text() fallback then read a spent stream and yielded "".
    const body = { error: "some_other_error" };
    const response = new Response(JSON.stringify(body), {
      status: 403,
      statusText: "Forbidden",
      headers: { "content-type": "application/json" },
    });

    await expect(
      raiseForStatus(response, "send multipart request"),
    ).rejects.toThrow(/Message: (?!\s*$).+/);
  });

  it("keeps the descriptive message for org_scoped_key_requires_workspace", async () => {
    const body = { error: "org_scoped_key_requires_workspace" };
    const response = new Response(JSON.stringify(body), {
      status: 403,
      statusText: "Forbidden",
      headers: { "content-type": "application/json" },
    });

    await expect(
      raiseForStatus(response, "send multipart request"),
    ).rejects.toThrow(/org-scoped and requires workspace specification/);
  });

  it("throws a bare status for a non-JSON 403 body", async () => {
    const response = new Response("<html>403 Forbidden</html>", {
      status: 403,
      statusText: "Forbidden",
      headers: { "content-type": "text/html" },
    });

    await expect(
      raiseForStatus(response, "send multipart request"),
    ).rejects.toThrow("403 Forbidden");
  });
});
