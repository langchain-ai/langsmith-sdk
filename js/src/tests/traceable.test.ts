import type { RunTree } from "../run_trees.js";
import { ROOT, traceable } from "../traceable.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { mockClient } from "./utils/mock_client.js";

test("basic traceable implementation", async () => {
  const { client, callSpy } = mockClient();
  const llm = traceable(
    async function* llm(input: string) {
      const response = input.repeat(2).split("");
      for (const char of response) {
        yield char;
      }
    },
    { client, tracingEnabled: true }
  );

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of llm("Hello world")) {
    // pass
  }

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["llm:0"],
    edges: [],
  });
});

test("nested traceable implementation", async () => {
  const { client, callSpy } = mockClient();

  const llm = traceable(async function llm(input: string) {
    return input.repeat(2);
  });

  const str = traceable(async function* str(input: string) {
    const response = input.split("").reverse();
    for (const char of response) {
      yield char;
    }
  });

  const chain = traceable(
    async function chain(input: string) {
      const question = await llm(input);

      let answer = "";
      for await (const char of str(question)) {
        answer += char;
      }

      return { question, answer };
    },
    { client, tracingEnabled: true }
  );

  const result = await chain("Hello world");

  expect(result).toEqual({
    question: "Hello worldHello world",
    answer: "dlrow olleHdlrow olleH",
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["chain:0", "llm:1", "str:2"],
    edges: [
      ["chain:0", "llm:1"],
      ["chain:0", "str:2"],
    ],
  });
});

test("passing run tree manually", async () => {
  const { client, callSpy } = mockClient();
  const child = traceable(
    async (runTree: RunTree, depth = 0): Promise<number> => {
      if (depth < 2) {
        return child(runTree, depth + 1);
      }
      return 3;
    },
    { name: "child" }
  );

  const parent = traceable(
    async function parent(runTree: RunTree) {
      const first = await child(runTree);
      const second = await child(runTree);

      return first + second;
    },
    { client, tracingEnabled: true }
  );

  await parent(ROOT);

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: [
      "parent:0",
      "child:1",
      "child:2",
      "child:3",
      "child:4",
      "child:5",
      "child:6",
    ],
    edges: [
      ["parent:0", "child:1"],
      ["child:1", "child:2"],
      ["child:2", "child:3"],
      ["parent:0", "child:4"],
      ["child:4", "child:5"],
      ["child:5", "child:6"],
    ],
  });
});

test("async generators", async () => {
  const { client, callSpy } = mockClient();

  const iterableTraceable = traceable(
    async function* giveMeNumbers() {
      for (let i = 0; i < 5; i++) {
        yield i;
      }
    },
    { client, tracingEnabled: true }
  );

  const numbers: number[] = [];
  for await (const num of iterableTraceable()) {
    numbers.push(num);
  }

  expect(numbers).toEqual([0, 1, 2, 3, 4]);
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["giveMeNumbers:0"],
    edges: [],
  });
});

test("async generators error", async () => {
  const { client, callSpy } = mockClient();
  const throwTraceable = traceable(
    async function* () {
      for (let i = 0; i < 5; i++) {
        yield i;
        if (i == 2) throw new Error("I am bad");
      }
    },
    { name: "throwTraceable", client, tracingEnabled: true }
  );

  await expect(async () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of throwTraceable()) {
      // pass
    }
  }).rejects.toThrow("I am bad");

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["throwTraceable:0"],
    edges: [],
    data: {
      "throwTraceable:0": {
        error: "Error: I am bad",
        outputs: { outputs: [0, 1, 2] },
      },
    },
  });
});

test("async generator break", async () => {
  const { client, callSpy } = mockClient();
  const iterableTraceable = traceable(
    async function* giveMeNumbers() {
      for (let i = 0; i < 5; i++) {
        yield i;
      }
    },
    { client, tracingEnabled: true }
  );

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of iterableTraceable()) {
    break;
  }

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["giveMeNumbers:0"],
    edges: [],
    data: {
      "giveMeNumbers:0": {
        outputs: { outputs: [0] },
        error: "Cancelled",
      },
    },
  });
});


