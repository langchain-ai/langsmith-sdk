/* eslint-disable no-process-env, no-instanceof/no-instanceof */
import { traceable } from "../traceable.js";
import { Client } from "../client.js";
import { v7 as uuidv7 } from "uuid";

import * as fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

test("Test performance with large runs and concurrency", async () => {
  const pathname = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "test_data",
    "beemovie.txt"
  );

  const largeInput = { bee: fs.readFileSync(pathname).toString() };
  const client = new Client({
    debug: true,
  });
  const largeTest = traceable(
    async (foo: { bee: string }) => {
      await new Promise((resolve) => setTimeout(resolve, 100));
      return { reversebee: foo.bee.toString().split("").reverse().join("") };
    },
    {
      client,
    }
  );

  await Promise.all(
    Array.from({ length: 1000 }, async () => {
      await largeTest(largeInput);
    })
  );

  await client.awaitPendingTraceBatches();
});

/**
 * Benchmark event-loop blocking caused by tracing large payloads.
 *
 * This test measures how long the event loop is unable to run other work
 * while the SDK performs end-to-end createRun/updateRun calls with large
 * payloads. A monitor runs on a short timer and records the actual delay
 * between ticks -- any delay beyond the target interval is time the event
 * loop was blocked.
 *
 * The hot-path size estimator is assumed to be enabled (it landed
 * separately and is now the standard hot-path behavior). The flush-time
 * worker offload is force-enabled inside the test, so the result reflects
 * the full perf optimization stack.
 *
 * The benchmark is skipped by default and runs only when
 * LANGSMITH_RUN_PERF_BENCH=true. The js-perf CI workflow sets that flag
 * and runs the bench on both `main` and PR HEAD to produce a PR comment.
 *
 * Manual run:
 *   LANGSMITH_RUN_PERF_BENCH=true LANGSMITH_TRACING=false \
 *     pnpm test:integration src/tests/perf.int.test.ts -t "benchmark event loop"
 */
// Force the perf optimization on for benchmark runs so results reflect
// the shipped perf behavior regardless of the invoker's env.
process.env.LANGSMITH_PERF_OPTIMIZATION = "true";

// Enabled by setting LANGSMITH_RUN_PERF_BENCH=true. Skipped in CI by default.
const benchIt =
  process.env.LANGSMITH_RUN_PERF_BENCH === "true" ? test : test.skip;
