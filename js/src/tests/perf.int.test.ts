/* eslint-disable no-process-env, no-instanceof/no-instanceof */
import { traceable } from "../traceable.js";
import { Client } from "../client.js";
import { v7 as uuidv7 } from "../utils/uuid/src/index.js";

import * as fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

test("Test performance with large runs and concurrency", async () => {
  const pathname = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "test_data",
    "beemovie.txt",
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
    },
  );

  await Promise.all(
    Array.from({ length: 1000 }, async () => {
      await largeTest(largeInput);
    }),
  );

  await client.awaitPendingTraceBatches();
});

/**
 * Benchmarks event-loop blocking caused by tracing large payloads.
 *
 * Two payload shapes are measured:
 *   1. Large-string ("base64"): payload dominated by a few multi-hundred-KB
 *      strings. This is the shape the worker-offload path is optimized for.
 *   2. Structural: payload whose bulk is many small strings across a wide /
 *      nested object graph. `hasLargeString` should return false here and
 *      the client should fall back to synchronous serialize at flush. This
 *      bench protects against regressions in that non-offloaded path.
 *
 * Each bench writes its machine-readable results to a JSON file under
 * `$LANGSMITH_PERF_BENCH_DIR` (defaults to the repo-local `js/` directory).
 * The js-perf CI workflow reads those files from both `main` and PR HEAD
 * and posts a comparison comment.
 *
 * Benchmarks are skipped by default and run only when
 * LANGSMITH_RUN_PERF_BENCH=true.
 *
 * Manual run:
 *   LANGSMITH_RUN_PERF_BENCH=true LANGSMITH_TRACING=false \
 *     pnpm test:integration src/tests/perf.int.test.ts -t "benchmark"
 */
// Default the perf optimization on for benchmark runs so results reflect
// the shipped perf behavior. Respect an explicit override from the invoker
// so `LANGSMITH_PERF_OPTIMIZATION=false` can be used to measure the
// unoptimized baseline for comparison.
if (process.env.LANGSMITH_PERF_OPTIMIZATION === undefined) {
  process.env.LANGSMITH_PERF_OPTIMIZATION = "true";
}

// Enabled by setting LANGSMITH_RUN_PERF_BENCH=true. Skipped in CI by default.
const benchIt =
  process.env.LANGSMITH_RUN_PERF_BENCH === "true" ? test : test.skip;

interface BenchStats {
  total: number;
  max: number;
  p50: number;
  p95: number;
  p99: number;
}

interface BenchResult {
  name: string;
  runs: number;
  inputBytes: number;
  outputBytes: number;
  wallMs: number;
  createRun: BenchStats;
  updateRun: BenchStats;
  loopLag: BenchStats & { samples: number };
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  return values[Math.min(values.length - 1, Math.floor(values.length * p))];
}

function stats(values: number[]): BenchStats {
  return {
    total: values.reduce((a, b) => a + b, 0),
    max: values.length ? values[values.length - 1] : 0,
    p50: percentile(values, 0.5),
    p95: percentile(values, 0.95),
    p99: percentile(values, 0.99),
  };
}

function benchOutputPath(filename: string): string {
  const dir = process.env.LANGSMITH_PERF_BENCH_DIR ?? process.cwd();
  return path.join(dir, filename);
}

// Shared mock fetch: /info returns a batch-ingest config; everything else
// returns an empty 202. Keeps the bench end-to-end without hitting network.
const benchFetch: typeof fetch = async (input) => {
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
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
  return new Response(JSON.stringify({ ok: true }), {
    status: 202,
    headers: { "content-type": "application/json" },
  });
};

