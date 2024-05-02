import type { ROOT as TRoot } from "../traceable.js";
import type { RunTree } from "../run_trees.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { mockClient } from "./utils/mock_client.js";

test("basic traceable implementation", async () => {
  const { client, callSpy } = mockClient();
  const { traceable } = await import("../traceable.js");

  const llm = traceable(
    async function* llm(input: string) {
      const response = input.repeat(2).split("");
      for (const char of response) {
        yield char;
      }
    },
    { client }
  );

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of llm("Hello world")) {
    // pass
  }

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toEqual({
    nodes: ["llm:0"],
    edges: [],
  });
});

test("nested traceable implementation", async () => {
  const { client, callSpy } = mockClient();
  const { traceable } = await import("../traceable.js");

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
    { client }
  );

  const result = await chain("Hello world");

  expect(result).toEqual({
    question: "Hello worldHello world",
    answer: "dlrow olleHdlrow olleH",
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toEqual({
    nodes: ["chain:0", "llm:1", "str:2"],
    edges: [
      ["chain:0", "llm:1"],
      ["chain:0", "str:2"],
    ],
  });
});

test("passing run tree manually", async () => {
  const { client, callSpy } = mockClient();
  const { traceable, ROOT } = await import("../traceable.js");

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
    { client }
  );

  await parent(ROOT as typeof TRoot);

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toEqual({
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
