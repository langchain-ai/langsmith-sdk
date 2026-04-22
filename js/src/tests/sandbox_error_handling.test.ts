import { createServer, Server } from "http";
import { describe, it, expect, beforeAll, afterAll } from "@jest/globals";
import { SandboxClient } from "../experimental/sandbox/client.js";
import {
  LangSmithValidationError,
  LangSmithSandboxCreationError,
} from "../experimental/sandbox/errors.js";

let server: Server;
let port: number;
let nextResponse: { status: number; body: unknown };

beforeAll((done) => {
  server = createServer((_req, res) => {
    res.writeHead(nextResponse.status, {
      "Content-Type": "application/json",
    });
    res.end(JSON.stringify(nextResponse.body));
  });
  server.listen(0, () => {
    port = (server.address() as any).port;
    done();
  });
});

afterAll((done) => {
  server.close(done);
});

function makeClient(): SandboxClient {
  return new SandboxClient({
    apiEndpoint: `http://localhost:${port}/v2/sandboxes`,
    apiKey: "test-key",
    maxRetries: 0,
  });
}

describe("handleClientHttpError body consumption", () => {
  it("handles 422 with pydantic validation details without crashing", async () => {
    nextResponse = {
      status: 422,
      body: {
        detail: [
          {
            loc: ["body", "name"],
            msg: "field required",
            type: "value_error.missing",
          },
        ],
      },
    };

    const client = makeClient();

    // Bug: handleClientHttpError calls parseErrorResponse (consuming body),
    // then response.clone() — crashes with "Body has already been consumed"
    await expect(
      client.captureSnapshot("test-sandbox", "my-snapshot")
    ).rejects.toThrow(LangSmithValidationError);
  });
});

describe("handleSandboxCreationError body consumption", () => {
  it("handles 422 pydantic value_error during sandbox creation without crashing", async () => {
    nextResponse = {
      status: 422,
      body: {
        detail: [
          {
            loc: ["body", "vcpus"],
            msg: "ensure this value is greater than 0",
            type: "value_error",
          },
        ],
      },
    };

    const client = makeClient();

    await expect(
      client.createSandbox(undefined, { snapshotId: "snap-123" })
    ).rejects.toThrow(LangSmithValidationError);
  });

  it("handles 422 runtime creation error during sandbox creation", async () => {
    nextResponse = {
      status: 422,
      body: {
        detail: {
          error: "ImagePullFailed",
          message: "Failed to pull image foo:latest",
        },
      },
    };

    const client = makeClient();

    await expect(
      client.createSandbox(undefined, { snapshotId: "snap-123" })
    ).rejects.toThrow(LangSmithSandboxCreationError);
  });
});
