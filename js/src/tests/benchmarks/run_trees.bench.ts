/**
 * Benchmarks for `RunTree`.
 *
 * `RunTree` is created for every span: it derives ids, dotted orders and
 * inherited metadata, then serializes and ships the run through the client.
 */
import { bench, describe } from "vitest";

import { RunTree, convertToDottedOrderFormat } from "../../run_trees.js";
import { uuid7 } from "../../uuid.js";
import { benchClient, largeArrayPayload } from "./utils.js";

const client = benchClient();

function buildTree(depth: number, width: number): RunTree {
  const root = new RunTree({
    name: "root",
    client,
    tracingEnabled: true,
    inputs: { question: "hello" },
  });
  let frontier = [root];
  for (let level = 0; level < depth; level += 1) {
    const next: RunTree[] = [];
    for (const parent of frontier) {
      for (let i = 0; i < width; i += 1) {
        next.push(
          parent.createChild({
            name: `child_${level}_${i}`,
            run_type: "llm",
            inputs: { prompt: "hello world" },
          }),
        );
      }
    }
    frontier = next;
  }
  return root;
}

describe("RunTree", () => {
  bench("create 100 root run trees", () => {
    for (let i = 0; i < 100; i += 1) {
      // eslint-disable-next-line no-new
      new RunTree({ name: `run-${i}`, client, tracingEnabled: true });
    }
  });

  bench("build nested tree (3x4)", () => {
    buildTree(3, 4);
  });

  bench("post nested tree (2x5)", async () => {
    const root = buildTree(2, 5);
    await root.postRun(false);
  });

  bench("post and patch a large run", async () => {
    const run = new RunTree({
      name: "large-run",
      client,
      tracingEnabled: true,
      inputs: largeArrayPayload(200),
    });
    await run.postRun();
    await run.end(largeArrayPayload(200));
    await run.patchRun();
  });
});

describe("dotted order", () => {
  const ids = Array.from({ length: 500 }, () => uuid7());

  bench("convertToDottedOrderFormat x500", () => {
    for (let i = 0; i < ids.length; i += 1) {
      convertToDottedOrderFormat(1620000000000 + i, ids[i], i + 1);
    }
  });

  bench("uuid7 x500", () => {
    for (let i = 0; i < 500; i += 1) {
      uuid7();
    }
  });
});