benchIt(
  "benchmark event loop blocking from tracing large payloads",
  async () => {
    const pathname = path.join(
      path.dirname(fileURLToPath(import.meta.url)),
      "test_data",
      "beemovie.txt"
    );

    // Build a realistically large payload. Real-world LangSmith payloads
    // are frequently dominated by inlined base64 image data in OpenAI-style
    // message content parts -- exactly the shape that structuredClone /
    // worker transfer handles best. We therefore construct a payload that
    // matches that shape.
    const baseText = fs.readFileSync(pathname).toString();
    const base64Chunk =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
    // ~500KB base64 image per message
    const imageB64 = base64Chunk.repeat(
      Math.ceil((500 * 1024) / base64Chunk.length)
    );
    const dataUri = `data:image/png;base64,${imageB64}`;
    const largeInputs = {
      messages: Array.from({ length: 5 }, (_, i) => ({
        role: i % 2 === 0 ? "user" : "assistant",
        content: [
          { type: "text", text: baseText.slice(0, 2000) },
          { type: "image_url", image_url: { url: dataUri, detail: "high" } },
        ],
      })),
      model: "gpt-4o",
      temperature: 0.7,
    };
    const largeOutputs = {
      choices: [
        {
          message: {
            role: "assistant",
            content: baseText.slice(0, 5000),
          },
          finish_reason: "stop",
        },
      ],
      usage: {
        prompt_tokens: 120000,
        completion_tokens: 48000,
      },
    };

    const inputJsonSize = JSON.stringify(largeInputs).length;
    const outputJsonSize = JSON.stringify(largeOutputs).length;

    const targetInterval = 1;
    const lags: number[] = [];
    let lastTick = performance.now();
    const monitor = setInterval(() => {
      const now = performance.now();
      const lag = now - lastTick - targetInterval;
      if (lag > 0) lags.push(lag);
      lastTick = now;
    }, targetInterval);
    monitor.unref();

    const fetchImplementation: typeof fetch = async (input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
          ? input.toString()
          : input.url;
      if (url.endsWith("/info")) {
        return new Response(
          JSON.stringify({
            batch_ingest_config: {
              use_multipart_endpoint: true,
              size_limit: 100,
              size_limit_bytes: 20 * 1024 * 1024,
            },
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          }
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 202,
        headers: { "content-type": "application/json" },
      });
    };

    const client = new Client({
      autoBatchTracing: true,
      fetchImplementation,
      fetchOptions: {
        signal: AbortSignal.timeout(30_000),
      },
    });

    const NUM_RUNS = 100;
    const createTimes: number[] = [];
    const updateTimes: number[] = [];
    const wallStart = performance.now();

    for (let i = 0; i < NUM_RUNS; i++) {
      const runId = uuidv7();

      const createStart = performance.now();
      await client.createRun({
        id: runId,
        trace_id: runId,
        dotted_order: `${new Date().toISOString()}${runId}`,
        name: "bench_run",
        run_type: "llm",
        inputs: largeInputs,
        start_time: Date.now(),
      });
      createTimes.push(performance.now() - createStart);

      await new Promise((resolve) => setImmediate(resolve));

      const updateStart = performance.now();
      await client.updateRun(runId, {
        outputs: largeOutputs,
        end_time: Date.now(),
      });
      updateTimes.push(performance.now() - updateStart);

      await new Promise((resolve) => setImmediate(resolve));
    }

    await client.awaitPendingTraceBatches();

    const wallEnd = performance.now();
    clearInterval(monitor);

    lags.sort((a, b) => a - b);
    createTimes.sort((a, b) => a - b);
    updateTimes.sort((a, b) => a - b);
    const percentile = (values: number[], p: number) =>
      values.length === 0
        ? 0
        : values[Math.min(values.length - 1, Math.floor(values.length * p))];

    const stats = (values: number[]) => ({
      total: values.reduce((a, b) => a + b, 0),
      max: values.length ? values[values.length - 1] : 0,
      p50: percentile(values, 0.5),
      p95: percentile(values, 0.95),
      p99: percentile(values, 0.99),
    });

    const createStats = stats(createTimes);
    const updateStats = stats(updateTimes);
    const lagStats = stats(lags);

    const fmt = (n: number) => n.toFixed(2).padStart(9);
    const humanReadable = [
      ``,
      `=== Event loop benchmark ===`,
      `Runs traced:                 ${NUM_RUNS}`,
      `Per-run create payload:      ${(inputJsonSize / 1024).toFixed(1)} KB`,
      `Per-run update payload:      ${(outputJsonSize / 1024).toFixed(1)} KB`,
      `Wall time (incl. drain):     ${(wallEnd - wallStart).toFixed(1)} ms`,
      ``,
      `                 total       max       p50       p95       p99`,
      `createRun   ${fmt(createStats.total)} ${fmt(createStats.max)} ${fmt(
        createStats.p50
      )} ${fmt(createStats.p95)} ${fmt(createStats.p99)}`,
      `updateRun   ${fmt(updateStats.total)} ${fmt(updateStats.max)} ${fmt(
        updateStats.p50
      )} ${fmt(updateStats.p95)} ${fmt(updateStats.p99)}`,
      `loop lag    ${fmt(lagStats.total)} ${fmt(lagStats.max)} ${fmt(
        lagStats.p50
      )} ${fmt(lagStats.p95)} ${fmt(lagStats.p99)}`,
      `(loop lag monitor: ${targetInterval}ms target, ${lags.length} samples > 0)`,
    ].join("\n");

    // Machine-readable payload. The js-perf CI workflow greps for the
    // sentinel, parses the JSON, and posts a comparison comment on the PR.
    const machineReadable = JSON.stringify({
      runs: NUM_RUNS,
      inputBytes: inputJsonSize,
      outputBytes: outputJsonSize,
      wallMs: wallEnd - wallStart,
      createRun: createStats,
      updateRun: updateStats,
      loopLag: { ...lagStats, samples: lags.length },
    });

    console.log(humanReadable);
    console.log(`<<PERF_BENCH_JSON>>${machineReadable}<<END_PERF_BENCH_JSON>>`);
  },
  120_000
);