async function runBench(opts: {
  name: string;
  inputs: unknown;
  outputs: unknown;
  numRuns: number;
  outFile: string;
}): Promise<BenchResult> {
  const { name, inputs, outputs, numRuns, outFile } = opts;
  const inputJsonSize = JSON.stringify(inputs).length;
  const outputJsonSize = JSON.stringify(outputs).length;

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

  const client = new Client({
    autoBatchTracing: true,
    fetchImplementation: benchFetch,
    fetchOptions: { signal: AbortSignal.timeout(30_000) },
  });

  const createTimes: number[] = [];
  const updateTimes: number[] = [];
  const wallStart = performance.now();

  for (let i = 0; i < numRuns; i++) {
    const runId = uuidv7();

    const createStart = performance.now();
    await client.createRun({
      id: runId,
      trace_id: runId,
      dotted_order: `${new Date().toISOString()}${runId}`,
      name: "bench_run",
      run_type: "llm",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      inputs: inputs as any,
      start_time: Date.now(),
    });
    createTimes.push(performance.now() - createStart);

    await new Promise((resolve) => setImmediate(resolve));

    const updateStart = performance.now();
    await client.updateRun(runId, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      outputs: outputs as any,
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

  const createStats = stats(createTimes);
  const updateStats = stats(updateTimes);
  const lagStats = stats(lags);
  const result: BenchResult = {
    name,
    runs: numRuns,
    inputBytes: inputJsonSize,
    outputBytes: outputJsonSize,
    wallMs: wallEnd - wallStart,
    createRun: createStats,
    updateRun: updateStats,
    loopLag: { ...lagStats, samples: lags.length },
  };

  const fmt = (n: number) => n.toFixed(2).padStart(9);
  const humanReadable = [
    ``,
    `=== Event loop benchmark: ${name} ===`,
    `Runs traced:                 ${numRuns}`,
    `Per-run create payload:      ${(inputJsonSize / 1024).toFixed(1)} KB`,
    `Per-run update payload:      ${(outputJsonSize / 1024).toFixed(1)} KB`,
    `Wall time (incl. drain):     ${(wallEnd - wallStart).toFixed(1)} ms`,
    ``,
    `                 total       max       p50       p95       p99`,
    `createRun   ${fmt(createStats.total)} ${fmt(createStats.max)} ${fmt(
      createStats.p50,
    )} ${fmt(createStats.p95)} ${fmt(createStats.p99)}`,
    `updateRun   ${fmt(updateStats.total)} ${fmt(updateStats.max)} ${fmt(
      updateStats.p50,
    )} ${fmt(updateStats.p95)} ${fmt(updateStats.p99)}`,
    `loop lag    ${fmt(lagStats.total)} ${fmt(lagStats.max)} ${fmt(
      lagStats.p50,
    )} ${fmt(lagStats.p95)} ${fmt(lagStats.p99)}`,
    `(loop lag monitor: ${targetInterval}ms target, ${lags.length} samples > 0)`,
  ].join("\n");
  console.log(humanReadable);

  fs.writeFileSync(benchOutputPath(outFile), JSON.stringify(result, null, 2));
  return result;
}

benchIt(
  "benchmark event loop blocking from tracing large base64-heavy payloads",
  async () => {
    const pathname = path.join(
      path.dirname(fileURLToPath(import.meta.url)),
      "test_data",
      "beemovie.txt",
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
      Math.ceil((500 * 1024) / base64Chunk.length),
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

    await runBench({
      name: "base64",
      inputs: largeInputs,
      outputs: largeOutputs,
      numRuns: 100,
      outFile: "bench-base64.json",
    });
  },
  120_000,
);

benchIt(
  "benchmark event loop blocking from tracing structural large payloads",
  async () => {
    // Structural-large payload: large total JSON size, but made up of many
    // small-to-medium strings across a wide/nested object graph. No single
    // string exceeds the worker-offload threshold, so this exercises the
    // *non-offloaded* flush path (sync serialize on the main thread) even
    // when LANGSMITH_PERF_OPTIMIZATION is on. Guards against regressions in
    // the fallback path and confirms hasLargeString correctly filters this
    // shape out.
    const NUM_MESSAGES = 200;
    const PER_MESSAGE_CHARS = 6_000; // well below the 64KB worker threshold

    // Distinct-ish content per message so V8 can't aggressively dedupe.
    const makeText = (seed: number, chars: number) => {
      const base = `msg-${seed} ` + "lorem ipsum dolor sit amet ".repeat(40);
      return base.repeat(Math.ceil(chars / base.length)).slice(0, chars);
    };

    const structuralInputs = {
      messages: Array.from({ length: NUM_MESSAGES }, (_, i) => ({
        role: i % 2 === 0 ? "user" : "assistant",
        name: `speaker_${i}`,
        timestamp: new Date(
          Date.now() - (NUM_MESSAGES - i) * 1000,
        ).toISOString(),
        metadata: {
          turn: i,
          tokens: 200 + (i % 50),
          tags: [`tag-${i % 7}`, `tag-${i % 11}`, `tag-${i % 13}`],
          nested: {
            score: (i * 0.017) % 1,
            flags: { a: i % 2 === 0, b: i % 3 === 0, c: i % 5 === 0 },
          },
        },
        content: makeText(i, PER_MESSAGE_CHARS),
      })),
      tools: Array.from({ length: 20 }, (_, i) => ({
        name: `tool_${i}`,
        description: makeText(10000 + i, 400),
        parameters: {
          type: "object",
          properties: Object.fromEntries(
            Array.from({ length: 8 }, (_, j) => [
              `param_${j}`,
              {
                type: j % 2 === 0 ? "string" : "number",
                description: `description of param ${j} for tool ${i}`,
              },
            ]),
          ),
        },
      })),
      model: "gpt-4o",
      temperature: 0.7,
    };

    const structuralOutputs = {
      choices: [
        {
          message: {
            role: "assistant",
            content: makeText(999999, 8_000),
            tool_calls: Array.from({ length: 10 }, (_, i) => ({
              id: `call_${i}`,
              type: "function",
              function: {
                name: `tool_${i}`,
                arguments: JSON.stringify({
                  query: makeText(20000 + i, 400),
                  filters: { k1: `v${i}`, k2: i, k3: i % 2 === 0 },
                }),
              },
            })),
          },
          finish_reason: "stop",
        },
      ],
      usage: { prompt_tokens: 120000, completion_tokens: 48000 },
    };

    await runBench({
      name: "structural",
      inputs: structuralInputs,
      outputs: structuralOutputs,
      numRuns: 100,
      outFile: "bench-structural.json",
    });
  },
  120_000,
);
