/* eslint-disable no-process-env, no-instanceof/no-instanceof */
import { traceable } from "../traceable.js";
import { Client } from "../client.js";
import { v7 as uuidv7 } from "uuid";

import * as fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

test.skip("Test performance with large runs and concurrency", async () => {
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
 * The hot-path size estimation optimization is opt-in via
 * LANGSMITH_PERF_OPTIMIZATION=true. Running the benchmark with and
 * without that flag shows the before/after impact on the real public API
 * path, not just the internal queue.
 *
 * Example (run both to compare):
 *   # Default behavior (serialize on hot path)
 *   LANGSMITH_TRACING=false pnpm test:integration src/tests/perf.int.test.ts \
 *     -t "benchmark event loop"
 *
 *   # With opt-in optimization (estimator)
 *   LANGSMITH_PERF_OPTIMIZATION=true LANGSMITH_TRACING=false \
 *     pnpm test:integration src/tests/perf.int.test.ts -t "benchmark event loop"
 */
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
    const workerEnv = process.env.LANGSMITH_PERF_OPTIMIZATION === "true";
    const mode = workerEnv
      ? "PERF (estimator on hot path + worker-thread serialize at flush)"
      : "DEFAULT (serialize on hot path + main-thread serialize at flush)";

    console.log(`\n=== Event loop benchmark ===`);
    console.log(`Mode: ${mode}`);
    console.log(
      `Per-run create payload size: ${(inputJsonSize / 1024).toFixed(1)} KB`
    );
    console.log(
      `Per-run update payload size: ${(outputJsonSize / 1024).toFixed(1)} KB`
    );

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
    const percentile = (values: number[], p: number) =>
      values.length === 0
        ? 0
        : values[Math.min(values.length - 1, Math.floor(values.length * p))];
    const totalLag = lags.reduce((a, b) => a + b, 0);
    const maxLag = lags.length ? lags[lags.length - 1] : 0;

    createTimes.sort((a, b) => a - b);
    updateTimes.sort((a, b) => a - b);
    const createTotal = createTimes.reduce((a, b) => a + b, 0);
    const updateTotal = updateTimes.reduce((a, b) => a + b, 0);
    const createMax = createTimes.length
      ? createTimes[createTimes.length - 1]
      : 0;
    const updateMax = updateTimes.length
      ? updateTimes[updateTimes.length - 1]
      : 0;

    console.log(`\nRuns traced: ${NUM_RUNS}`);
    console.log(
      `Wall time (including batch drain): ${(wallEnd - wallStart).toFixed(1)}ms`
    );
    console.log(`\ncreateRun sync time (ms):`);
    console.log(`  total:       ${createTotal.toFixed(2)}ms`);
    console.log(`  max:         ${createMax.toFixed(2)}ms`);
    console.log(`  p50:         ${percentile(createTimes, 0.5).toFixed(2)}ms`);
    console.log(`  p95:         ${percentile(createTimes, 0.95).toFixed(2)}ms`);
    console.log(`  p99:         ${percentile(createTimes, 0.99).toFixed(2)}ms`);
    console.log(`\nupdateRun sync time (ms):`);
    console.log(`  total:       ${updateTotal.toFixed(2)}ms`);
    console.log(`  max:         ${updateMax.toFixed(2)}ms`);
    console.log(`  p50:         ${percentile(updateTimes, 0.5).toFixed(2)}ms`);
    console.log(`  p95:         ${percentile(updateTimes, 0.95).toFixed(2)}ms`);
    console.log(`  p99:         ${percentile(updateTimes, 0.99).toFixed(2)}ms`);
    console.log(
      `\nEvent loop lag (setInterval monitor, ${targetInterval}ms target):`
    );
    console.log(`  samples > 0: ${lags.length}`);
    console.log(`  total:       ${totalLag.toFixed(2)}ms`);
    console.log(`  max:         ${maxLag.toFixed(2)}ms`);
    console.log(`  p50:         ${percentile(lags, 0.5).toFixed(2)}ms`);
    console.log(`  p95:         ${percentile(lags, 0.95).toFixed(2)}ms`);
    console.log(`  p99:         ${percentile(lags, 0.99).toFixed(2)}ms`);
  },
  120_000
);
