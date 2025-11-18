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

  it("should respect Retry-After header with seconds", async () => {
    testMode = "retry_after_seconds";
    requestCount = 0;
    const retryDelaySeconds = 1;
    const startTime = Date.now();

    testServer.removeAllListeners("request");
    testServer.on("request", (req, res) => {
      requestCount++;

      if (requestCount === 1) {
        // First request: return 429 with Retry-After in seconds
        res.writeHead(429, {
          "Content-Type": "application/json",
          "Retry-After": retryDelaySeconds.toString(),
        });
        res.end(JSON.stringify({ error: "Too Many Requests" }));
      } else {
        // Second request: succeed
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

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 5000,
      autoBatchTracing: true,
    });

    (client as any).caller = new AsyncCaller({
      maxRetries: 2,
      maxConcurrency: 1,
    });

    const result = await client.readRun(v4());
    const elapsedTime = Date.now() - startTime;

    expect(result).toHaveProperty("id");
    expect(requestCount).toBe(2);
    // Should have waited at least the retry delay
    expect(elapsedTime).toBeGreaterThanOrEqual(retryDelaySeconds * 1000);
  });

  it("should respect Retry-After header with HTTP date", async () => {
    testMode = "retry_after_date";
    requestCount = 0;
    const retryDelayMs = 1000;
    const startTime = Date.now();

    testServer.removeAllListeners("request");
    testServer.on("request", (req, res) => {
      requestCount++;

      if (requestCount === 1) {
        // First request: return 429 with Retry-After as HTTP date
        const retryAfterDate = new Date(Date.now() + retryDelayMs);
        res.writeHead(429, {
          "Content-Type": "application/json",
          "Retry-After": retryAfterDate.toUTCString(),
        });
        res.end(JSON.stringify({ error: "Too Many Requests" }));
      } else {
        // Second request: succeed
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

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 5000,
      autoBatchTracing: true,
    });

    (client as any).caller = new AsyncCaller({
      maxRetries: 2,
      maxConcurrency: 1,
    });

    const result = await client.readRun(v4());
    const elapsedTime = Date.now() - startTime;

    expect(result).toHaveProperty("id");
    expect(requestCount).toBe(2);
    // Should have waited at least the retry delay (with some tolerance for timing)
    expect(elapsedTime).toBeGreaterThanOrEqual(retryDelayMs - 100);
  });

  it("should respect maxRetries even with Retry-After header", async () => {
    testMode = "retry_after_max_retries";
    requestCount = 0;

    testServer.removeAllListeners("request");
    testServer.on("request", (req, res) => {
      requestCount++;
      // Always return 429 with Retry-After
      res.writeHead(429, {
        "Content-Type": "application/json",
        "Retry-After": "1",
      });
      res.end(JSON.stringify({ error: "Too Many Requests" }));
    });

    const client = new Client({
      apiKey: "test-api-key",
      apiUrl: `http://localhost:${port}`,
      timeout_ms: 10000,
      autoBatchTracing: true,
    });

    const maxRetries = 2;
    (client as any).caller = new AsyncCaller({
      maxRetries,
      maxConcurrency: 1,
    });

    // Should fail after exhausting retries
    await expect(client.readRun(v4())).rejects.toThrow();

    // Should make initial attempt + maxRetries attempts
    expect(requestCount).toBe(maxRetries + 1);
  });
});
