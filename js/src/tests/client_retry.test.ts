/* eslint-disable @typescript-eslint/no-explicit-any */
import { v4 } from "uuid";
import { createServer, Server } from "http";
import { Client } from "../client.js";
import { AsyncCaller } from "../utils/async_caller.js";

describe("Client timeout and retry behavior", () => {
  let testServer: Server;
  const port = 9876;
  let requestCount = 0;
  let testMode = "timeout";

  beforeAll((done) => {
    testServer = createServer((req, res) => {
      requestCount++;

      if (testMode === "timeout") {
        // Never respond to simulate timeout
        return;
      } else if (testMode === "408_timeout") {
        // Return 408 Request Timeout status (should not retry)
        res.writeHead(408, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Request Timeout" }));
      } else if (testMode === "429_retry") {
        if (requestCount <= 2) {
          // First two requests: return 429 (should retry)
          res.writeHead(429, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Too Many Requests" }));
          return;
        }
        // Third request: succeed
        const url = req.url || "";
        const runId = url.split("/runs/")[1] || "test-run-id";
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            id: runId,
            name: "test_run",
            run_type: "llm",
            status: "success",
            start_time: new Date().toISOString(),
            end_time: new Date().toISOString(),
          })
        );
      }
    });

    testServer.listen(port, done);
  });

  afterAll((done) => {
    testServer.close(done);
  });

  it("should not retry on 408 timeout status", async () => {
    testMode = "408_timeout";
    requestCount = 0;

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 1000,
      autoBatchTracing: true,
    });

    // Override caller with lower max retries for faster test
    (client as any).caller = new AsyncCaller({
      maxRetries: 2,
      maxConcurrency: 1,
    });

    // Should fail immediately without retries on 408 status
    await expect(client.readRun(v4())).rejects.toThrow();

    // Should only make one request (no retries)
    expect(requestCount).toBe(1);
  });

  it("should retry on 429 status and eventually succeed", async () => {
    testMode = "429_retry";
    requestCount = 0;

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 1000,
      autoBatchTracing: true,
    });

    // Override caller with lower max retries for faster test
    (client as any).caller = new AsyncCaller({
      maxRetries: 3,
      maxConcurrency: 1,
    });

    // This should succeed after retries
    const result = await client.readRun(v4());
    expect(result).toHaveProperty("id");
    expect(result.name).toBe("test_run");
    expect(requestCount).toBe(3); // Should have made 3 requests (2 failures + 1 success)
  });

  it("should not retry on timeout", async () => {
    testMode = "timeout";
    requestCount = 0;

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 1000,
      autoBatchTracing: true,
    });

    await expect(client.readRun(v4())).rejects.toThrow();
    expect(requestCount).toBe(1);
  });
});
