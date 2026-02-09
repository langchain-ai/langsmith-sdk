import { __private } from "../evaluation/_runner.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function* fromArray<T>(items: T[]): AsyncGenerator<T> {
  for (const item of items) {
    yield item;
  }
}

async function collect<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const results: T[] = [];
  for await (const item of iterable) {
    results.push(item);
  }
  return results;
}

describe("evaluation runner internals", () => {
  test("mapWithConcurrency runs sequentially when maxConcurrency <= 0", async () => {
    let active = 0;
    let maxActive = 0;
    const output = await collect(
      __private.mapWithConcurrency(fromArray([1, 2, 3]), 0, async (value) => {
        active += 1;
        maxActive = Math.max(maxActive, active);
        await sleep(10);
        active -= 1;
        return value;
      })
    );

    expect(output).toEqual([1, 2, 3]);
    expect(maxActive).toBe(1);
  });

  test("mapWithConcurrency yields by completion order and honors concurrency", async () => {
    let active = 0;
    let maxActive = 0;
    const delays: Record<number, number> = {
      1: 30,
      2: 5,
      3: 10,
    };

    const output = await collect(
      __private.mapWithConcurrency(fromArray([1, 2, 3]), 2, async (value) => {
        active += 1;
        maxActive = Math.max(maxActive, active);
        await sleep(delays[value]);
        active -= 1;
        return value;
      })
    );

    expect(output).toEqual([2, 3, 1]);
    expect(maxActive).toBeLessThanOrEqual(2);
    expect(maxActive).toBe(2);
  });

  test("mapWithConcurrency propagates mapper errors", async () => {
    await expect(
      collect(
        __private.mapWithConcurrency(fromArray([1, 2, 3]), 2, async (value) => {
          if (value === 2) {
            throw new Error("mapper boom");
          }
          await sleep(1);
          return value;
        })
      )
    ).rejects.toThrow("mapper boom");
  });

  test("mapWithConcurrency propagates source iterable errors", async () => {
    async function* source(): AsyncGenerator<number> {
      yield 1;
      throw new Error("source boom");
    }

    await expect(
      collect(__private.mapWithConcurrency(source(), 2, async (value) => value))
    ).rejects.toThrow("source boom");
  });

  test("reorderResultRowsByExampleIndex restores original example order", () => {
    const inputRows = [
      {
        exampleIndex: 2,
        run: { id: "run-2" },
        example: { id: "example-2" },
        evaluationResults: { results: [{ key: "key-2" }] },
      },
      {
        exampleIndex: 0,
        run: { id: "run-0" },
        example: { id: "example-0" },
        evaluationResults: { results: [{ key: "key-0" }] },
      },
      {
        exampleIndex: 1,
        run: { id: "run-1" },
        example: { id: "example-1" },
        evaluationResults: { results: [{ key: "key-1" }] },
      },
    ] as unknown as Parameters<
      typeof __private.reorderResultRowsByExampleIndex
    >[0];

    const { orderedRows, orderedRuns } =
      __private.reorderResultRowsByExampleIndex(inputRows);

    expect(orderedRows.map((row) => row.example.id)).toEqual([
      "example-0",
      "example-1",
      "example-2",
    ]);
    expect(
      orderedRows.map((row) => row.evaluationResults.results[0].key)
    ).toEqual(["key-0", "key-1", "key-2"]);
    expect(orderedRuns.map((run) => run.id)).toEqual([
      "run-0",
      "run-1",
      "run-2",
    ]);
    expect(inputRows.map((row) => row.exampleIndex)).toEqual([2, 0, 1]);
  });

  test("reorderResultRowsByExampleIndex keeps stable order for ties", () => {
    const inputRows = [
      {
        exampleIndex: 1,
        run: { id: "run-a" },
        example: { id: "example-a" },
        evaluationResults: { results: [] },
      },
      {
        exampleIndex: 1,
        run: { id: "run-b" },
        example: { id: "example-b" },
        evaluationResults: { results: [] },
      },
      {
        exampleIndex: 0,
        run: { id: "run-c" },
        example: { id: "example-c" },
        evaluationResults: { results: [] },
      },
    ] as unknown as Parameters<
      typeof __private.reorderResultRowsByExampleIndex
    >[0];

    const { orderedRuns } =
      __private.reorderResultRowsByExampleIndex(inputRows);
    expect(orderedRuns.map((run) => run.id)).toEqual([
      "run-c",
      "run-a",
      "run-b",
    ]);
  });
});
