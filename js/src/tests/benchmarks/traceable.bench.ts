/**
 * Benchmarks for `traceable`.
 *
 * `traceable` wraps user functions directly, so its wrapper cost (AsyncLocalStorage
 * bookkeeping, input/output extraction, run creation) is paid on every call of
 * every instrumented function.
 */
import { bench, describe } from "vitest";

import { traceable } from "../../traceable.js";
import { benchClient } from "./utils.js";

const client = benchClient();

const plain = (a: number, b: number, c: string) => ({ result: a + b, c });

const traced = traceable(plain, { client, tracingEnabled: true });
const untraced = traceable(plain, { client, tracingEnabled: false });

const tracedChild = traceable((i: number) => i * 2, {
  client,
  tracingEnabled: true,
  name: "child",
});

const tracedParent = traceable(
  async (n: number) => {
    let total = 0;
    for (let i = 0; i < n; i += 1) {
      total += await tracedChild(i);
    }
    return total;
  },
  { client, tracingEnabled: true, name: "parent" },
);

describe("traceable", () => {
  bench("baseline (undecorated) x20", () => {
    for (let i = 0; i < 20; i += 1) {
      plain(1, 2, "hello");
    }
  });

  bench("traced call x20", async () => {
    for (let i = 0; i < 20; i += 1) {
      await traced(1, 2, "hello");
    }
  });

  bench("traced call, tracing disabled x20", async () => {
    for (let i = 0; i < 20; i += 1) {
      await untraced(1, 2, "hello");
    }
  });

  bench("nested traced calls", async () => {
    await tracedParent(10);
  });
});
