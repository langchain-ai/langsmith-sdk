import { jest } from "@jest/globals";
import type { ROOT as TRoot } from "../traceable.js";
import type { RunTree } from "../run_trees.js";

const mockCounter = jest.fn();

const treeState: {
  nodes: string[];
  edges: [string, string][];
} = { nodes: [], edges: [] };

const mockEnd = jest.fn();
const mockTree = jest.fn().mockImplementation((...args) => {
  mockCounter();
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-expect-error
  const name = args.at(0)?.name as string | undefined;
  const id = name + ":" + mockCounter.mock.calls.length;
  treeState.nodes.push(id);

  const lastArg = args.at(-1);
  if (typeof lastArg === "string") {
    treeState.edges.push([lastArg, id]);
  }

  return {
    createChild: (...args: unknown[]) => mockTree(...args, id),
    end: (...args: unknown[]) => mockEnd(...args, id),
    postRun: jest.fn(),
    patchRun: jest.fn(),
  };
});

jest.unstable_mockModule("../run_trees.js", () => {
  return {
    RunTree: mockTree,
    isRunTree: (x: unknown) =>
      x !== undefined &&
      typeof (x as RunTree).createChild === "function" &&
      typeof (x as RunTree).postRun === "function",
    isRunnableConfigLike: jest.fn().mockReturnValue(false),
  };
});

beforeEach(() => {
  jest.clearAllMocks();
  treeState.nodes = [];
  treeState.edges = [];
});

test("basic traceable implementation", async () => {
  const { traceable } = await import("../traceable.js");

  const llm = traceable(async function* llm(input: string) {
    const response = input.repeat(2).split("");
    for (const char of response) {
      yield char;
    }
  });

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of llm("Hello world")) {
    // pass
  }

  mockCounter.mock;

  expect(mockTree).toBeCalledTimes(1);
  expect(mockTree).toBeCalledWith({ name: "llm", tags: [], metadata: {} });
});

test("nested traceable implementation", async () => {
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

  const chain = traceable(async function chain(input: string) {
    const question = await llm(input);

    let answer = "";
    for await (const char of str(question)) {
      answer += char;
    }

    return { question, answer };
  });

  const result = await chain("Hello world");

  expect(result).toEqual({
    question: "Hello worldHello world",
    answer: "dlrow olleHdlrow olleH",
  });

  expect(mockTree).toBeCalledTimes(3);
  expect(mockTree).toBeCalledWith({ name: "chain", tags: [], metadata: {} });
  expect(mockTree).toBeCalledWith(
    { name: "llm", tags: [], metadata: {} },
    "chain:1"
  );
  expect(mockTree).toBeCalledWith(
    { name: "str", tags: [], metadata: {} },
    "chain:1"
  );
});

test("passing run tree manually", async () => {
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

  const parent = traceable(async function parent(runTree: RunTree) {
    const first = await child(runTree);
    const second = await child(runTree);

    return first + second;
  });

  await parent(ROOT as typeof TRoot);
  expect(mockTree).toBeCalledTimes(7);
  expect(treeState.edges).toEqual([
    ["parent:1", "child:2"],
    ["child:2", "child:3"],
    ["child:3", "child:4"],
    ["parent:1", "child:5"],
    ["child:5", "child:6"],
    ["child:6", "child:7"],
  ]);
});
