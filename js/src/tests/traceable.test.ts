/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { _LC_CONTEXT_VARIABLES_KEY } from "../singletons/constants.js";
import {
  ROOT,
  traceable,
  withRunTree,
  isTraceableFunction,
} from "../traceable.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { mockClient } from "./utils/mock_client.js";
import { Client, overrideFetchImplementation } from "../index.js";
import {
  AsyncLocalStorageProviderSingleton,
  getCurrentRunTree,
} from "../singletons/traceable.js";
import { KVMap } from "../schemas.js";

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

test("404s should only log, not throw an error", async () => {
  const overriddenFetch = jest.fn(() =>
    Promise.resolve({
      ok: false,
      status: 404,
      statusText: "Expected test error",
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("Expected test error."),
    })
  );
  overrideFetchImplementation(overriddenFetch);
  const client = new Client({
    apiUrl: "https://foobar.notreal",
    autoBatchTracing: false,
  });
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
  expect(overriddenFetch).toHaveBeenCalled();
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

test("nested traceable passes through LangChain context vars", (done) => {
  const alsInstance = AsyncLocalStorageProviderSingleton.getInstance();

  alsInstance.run(
    {
      [_LC_CONTEXT_VARIABLES_KEY]: { foo: "bar" },
    } as any,
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    async () => {
      try {
        expect(
          (alsInstance.getStore() as any)?.[_LC_CONTEXT_VARIABLES_KEY]?.foo
        ).toEqual("bar");
        const { client, callSpy } = mockClient();

        const llm = traceable(async function llm(input: string) {
          expect(
            (alsInstance.getStore() as any)?.[_LC_CONTEXT_VARIABLES_KEY]?.foo
          ).toEqual("bar");
          return input.repeat(2);
        });

        const str = traceable(async function* str(input: string) {
          const response = input.split("").reverse();
          for (const char of response) {
            yield char;
          }
          expect(
            (alsInstance.getStore() as any)?.[_LC_CONTEXT_VARIABLES_KEY]?.foo
          ).toEqual("bar");
        });

        const chain = traceable(
          async function chain(input: string) {
            expect(
              (alsInstance.getStore() as any)?.[_LC_CONTEXT_VARIABLES_KEY]?.foo
            ).toEqual("bar");
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
        expect(
          (alsInstance.getStore() as any)?.[_LC_CONTEXT_VARIABLES_KEY]?.foo
        ).toEqual("bar");
        done();
      } catch (e) {
        done(e);
      }
    }
  );
});

test("trace circular input and output objects", async () => {
  const { client, callSpy } = mockClient();
  const a: Record<string, any> = {};
  const b: Record<string, any> = {};
  a.b = b;
  b.a = a;
  const llm = traceable(
    async function foo(_: Record<string, any>) {
      return a;
    },
    { client, tracingEnabled: true }
  );

  const input = {
    a,
    a2: a,
    normalParam: {
      test: true,
    },
  };
  await llm(input);

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["foo:0"],
    edges: [],
    data: {
      "foo:0": {
        inputs: {
          a: {
            b: {
              a: {
                result: "[Circular]",
              },
            },
          },
          a2: {
            b: {
              a: {
                result: "[Circular]",
              },
            },
          },
          normalParam: {
            test: true,
          },
        },
        outputs: {
          b: {
            a: {
              b: {
                result: "[Circular]",
              },
            },
          },
        },
      },
    },
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

describe("distributed tracing", () => {
  it("default", async () => {
    const { client, callSpy } = mockClient();
    const child = traceable(
      async (depth = 0): Promise<number> => {
        if (depth < 2) return child(depth + 1);
        return 3;
      },
      { name: "child" }
    );

    const parent = traceable(async function parent() {
      const first = await child();
      const second = await child();
      return first + second;
    });

    const clientRunTree = new RunTree({
      name: "client",
      client,
      tracingEnabled: true,
    });
    await clientRunTree.postRun();

    // do nothing with the client run tree

    await clientRunTree.patchRun();

    const response = await withRunTree(clientRunTree, () => parent());
    expect(response).toBe(6);

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: [
        "client:0",
        "parent:1",
        "child:2",
        "child:3",
        "child:4",
        "child:5",
        "child:6",
        "child:7",
      ],
      edges: [
        ["client:0", "parent:1"],
        ["parent:1", "child:2"],
        ["child:2", "child:3"],
        ["child:3", "child:4"],
        ["parent:1", "child:5"],
        ["child:5", "child:6"],
        ["child:6", "child:7"],
      ],
    });
  });

  it("sync function", async () => {
    const { client, callSpy } = mockClient();
    const child = traceable(
      async (depth = 0): Promise<number> => {
        if (depth < 2) return child(depth + 1);
        return 3;
      },
      { name: "child" }
    );

    const parent = traceable(async function parent() {
      const first = await child();
      const second = await child();
      return first + second;
    });

    const clientRunTree = new RunTree({
      name: "client",
      client,
      tracingEnabled: true,
    });
    await clientRunTree.postRun();
    await clientRunTree.patchRun();

    let promiseOutside: Promise<unknown> = Promise.resolve();

    const response = await withRunTree(clientRunTree, () => {
      promiseOutside = parent();
    });

    expect(response).toBeUndefined();
    await promiseOutside;

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: [
        "client:0",
        "parent:1",
        "child:2",
        "child:3",
        "child:4",
        "child:5",
        "child:6",
        "child:7",
      ],
      edges: [
        ["client:0", "parent:1"],
        ["parent:1", "child:2"],
        ["child:2", "child:3"],
        ["child:3", "child:4"],
        ["parent:1", "child:5"],
        ["child:5", "child:6"],
        ["child:6", "child:7"],
      ],
    });
  });
});

describe("async generators", () => {
  test("success", async () => {
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
      data: {
        "giveMeNumbers:0": {
          outputs: { outputs: [0, 1, 2, 3, 4] },
        },
      },
    });
  });

  test("error", async () => {
    const { client, callSpy } = mockClient();
    const throwTraceable = traceable(
      async function* () {
        for (let i = 0; i < 5; i++) {
          yield i;
          if (i === 2) throw new Error("I am bad");
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

  test("break", async () => {
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

  // https://github.com/nodejs/node/issues/42237
  test("nested invocation", async () => {
    const { client, callSpy } = mockClient();
    const child = traceable(
      async function* child() {
        for (let i = 0; i < 5; i++) yield i;
      },
      { name: "child", client, tracingEnabled: true }
    );

    const parent = traceable(
      async function* parent() {
        for await (const num of child()) yield num;
        for await (const num of child()) yield 4 - num;
      },
      { name: "parent", client, tracingEnabled: true }
    );

    const numbers: number[] = [];
    for await (const num of parent()) {
      numbers.push(num);
    }

    expect(numbers).toEqual([0, 1, 2, 3, 4, 4, 3, 2, 1, 0]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parent:0", "child:1", "child:2"],
      edges: [
        ["parent:0", "child:1"],
        ["parent:0", "child:2"],
      ],
    });
  });

  test("in promise success", async () => {
    const { client, callSpy } = mockClient();
    async function giveMeGiveMeNumbers() {
      async function* giveMeNumbers() {
        for (let i = 0; i < 5; i++) {
          yield i;
        }
      }
      return giveMeNumbers();
    }

    const it = traceable(giveMeGiveMeNumbers, { client, tracingEnabled: true });

    const numbers: number[] = [];
    for await (const num of await it()) {
      numbers.push(num);
    }

    expect(numbers).toEqual([0, 1, 2, 3, 4]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["giveMeGiveMeNumbers:0"],
      edges: [],
      data: {
        "giveMeGiveMeNumbers:0": {
          outputs: { outputs: [0, 1, 2, 3, 4] },
        },
      },
    });
  });

  test("in promise error", async () => {
    const { client, callSpy } = mockClient();

    async function giveMeGiveMeNumbers() {
      async function* giveMeNumbers() {
        for (let i = 0; i < 5; i++) {
          yield i;
          if (i === 2) throw new Error("I am bad");
        }
      }
      return giveMeNumbers();
    }

    const it = traceable(giveMeGiveMeNumbers, { client, tracingEnabled: true });

    await expect(async () => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      for await (const _ of await it()) {
        // pass
      }
    }).rejects.toThrow("I am bad");

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["giveMeGiveMeNumbers:0"],
      edges: [],
      data: {
        "giveMeGiveMeNumbers:0": {
          error: "Error: I am bad",
          outputs: { outputs: [0, 1, 2] },
        },
      },
    });
  });

  test("in promise break", async () => {
    const { client, callSpy } = mockClient();

    async function giveMeGiveMeNumbers() {
      async function* giveMeNumbers() {
        for (let i = 0; i < 5; i++) {
          yield i;
        }
      }
      return giveMeNumbers();
    }

    const it = traceable(giveMeGiveMeNumbers, { client, tracingEnabled: true });

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of await it()) {
      break;
    }

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["giveMeGiveMeNumbers:0"],
      edges: [],
      data: {
        "giveMeGiveMeNumbers:0": {
          outputs: { outputs: [0] },
          error: "Cancelled",
        },
      },
    });
  });

  // https://github.com/nodejs/node/issues/42237
  test("in promise nested invocation", async () => {
    const { client, callSpy } = mockClient();
    const child = traceable(async function child() {
      async function* child() {
        for (let i = 0; i < 5; i++) yield i;
      }
      return child();
    });

    async function parent() {
      async function* parent() {
        for await (const num of await child()) yield num;
        for await (const num of await child()) yield 4 - num;
      }
      return parent();
    }

    const it = traceable(parent, { client, tracingEnabled: true });

    const numbers: number[] = [];
    for await (const num of await it()) {
      numbers.push(num);
    }

    expect(numbers).toEqual([0, 1, 2, 3, 4, 4, 3, 2, 1, 0]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parent:0", "child:1", "child:2"],
      edges: [
        ["parent:0", "child:1"],
        ["parent:0", "child:2"],
      ],
    });
  });

  test("readable stream", async () => {
    const { client, callSpy } = mockClient();

    const stream = traceable(
      async function stream() {
        const readStream = new ReadableStream({
          async pull(controller) {
            for (let i = 0; i < 5; i++) {
              controller.enqueue(i);
            }
            controller.close();
          },
        });

        return readStream;
      },
      { client, tracingEnabled: true }
    );

    const numbers: number[] = [];
    for await (const num of (await stream()) as unknown as AsyncGenerator<number>) {
      numbers.push(num);
    }

    expect(numbers).toEqual([0, 1, 2, 3, 4]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["stream:0"],
      edges: [],
      data: {
        "stream:0": {
          outputs: { outputs: [0, 1, 2, 3, 4] },
        },
      },
    });
  });

  test("iterable with props", async () => {
    const { client, callSpy } = mockClient();

    const iterableTraceable = traceable(
      function iterableWithProps() {
        return {
          *[Symbol.asyncIterator]() {
            yield 0;
          },
          prop: "value",
        };
      },
      {
        client,
        tracingEnabled: true,
      }
    );

    const numbers: number[] = [];
    const iterableWithProps = await iterableTraceable();
    for await (const num of iterableWithProps) {
      numbers.push(num);
    }

    expect(numbers).toEqual([0]);

    expect(iterableWithProps.prop).toBe("value");
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["iterableWithProps:0"],
      edges: [],
      data: {
        "iterableWithProps:0": {
          outputs: { outputs: [0] },
        },
      },
    });
  });
});

describe("deferred input", () => {
  test("generator", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function* parrotStream(input: Generator<string>) {
        for (const token of input) {
          yield token;
        }
      },
      { client, tracingEnabled: true }
    );

    const inputGenerator = function* () {
      for (const token of "Hello world".split(" ")) {
        yield token;
      }
    };

    const tokens: string[] = [];
    for await (const token of parrotStream(inputGenerator())) {
      tokens.push(token);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: ["Hello", "world"] },
          outputs: { outputs: ["Hello", "world"] },
        },
      },
    });
  });

  test("async generator", async () => {
    const { client, callSpy } = mockClient();
    const inputStream = async function* inputStream() {
      for (const token of "Hello world".split(" ")) {
        yield token;
      }
    };

    const parrotStream = traceable(
      async function* parrotStream(input: AsyncGenerator<string>) {
        for await (const token of input) {
          yield token;
        }
      },
      { client, tracingEnabled: true }
    );

    const tokens: string[] = [];
    for await (const token of parrotStream(inputStream())) {
      tokens.push(token);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: ["Hello", "world"] },
          outputs: { outputs: ["Hello", "world"] },
        },
      },
    });
  });

  test("readable stream", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function* parrotStream(input: ReadableStream<string>) {
        for await (const token of input as unknown as AsyncGenerator<string>) {
          yield token;
        }
      },
      { client, tracingEnabled: true }
    );

    const readStream = new ReadableStream({
      async start(controller) {
        for (const token of "Hello world".split(" ")) {
          controller.enqueue(token);
        }
        controller.close();
      },
    });

    const tokens: string[] = [];
    for await (const token of parrotStream(readStream)) {
      tokens.push(token);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: ["Hello", "world"] },
          outputs: { outputs: ["Hello", "world"] },
        },
      },
    });
  });

  test("readable stream reader", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function* parrotStream(input: ReadableStream<string>) {
        const reader = input.getReader();
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            yield value;
          }
        } finally {
          reader.releaseLock();
        }
      },
      { client, tracingEnabled: true }
    );

    const readStream = new ReadableStream({
      async start(controller) {
        for (const token of "Hello world".split(" ")) {
          controller.enqueue(token);
        }
        controller.close();
      },
    });

    const tokens: string[] = [];
    for await (const token of parrotStream(readStream)) {
      tokens.push(token);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: ["Hello", "world"] },
          outputs: { outputs: ["Hello", "world"] },
        },
      },
    });
  });

  test("promise", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function* parrotStream(input: Promise<string[]>) {
        // eslint-disable-next-line no-instanceof/no-instanceof
        if (!(input instanceof Promise)) {
          throw new Error("Input must be a promise");
        }

        for (const token of await input) {
          yield token;
        }
      },
      { client, tracingEnabled: true }
    );

    const tokens: string[] = [];
    for await (const token of parrotStream(
      Promise.resolve(["Hello", "world"])
    )) {
      tokens.push(token);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: ["Hello", "world"] },
          outputs: { outputs: ["Hello", "world"] },
        },
      },
    });
  });

  test("promise rejection", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function parrotStream(input: Promise<string[]>) {
        return await input;
      },
      { client, tracingEnabled: true }
    );

    await expect(async () => {
      await parrotStream(Promise.reject(new Error("Rejected!")));
    }).rejects.toThrow("Rejected!");

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: { error: {} } },
          error: "Error: Rejected!",
        },
      },
    });
  });

  test("promise rejection, callback handling", async () => {
    const { client, callSpy } = mockClient();
    const parrotStream = traceable(
      async function parrotStream(input: Promise<string[]>) {
        return input.then((value) => value);
      },
      { client, tracingEnabled: true }
    );

    await expect(async () => {
      await parrotStream(Promise.reject(new Error("Rejected!")));
    }).rejects.toThrow("Rejected!");

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["parrotStream:0"],
      edges: [],
      data: {
        "parrotStream:0": {
          inputs: { input: { error: {} } },
          error: "Error: Rejected!",
        },
      },
    });
  });
});

describe("generator", () => {
  function gatherAll(iterator: Iterator<unknown>) {
    const chunks: unknown[] = [];
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const next = iterator.next();
      chunks.push(next.value);
      if (next.done) break;
    }

    return chunks;
  }

  test("yield", async () => {
    const { client, callSpy } = mockClient();

    function* generator() {
      for (let i = 0; i < 3; ++i) yield i;
    }

    const traced = traceable(generator, { client, tracingEnabled: true });

    expect(gatherAll(await traced())).toEqual(gatherAll(generator()));
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["generator:0"],
      edges: [],
      data: {
        "generator:0": {
          outputs: { outputs: [0, 1, 2] },
        },
      },
    });
  });

  test("with return", async () => {
    const { client, callSpy } = mockClient();

    function* generator() {
      for (let i = 0; i < 3; ++i) yield i;
      return 3;
    }

    const traced = traceable(generator, { client, tracingEnabled: true });

    expect(gatherAll(await traced())).toEqual(gatherAll(generator()));
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["generator:0"],
      edges: [],
      data: { "generator:0": { outputs: { outputs: [0, 1, 2, 3] } } },
    });
  });

  test("nested", async () => {
    const { client, callSpy } = mockClient();

    function* generator() {
      function* child() {
        for (let i = 0; i < 3; ++i) yield i;
      }

      for (let i = 0; i < 2; ++i) {
        for (const num of child()) yield num;
      }

      return 3;
    }

    const traced = traceable(generator, { client, tracingEnabled: true });
    expect(gatherAll(await traced())).toEqual(gatherAll(generator()));
    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
      nodes: ["generator:0"],
      edges: [],
      data: {
        "generator:0": {
          outputs: { outputs: [0, 1, 2, 0, 1, 2, 3] },
        },
      },
    });
  });
});

test("metadata", async () => {
  const { client, callSpy } = mockClient();
  const main = traceable(async (): Promise<number> => 42, {
    client,
    name: "main",
    metadata: { customValue: "hello" },
    tracingEnabled: true,
  });

  await main();

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["main:0"],
    edges: [],
    data: {
      "main:0": {
        extra: { metadata: { customValue: "hello" } },
        outputs: { outputs: 42 },
      },
    },
  });
});

test("argsConfigPath", async () => {
  const { client, callSpy } = mockClient();
  const main = traceable(
    async (
      value: number,
      options: {
        suffix: string;
        langsmithExtra?: Partial<RunTreeConfig>;
      }
    ): Promise<string> => `${value}${options.suffix}`,
    {
      client,
      name: "main",
      argsConfigPath: [1, "langsmithExtra"],
      tracingEnabled: true,
    }
  );

  await main(1, {
    suffix: "hello",
    langsmithExtra: {
      name: "renamed",
      tags: ["tag1", "tag2"],
      metadata: { customValue: "hello" },
    },
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["renamed:0"],
    edges: [],
    data: {
      "renamed:0": {
        extra: { metadata: { customValue: "hello" } },
        tags: ["tag1", "tag2"],
        inputs: {
          args: [1, { suffix: "hello" }],
        },
        outputs: { outputs: "1hello" },
      },
    },
  });
});

test("traceable continues execution when client throws error", async () => {
  const errorClient = {
    createRun: jest
      .fn()
      .mockRejectedValue(new Error("Expected test client error") as never),
    updateRun: jest
      .fn()
      .mockRejectedValue(new Error("Expected test client error") as never),
  };

  const tracedFunction = traceable(
    async (value: number): Promise<number> => value * 2,
    {
      client: errorClient as unknown as Client,
      name: "errorTest",
      tracingEnabled: true,
    }
  );

  const result = await tracedFunction(5);

  expect(result).toBe(10);
  expect(errorClient.createRun).toHaveBeenCalled();
  expect(errorClient.updateRun).toHaveBeenCalled();
});

test("traceable with processInputs", async () => {
  const { client, callSpy } = mockClient();

  type FuncInputs = { username: string; password: string };

  const processInputs = jest.fn((inputs: FuncInputs) => {
    return { ...inputs, password: "****" };
  });

  const originalFunc = async function func(input: FuncInputs) {
    // The function should receive the original inputs
    expect(input.password).toBe("secret");
    return `Welcome, ${input.username}`;
  };

  let func = traceable(originalFunc, {
    client,
    tracingEnabled: true,
    // @ts-expect-error - Should infer inputs as FuncInputs
    processInputs: (inputs: { foo: string }) => {
      return { ...inputs, password: "****" };
    },
  });

  func = traceable(originalFunc, {
    client,
    tracingEnabled: true,
    processInputs,
  });

  await func({ username: "user1", password: "secret" });

  expect(processInputs).toHaveBeenCalledWith({
    username: "user1",
    password: "secret",
  });
  // Verify that the logged inputs have the password masked
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        inputs: {
          username: "user1",
          password: "****",
        },
        outputs: { outputs: "Welcome, user1" },
      },
    },
  });
});

test("traceable with processOutputs", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((_outputs: { outputs: string }) => {
    return { outputs: "Modified Output" };
  });

  const originalFunc = async function (input: string) {
    return `Original Output for ${input}`;
  };

  let func = traceable(originalFunc, {
    client,
    tracingEnabled: true,
    // @ts-expect-error - Should infer outputs as a nested object for simple string return values
    processOutputs: (outputs: string) => {
      return outputs;
    },
  });

  func = traceable(originalFunc, {
    client,
    tracingEnabled: true,
    processOutputs,
  });

  const result = await func("test");

  expect(processOutputs).toHaveBeenCalledWith({
    outputs: "Original Output for test",
  });
  expect(result).toBe("Original Output for test");
  // Verify that the tracing data shows the modified output
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["originalFunc:0"],
    edges: [],
    data: {
      "originalFunc:0": {
        inputs: { input: "test" },
        outputs: { outputs: "Modified Output" },
      },
    },
  });
});

test("traceable process inputs/process outputs type inference", async () => {
  const { client } = mockClient();

  const funcWithMultipleArgs = async (a: string, b: number, c: boolean) => {
    return { a, b, c };
  };

  await traceable(funcWithMultipleArgs, {
    client,
    processInputs: (inputs) => {
      // @ts-expect-error - Should infer several inputs as an array
      inputs.a;
      inputs.args[0];
      if (
        typeof inputs.args[0] !== "string" ||
        typeof inputs.args[1] !== "number" ||
        typeof inputs.args[2] !== "boolean"
      ) {
        throw new Error("Invalid inputs");
      }
      return {};
    },
    processOutputs: (outputs) => {
      // @ts-expect-error - Should infer object return values unchanged
      outputs.outputs;
      if (
        typeof outputs.a !== "string" ||
        typeof outputs.b !== "number" ||
        typeof outputs.c !== "boolean"
      ) {
        throw new Error("Invalid outputs");
      }
      return {};
    },
  })("a", 1, true);

  const funcWithArrayInputAndReturn = async (a: string[]) => {
    a.slice(0, 1);
    return ["a", "b", "c"];
  };

  await traceable(funcWithArrayInputAndReturn, {
    client,
    processInputs: (inputs) => {
      inputs.input[0];
      return {};
    },
    processOutputs: (outputs) => {
      // @ts-expect-error - Should wrap string return values as { outputs: string }
      outputs.slice;
      outputs.outputs.slice(0, 1);
      return {};
    },
  })(["a", "b", "c"]);

  const funcWithStringInputAndReturn = async (a: string) => {
    a.slice(0, 1);
    return "b";
  };

  await traceable(funcWithStringInputAndReturn, {
    client,
    processInputs: (inputs) => {
      // @ts-expect-error - Should infer string input as { input: string }
      inputs.slice;
      if (typeof inputs.input !== "string") {
        throw new Error("Invalid inputs");
      }
      return {};
    },
    processOutputs: (outputs) => {
      // @ts-expect-error - Should infer string return value as { outputs: string }
      outputs.slice;
      if (typeof outputs.outputs !== "string") {
        throw new Error("Invalid outputs");
      }
      return {};
    },
  })("a");

  const funcWithObjectInputAndReturn = async (a: { b: string }) => {
    a.b.slice(0, 1);
    return { b: "b" };
  };

  await traceable(funcWithObjectInputAndReturn, {
    client,
    processInputs: (inputs) => {
      // @ts-expect-error - Should infer object input directly
      inputs.slice;
      if (typeof inputs.b !== "string") {
        throw new Error("Invalid inputs");
      }
      return { b: inputs.b };
    },
    processOutputs: (outputs) => {
      // @ts-expect-error - Should infer object return value directly
      outputs.slice;
      if (typeof outputs.b !== "string") {
        throw new Error("Invalid outputs");
      }
      return { b: outputs.b };
    },
  })({ b: "a" });

  const funcWithIteratorInputAndReturn = function* (a: Iterable<string>) {
    for (const item of a) {
      yield item;
    }
  };

  const tracedIteratorFunc = traceable(funcWithIteratorInputAndReturn, {
    client,
    processInputs: (inputs) => {
      // @ts-expect-error - Should infer nested input
      inputs.slice;
      inputs.input.slice(0, 1);
      if (!Array.isArray(inputs.input)) {
        throw new Error("Invalid inputs");
      }
      return {};
    },
    processOutputs: (outputs) => {
      // @ts-expect-error - Should infer nested return value
      outputs.slice;
      outputs.outputs.slice(0, 1);
      if (!Array.isArray(outputs.outputs)) {
        throw new Error("Invalid outputs");
      }
      return {};
    },
  });
  const chunks = [];
  for (const value of await tracedIteratorFunc(["a", "b", "c"])) {
    chunks.push(value);
  }
  expect(chunks).toEqual(["a", "b", "c"]);

  const funcWithAsyncIteratorInputAndReturn = async function* (
    a: AsyncIterable<string>
  ) {
    for await (const item of a) {
      yield item;
    }
  };

  const tracedAsyncIteratorFunc = traceable(
    funcWithAsyncIteratorInputAndReturn,
    {
      client,
      processInputs: (inputs) => {
        // @ts-expect-error - Should infer nested input
        inputs.slice;
        inputs.input.slice(0, 1);
        if (!Array.isArray(inputs.input)) {
          throw new Error("Invalid inputs");
        }
        return {};
      },
      processOutputs: (outputs) => {
        // @ts-expect-error - Should infer nested return value
        outputs.slice;
        outputs.outputs.slice(0, 1);
        if (!Array.isArray(outputs.outputs)) {
          throw new Error("Invalid outputs");
        }
        return {};
      },
    }
  );
  const inputAsyncIterable = (async function* () {
    yield "d";
    yield "e";
    yield "f";
  })();
  const chunks2 = [];
  for await (const value of tracedAsyncIteratorFunc(inputAsyncIterable)) {
    chunks2.push(value);
  }
  expect(chunks2).toEqual(["d", "e", "f"]);
});

test("traceable with processInputs throwing error does not affect invocation", async () => {
  const { client, callSpy } = mockClient();

  const processInputs = jest.fn((_inputs: Readonly<KVMap>) => {
    throw new Error("totally expected test processInputs error");
  });

  const func = traceable(
    async function func(input: { username: string }) {
      // This should not be called
      return `Hello, ${input.username}`;
    },
    {
      client,
      tracingEnabled: true,
      processInputs,
    }
  );

  const result = await func({ username: "user1" });

  expect(processInputs).toHaveBeenCalledWith({ username: "user1" });
  expect(result).toBe("Hello, user1");

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        inputs: { username: "user1" },
        outputs: { outputs: "Hello, user1" },
      },
    },
  });
});

test("traceable with processOutputs throwing error does not affect invocation", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((_outputs: Readonly<KVMap>) => {
    throw new Error("totally expected test processInputs error");
  });

  const func = traceable(
    async function func(input: string) {
      return `Original Output for ${input}`;
    },
    {
      client,
      tracingEnabled: true,
      processOutputs,
    }
  );

  const result = await func("test");

  expect(processOutputs).toHaveBeenCalledWith({
    outputs: "Original Output for test",
  });
  expect(result).toBe("Original Output for test");

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        inputs: { input: "test" },
        outputs: { outputs: "Original Output for test" },
      },
    },
  });
});

test("traceable async generator with processOutputs", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((outputs: Readonly<KVMap>) => {
    return { outputs: outputs.outputs.map((output: number) => output * 2) };
  });

  const func = traceable(
    async function* func() {
      for (let i = 1; i <= 3; i++) {
        yield i;
      }
    },
    {
      client,
      tracingEnabled: true,
      processOutputs,
    }
  );

  const results: number[] = [];
  for await (const value of func()) {
    results.push(value);
  }

  expect(results).toEqual([1, 2, 3]); // Original values
  expect(processOutputs).toHaveBeenCalledWith({ outputs: [1, 2, 3] });

  // Tracing data should reflect the processed outputs
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        outputs: { outputs: [2, 4, 6] }, // Processed outputs
      },
    },
  });
});

test("traceable function returning object with async iterable and processOutputs", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((outputs: Readonly<KVMap>) => {
    return { outputs: outputs.outputs.map((output: number) => output * 2) };
  });

  const func = traceable(
    async function func() {
      return {
        data: "some data",
        stream: (async function* () {
          for (let i = 1; i <= 3; i++) {
            yield i;
          }
        })(),
      };
    },
    {
      client,
      tracingEnabled: true,
      processOutputs,
      __finalTracedIteratorKey: "stream",
    }
  );

  const result = await func();
  expect(result.data).toBe("some data");

  const results: number[] = [];
  for await (const value of result.stream) {
    results.push(value);
  }

  expect(results).toEqual([1, 2, 3]);
  expect(processOutputs).toHaveBeenCalledWith({ outputs: [1, 2, 3] });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        outputs: { outputs: [2, 4, 6] },
      },
    },
  });
});

test("traceable generator function with processOutputs", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((outputs: Readonly<KVMap>) => {
    return { outputs: outputs.outputs.map((output: number) => output * 2) };
  });

  function* func() {
    for (let i = 1; i <= 3; i++) {
      yield i;
    }
  }

  const tracedFunc = traceable(func, {
    client,
    tracingEnabled: true,
    processOutputs,
  });

  const results: number[] = [];
  for (const value of await tracedFunc()) {
    results.push(value);
  }

  expect(results).toEqual([1, 2, 3]);
  expect(processOutputs).toHaveBeenCalledWith({ outputs: [1, 2, 3] });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        outputs: { outputs: [2, 4, 6] },
      },
    },
  });
});

test("traceable with complex outputs", async () => {
  const { client, callSpy } = mockClient();

  const processOutputs = jest.fn((outputs: Readonly<KVMap>) => {
    return { data: "****", output: outputs.output, nested: outputs.nested };
  });

  const func = traceable(
    async function func(input: string) {
      return {
        data: "some sensitive data",
        output: `Original Output for ${input}`,
        nested: {
          key: "value",
          nestedOutput: `Nested Output for ${input}`,
        },
      };
    },
    {
      client,
      tracingEnabled: true,
      processOutputs,
    }
  );

  const result = await func("test");

  expect(result).toEqual({
    data: "some sensitive data",
    output: "Original Output for test",
    nested: {
      key: "value",
      nestedOutput: "Nested Output for test",
    },
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        inputs: { input: "test" },
        outputs: {
          data: "****",
          output: "Original Output for test",
          nested: {
            key: "value",
            nestedOutput: "Nested Output for test",
          },
        },
      },
    },
  });
});

test("traceable with usage metadata", async () => {
  const { client, callSpy } = mockClient();

  const func = traceable(
    async function func(inputs: string) {
      return {
        messages: [
          {
            role: "assistant",
            content: inputs.split("").reverse().join(""),
          },
        ],
        usage_metadata: {
          input_tokens: 10,
          output_tokens: 20,
          total_tokens: 30,
        },
      };
    },
    {
      client,
      tracingEnabled: true,
    }
  );

  const result = await func("foo");

  expect(result).toEqual({
    messages: [
      {
        role: "assistant",
        content: "oof",
      },
    ],
    usage_metadata: {
      input_tokens: 10,
      output_tokens: 20,
      total_tokens: 30,
    },
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: 10,
              output_tokens: 20,
              total_tokens: 30,
            },
          },
        },
        inputs: { input: "foo" },
        outputs: {
          messages: [
            {
              role: "assistant",
              content: "oof",
            },
          ],
          usage_metadata: {
            input_tokens: 10,
            output_tokens: 20,
            total_tokens: 30,
          },
        },
      },
    },
  });
});

test("traceable with usage metadata with extract_usage", async () => {
  const { client, callSpy } = mockClient();

  const func = traceable(
    async function func(inputs: string) {
      const runTree = getCurrentRunTree();
      runTree.metadata.usage_metadata = {
        input_tokens: 100,
        output_tokens: 200,
        total_tokens: 300,
      };
      return {
        messages: [
          {
            role: "assistant",
            content: inputs.split("").reverse().join(""),
          },
        ],
      };
    },
    {
      client,
      tracingEnabled: true,
    }
  );

  const result = await func("foo");

  expect(result).toEqual({
    messages: [
      {
        role: "assistant",
        content: "oof",
      },
    ],
  });

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: 100,
              output_tokens: 200,
              total_tokens: 300,
            },
          },
        },
        inputs: { input: "foo" },
        outputs: {
          messages: [
            {
              role: "assistant",
              content: "oof",
            },
          ],
          usage_metadata: {
            input_tokens: 100,
            output_tokens: 200,
            total_tokens: 300,
          },
        },
      },
    },
  });
});

test("traceable with usage metadata with streaming", async () => {
  const { client, callSpy } = mockClient();

  const func = traceable(
    async function* func(inputs: string) {
      for (const char of inputs) {
        yield {
          messages: [
            {
              role: "assistant",
              content: char,
            },
          ],
        };
      }
      const runTree = getCurrentRunTree();
      runTree.metadata.usage_metadata = {
        input_tokens: 100,
        output_tokens: 200,
        total_tokens: 300,
      };
    },
    {
      client,
      tracingEnabled: true,
    }
  );

  const results: KVMap[] = [];
  for await (const chunk of func("foo")) {
    results.push(chunk);
  }

  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: 100,
              output_tokens: 200,
              total_tokens: 300,
            },
          },
        },
        inputs: { input: "foo" },
        outputs: {
          usage_metadata: {
            input_tokens: 100,
            output_tokens: 200,
            total_tokens: 300,
          },
        },
      },
    },
  });
});

test("serializes well-known types in inputs and outputs", async () => {
  const { client, callSpy } = mockClient();

  const func = traceable(
    async (_input: {
      map: Map<string, any>;
      set: Set<any>;
      date: Date;
      regex: RegExp;
      error: Error;
      bigint: bigint;
    }) => {
      return {
        processedMap: new Map([["result", "processed"]]),
        processedSet: new Set([1, 2, 3]),
        processedDate: new Date("2023-12-25T00:00:00.000Z"),
        processedRegex: /processed.*pattern/gi,
        processedError: new Error("Processed error"),
        processedBigint: BigInt(987654321),
        regularString: "normal output",
      };
    },
    { client, tracingEnabled: true, name: "serializeTypesTest" }
  );

  const inputMap = new Map<string, unknown>([["input", "value"]]);
  inputMap.set("nested", { deep: "object" });
  const inputSet = new Set(["a", "b", "c", 123]);
  const inputDate = new Date("2023-01-01T00:00:00.000Z");
  const inputRegex = /input.*test/i;
  const inputError = new Error("Input error message");
  inputError.name = "CustomError";
  const inputBigint = BigInt(123456789);

  const result = await func({
    map: inputMap,
    set: inputSet,
    date: inputDate,
    regex: inputRegex,
    error: inputError,
    bigint: inputBigint,
  });

  // Verify the function returns the expected types
  expect(result.processedMap).toBeInstanceOf(Map);
  expect(result.processedSet).toBeInstanceOf(Set);
  expect(result.processedDate).toBeInstanceOf(Date);
  expect(result.processedRegex).toBeInstanceOf(RegExp);
  expect(result.processedError).toBeInstanceOf(Error);
  expect(typeof result.processedBigint).toBe("bigint");

  // Verify serialization in traced inputs/outputs
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["serializeTypesTest:0"],
    edges: [],
    data: {
      "serializeTypesTest:0": {
        inputs: {
          map: { input: "value", nested: { deep: "object" } }, // Map -> Object
          set: ["a", "b", "c", 123], // Set -> Array
          date: "2023-01-01T00:00:00.000Z", // Date -> ISO string
          regex: "/input.*test/i", // RegExp -> string
          error: { name: "CustomError", message: "Input error message" }, // Error -> safe object (no stack)
          bigint: "123456789", // BigInt -> string
        },
        outputs: {
          processedMap: { result: "processed" }, // Map -> Object
          processedSet: [1, 2, 3], // Set -> Array
          processedDate: "2023-12-25T00:00:00.000Z", // Date -> ISO string
          processedRegex: "/processed.*pattern/gi", // RegExp -> string
          processedError: { name: "Error", message: "Processed error" }, // Error -> safe object
          processedBigint: "987654321", // BigInt -> string
          regularString: "normal output", // Regular string unchanged
        },
      },
    },
  });
});

// Unit tests converted from traceable.int.test.ts
test("traceable wrapper with error thrown", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  const addValueTraceable = traceable(
    (_: string, __: number) => {
      throw new Error("I am bad");
    },
    {
      name: "add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
      id: runId,
      tracingEnabled: true,
    }
  );

  expect(isTraceableFunction(addValueTraceable)).toBe(true);

  try {
    await addValueTraceable("testing", 9);
    expect(true).toBe(false); // Should not reach here
  } catch (e: any) {
    expect(e.message).toEqual("I am bad");
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["add_value:0"]);
  expect(tree.data["add_value:0"].error).toEqual("Error: I am bad");
});

test("traceable wrapper with async error thrown", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  const addValueTraceable = traceable(
    async (_: string, __: number) => {
      throw new Error("I am bad");
    },
    {
      name: "add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
      id: runId,
      tracingEnabled: true,
    }
  );

  expect(isTraceableFunction(addValueTraceable)).toBe(true);

  try {
    await addValueTraceable("testing", 9);
    expect(true).toBe(false); // Should not reach here
  } catch (e: any) {
    expect(e.message).toEqual("I am bad");
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["add_value:0"]);
  expect(tree.data["add_value:0"].error).toEqual("Error: I am bad");
  expect(tree.data["add_value:0"].inputs).toEqual({ args: ["testing", 9] });
});

test("traceable wrapper with nested calls", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  const addValueTraceable = traceable(
    (a: string, b: number) => {
      return a + b;
    },
    {
      name: "add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
      id: runId,
      tracingEnabled: true,
    }
  );

  expect(await addValueTraceable("testing", 9)).toBe("testing9");
  expect(isTraceableFunction(addValueTraceable)).toBe(true);

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["add_value:0"]);
  expect(tree.data["add_value:0"].outputs).toEqual({ outputs: "testing9" });

  // Test nested calls
  const runId2 = uuidv4();
  const nestedAddValueTraceable = traceable(
    (a: string, b: number) => {
      return a + b;
    },
    {
      name: "nested_add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
    }
  );

  const entryTraceable = traceable(
    async (complex: { value: string }) => {
      const result = await nestedAddValueTraceable(complex.value, 1);
      const result2 = await nestedAddValueTraceable(result, 2);
      return nestedAddValueTraceable(result2, 3);
    },
    {
      name: "run_with_nesting",
      project_name: "__test_traceable_wrapper",
      client: client,
      id: runId2,
    }
  );

  expect(await entryTraceable({ value: "testing" })).toBe("testing123");
  expect(isTraceableFunction(entryTraceable)).toBe(true);
});

test("traceable wrapper with getCurrentRunTree", async () => {
  const { client } = mockClient();

  // Called outside a traceable function - should throw
  expect(() => getCurrentRunTree()).toThrowError();

  const runId = uuidv4();
  const nestedAddValueTraceable = traceable(
    (a: string, b: number) => {
      const runTree = getCurrentRunTree();
      expect(runTree.id).toBeDefined();
      expect(runTree.id).not.toEqual(runId);
      expect(runTree.dotted_order.includes(`${runId}.`)).toBe(true);
      return a + b;
    },
    {
      name: "nested_add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
    }
  );

  const addValueTraceable = traceable(
    (a: string, b: number) => {
      const runTree = getCurrentRunTree();
      expect(runTree.id).toBe(runId);
      return nestedAddValueTraceable(a, b);
    },
    {
      name: "add_value",
      project_name: "__test_traceable_wrapper",
      client: client,
      tracingEnabled: true,
      id: runId,
    }
  );

  expect(await addValueTraceable("testing", 9)).toBe("testing9");
});

test("traceable wrapper with aggregator function", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();
  let tracedOutput = "";

  // Mock a streaming function that yields chunks
  async function* mockStreamingFunction(input: string) {
    const chunks = input.split(" ");
    for (const chunk of chunks) {
      yield { content: chunk };
    }
  }

  const iterableTraceable = traceable(mockStreamingFunction, {
    name: "streaming_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      tracedOutput = chunks.map((chunk) => chunk?.content ?? "").join(" ");
      return tracedOutput;
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  const chunks = [];
  for await (const chunk of iterableTraceable("Hello there")) {
    chunks.push(chunk);
  }

  expect(chunks.map((c) => c.content).join(" ")).toBe("Hello there");
  expect(tracedOutput).toBe("Hello there");

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["streaming_traceable:0"]);
  expect(tree.data["streaming_traceable:0"].outputs).toEqual({
    outputs: tracedOutput,
  });
});

test("traceable async generator success", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function* giveMeNumbers() {
    for (let i = 0; i < 5; i++) {
      yield i;
    }
  }

  const iterableTraceable = traceable(giveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  const results = [];
  for await (const num of iterableTraceable()) {
    results.push(num);
  }

  expect(results).toEqual([0, 1, 2, 3, 4]);

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0 1 2 3 4" });
});

test("traceable async generator throws error", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function* giveMeNumbers() {
    for (let i = 0; i < 5; i++) {
      yield i;
      if (i == 2) {
        throw new Error("I am bad");
      }
    }
  }

  const iterableTraceable = traceable(giveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  try {
    for await (const _ of iterableTraceable()) {
      // Pass
    }
    expect(true).toBe(false); // Should not reach here
  } catch (err: any) {
    expect(err.message).toEqual("I am bad");
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0 1 2" });
  expect(tree.data["i_traceable:0"].error).toEqual("Error: I am bad");
});

test("traceable async generator break finishes run", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function* giveMeNumbers() {
    for (let i = 0; i < 5; i++) {
      yield i;
    }
  }

  const iterableTraceable = traceable(giveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  for await (const _ of iterableTraceable()) {
    break;
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0" });
  expect(tree.data["i_traceable:0"].error).toEqual("Cancelled");
});

test("traceable with function overloads", async () => {
  const { client } = mockClient();

  async function overload(a: string, b: number): Promise<string>;
  async function overload(config: { a: string; b: number }): Promise<string>;
  async function overload(
    ...args: [a: string, b: number] | [config: { a: string; b: number }]
  ): Promise<string> {
    if (args.length === 1) {
      return args[0].a + args[0].b;
    }
    return args[0] + args[1];
  }

  const wrappedOverload = traceable(overload, {
    name: "wrapped_overload",
    project_name: "__test_traceable_wrapper",
    client: client,
  });

  expect(await wrappedOverload("testing", 123)).toBe("testing123");
  expect(await wrappedOverload({ a: "testing", b: 456 })).toBe("testing456");
  expect(isTraceableFunction(wrappedOverload)).toBe(true);
});

test("traceable returning async generator", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function giveMeGiveMeNumbers() {
    async function* giveMeNumbers() {
      for (let i = 0; i < 5; i++) {
        yield i;
      }
    }
    return giveMeNumbers();
  }

  const iterableTraceable = traceable(giveMeGiveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  for await (const _ of await iterableTraceable()) {
    // Pass
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0 1 2 3 4" });
});

test("traceable promise for async generator with error", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function giveMeGiveMeNumbers() {
    async function* giveMeNumbers() {
      for (let i = 0; i < 5; i++) {
        yield i;
        if (i == 2) {
          throw new Error("I am bad");
        }
      }
    }
    return giveMeNumbers();
  }

  const iterableTraceable = traceable(giveMeGiveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  try {
    for await (const _ of await iterableTraceable()) {
      // Pass
    }
    expect(true).toBe(false); // Should not reach here
  } catch (err: any) {
    expect(err.message).toEqual("I am bad");
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0 1 2" });
  expect(tree.data["i_traceable:0"].error).toEqual("Error: I am bad");
});

test("traceable promise for async generator break", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  async function giveMeGiveMeNumbers() {
    async function* giveMeNumbers() {
      for (let i = 0; i < 5; i++) {
        yield i;
      }
    }
    return giveMeNumbers();
  }

  const iterableTraceable = traceable(giveMeGiveMeNumbers, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    aggregator: (chunks) => {
      return chunks.join(" ");
    },
    tracingEnabled: true,
  });

  expect(isTraceableFunction(iterableTraceable)).toBe(true);

  for await (const _ of await iterableTraceable()) {
    break;
  }

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: "0" });
  expect(tree.data["i_traceable:0"].error).toEqual("Cancelled");
});

test("passing null doesn't throw an error", async () => {
  const { client, callSpy } = mockClient();
  const runId = uuidv4();

  const func = traceable(async (input: null) => input, {
    name: "i_traceable",
    project_name: "__test_traceable_wrapper_aggregator",
    client: client,
    id: runId,
    tracingEnabled: true,
  });

  expect(await func(null)).toBe(null);
  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["i_traceable:0"]);
  expect(tree.data["i_traceable:0"].inputs).toEqual({ inputs: null });
  expect(tree.data["i_traceable:0"].outputs).toEqual({ outputs: null });
});

test("traceable with invalid properties in usage metadata", async () => {
  const { client, callSpy } = mockClient();
  const traceableLLM = traceable(
    (_input: Record<string, unknown>) => {
      return {
        messages: [
          {
            role: "assistant",
            content: "Hello, world!",
          },
        ],
        usage_metadata: {
          foo: "bar",
          input_tokens: 10,
          output_tokens: 10,
          total_tokens: 20,
        },
      };
    },
    {
      name: "extra_usage_metadata_run",
      metadata: {
        ls_provider: "anthropic",
        ls_model_name: "claude-sonnet-4-20250514",
      },
      client,
      run_type: "llm",
      tracingEnabled: true,
    }
  );

  await traceableLLM({});

  await client.awaitPendingTraceBatches();

  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["extra_usage_metadata_run:0"]);

  expect(
    tree.data["extra_usage_metadata_run:0"].extra?.metadata?.usage_metadata
  ).toEqual({
    foo: "bar",
    input_tokens: 10,
    output_tokens: 10,
    total_tokens: 20,
  });
});

test("traceable should ignore undefined id", async () => {
  const { client, callSpy } = mockClient();
  const traceableLLM = traceable(
    (_input: Record<string, unknown>) => {
      return {
        messages: [
          {
            role: "assistant",
            content: "Hello, world!",
          },
        ],
        usage_metadata: {
          foo: "bar",
          input_tokens: 10,
          output_tokens: 10,
          total_tokens: 20,
        },
      };
    },
    {
      // simulate bad spread
      id: undefined,
      dotted_order: undefined,
      trace_id: undefined,
      name: "extra_usage_metadata_run",
      start_time: Date.now(),
      metadata: {
        ls_provider: "anthropic",
        ls_model_name: "claude-sonnet-4-20250514",
      },
      client,
      run_type: "llm",
      tracingEnabled: true,
    }
  );

  await traceableLLM({});

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls).toHaveLength(2);
  const tree = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(tree.nodes).toEqual(["extra_usage_metadata_run:0"]);
  expect(tree.data["extra_usage_metadata_run:0"].id).toBeDefined();
  expect(tree.data["extra_usage_metadata_run:0"].dotted_order).toBeDefined();
  expect(tree.data["extra_usage_metadata_run:0"].trace_id).toBeDefined();
  expect(tree.data["extra_usage_metadata_run:0"].id).toEqual(
    tree.data["extra_usage_metadata_run:0"].trace_id
  );
  expect(
    tree.data["extra_usage_metadata_run:0"].dotted_order?.includes(
      tree.data["extra_usage_metadata_run:0"].id
    )
  ).toBe(true);
});

test("traceable with nested calls and reroot replicas", async () => {
  const { client, callSpy } = mockClient({
    callerOptions: { maxRetries: 0 },
    timeout_ms: 30_000,
  });

  // Define nested traceable functions - innermost ones don't need replicas
  const innerTask = traceable(
    async (input: string) => {
      return `processed: ${input}`;
    },
    { name: "innerTask", client, tracingEnabled: true }
  );

  const middleTask = traceable(
    async (input: string) => {
      const result1 = await innerTask(`${input}-a`);
      const result2 = await innerTask(`${input}-b`);
      return `${result1}, ${result2}`;
    },
    { name: "middleTask", client, tracingEnabled: true }
  );

  // Outer task has replicas configured directly
  const outerTask = traceable(
    async (input: string) => {
      const result = await middleTask(input);
      return `final: ${result}`;
    },
    {
      name: "outerTask",
      client,
      tracingEnabled: true,
      replicas: [
        {
          projectName: "child-workspace-rerooted",
          apiKey: "child-key",
          apiUrl: "https://child.example.com",
          reroot: true,
        },
        {
          projectName: "full-trace-workspace",
          apiKey: "full-key",
          apiUrl: "https://full.example.com",
          reroot: false,
        },
      ],
    }
  );

  // Execute the nested traceable calls
  const result = await outerTask("test-input");

  // Verify the result
  expect(result).toBe(
    "final: processed: test-input-a, processed: test-input-b"
  );

  // Wait for async operations
  await client.awaitPendingTraceBatches();

  // Verify API calls were made to both replicas
  expect(callSpy.mock.calls.length).toBeGreaterThan(0);

  // Parse the POST bodies to verify rerooting behavior
  const childPostCalls = callSpy.mock.calls.filter(
    (call) =>
      (call[0] as string).includes("child.example.com") &&
      (call[0] as string).includes("/runs") &&
      (call[1] as any)?.method === "POST"
  );
  const fullPostCalls = callSpy.mock.calls.filter(
    (call) =>
      (call[0] as string).includes("full.example.com") &&
      (call[0] as string).includes("/runs") &&
      (call[1] as any)?.method === "POST"
  );

  expect(childPostCalls.length).toBeGreaterThan(0);
  expect(fullPostCalls.length).toBeGreaterThan(0);

  // Verify correct API keys
  childPostCalls.forEach((call) => {
    const headers = (call[1] as any)?.headers;
    expect(headers["x-api-key"]).toBe("child-key");
  });
  fullPostCalls.forEach((call) => {
    const headers = (call[1] as any)?.headers;
    expect(headers["x-api-key"]).toBe("full-key");
  });

  // Use the tree utility to parse runs from mock calls
  const childTree = getAssumedTreeFromCalls(childPostCalls);
  const fullTree = getAssumedTreeFromCalls(fullPostCalls);

  // Find outerTask and middleTask in both replicas to verify rerooting behavior
  const childOuterTask = Object.values(childTree.data).find(
    (run) => run.name === "outerTask"
  );
  const fullOuterTask = Object.values(fullTree.data).find(
    (run) => run.name === "outerTask"
  );
  const childMiddleTask = Object.values(childTree.data).find(
    (run) => run.name === "middleTask"
  );
  const fullMiddleTask = Object.values(fullTree.data).find(
    (run) => run.name === "middleTask"
  );

  expect(childOuterTask).toBeDefined();
  expect(fullOuterTask).toBeDefined();
  expect(childMiddleTask).toBeDefined();
  expect(fullMiddleTask).toBeDefined();

  // Type assertions after checking they're defined
  if (
    !childOuterTask ||
    !fullOuterTask ||
    !childMiddleTask ||
    !fullMiddleTask
  ) {
    throw new Error("Expected runs to be defined");
  }

  // With reroot=true on outerTask, outerTask should NOT have a parent_run_id in child workspace
  // (it becomes the root of a new tree)
  expect(childOuterTask.parent_run_id).toBeUndefined();

  // middleTask should STILL have a parent_run_id in the rerooted workspace
  // (reroot doesn't propagate to children - we want a new tree, not all root runs)
  expect(childMiddleTask.parent_run_id).toBeDefined();

  // In the full workspace without reroot, both maintain their normal parent relationships
  expect(fullMiddleTask.parent_run_id).toBeDefined();

  // Verify tree structure is maintained in rerooted workspace
  // Should have 4 runs total: outerTask, middleTask, innerTask x2
  expect(Object.keys(childTree.data).length).toBe(4);
  expect(Object.keys(fullTree.data).length).toBe(4);

  // Verify the tree edges in rerooted workspace form a proper tree
  // outerTask (root) -> middleTask -> innerTask (x2)
  expect(childTree.edges.length).toBe(3); // 3 parent-child relationships

  // Verify trace_id is updated for rerooted runs
  // In rerooted workspace, all runs should have trace_id pointing to outerTask
  expect(childOuterTask.trace_id).toBe(childOuterTask.id);
  expect(childMiddleTask.trace_id).toBe(childOuterTask.id);

  // Verify dotted_order is properly reset for the root run
  // Rerooted run should have only one segment in dotted_order
  const childOuterSegments = childOuterTask.dotted_order?.split(".") || [];
  expect(childOuterSegments.length).toBe(1);
}, 180_000);

test("child traceable with own replicas config", async () => {
  const { client, callSpy } = mockClient();

  const defaultProject = "mainProject";
  const replicaProject = "subrun";

  const greatGrandchild = traceable(
    async () => {
      return "greatGrandchild";
    },
    {
      name: "greatGrandchild",
      client,
      tracingEnabled: true,
    }
  );

  const grandchild = traceable(
    async () => {
      const greatGrandchildRes = await greatGrandchild();
      return "grandchild: " + greatGrandchildRes;
    },
    {
      name: "grandchild",
      client,
      tracingEnabled: true,
    }
  );
  const child = traceable(
    async () => {
      const grandchildRes = await grandchild();
      return "child: " + grandchildRes;
    },
    {
      replicas: [
        {
          projectName: defaultProject,
        },
        {
          projectName: replicaProject,
          reroot: true,
        },
      ],
      name: "child",
      client,
      tracingEnabled: true,
    }
  );
  const parent = traceable(
    async () => {
      const childRes = await child();
      return "parent: " + childRes;
    },
    {
      name: "parent",
      client,
      tracingEnabled: true,
      project_name: defaultProject,
    }
  );

  await parent();

  // Wait for async operations
  await new Promise((resolve) => setTimeout(resolve, 100));

  // Verify that child's replicas were used by checking calls to both projects
  const allPostCalls = callSpy.mock.calls.filter(
    (call) =>
      (call[0] as string).includes("/runs") &&
      (call[1] as any)?.method === "POST"
  );

  // Parent should only go to default project (no replicas)
  // Child and grandchild should go to both "main-project" and replicaProject
  // greatGrandchild should also go to both (inherits from grandchild which inherits from child)
  // Total: 1 (parent) + 2 (child) + 2 (grandchild) + 2 (greatGrandchild) = 7 POST calls
  expect(allPostCalls.length).toBe(7);

  // Parse calls - since all go to same mock endpoint, we need to check session_name in body
  const runs = allPostCalls.map((call) => {
    const body = (call[1] as any)?.body;
    let bodyStr: string;
    if (typeof body === "string") {
      bodyStr = body;
    } else if (Buffer.isBuffer(body)) {
      bodyStr = body.toString("utf-8");
    } else if (ArrayBuffer.isView(body)) {
      bodyStr = new TextDecoder().decode(body);
    } else {
      bodyStr = JSON.stringify(body);
    }
    return JSON.parse(bodyStr);
  });

  // Count runs by project
  const defaultProjectRuns = runs.filter(
    (r) => r.session_name === defaultProject
  );
  const subrunRuns = runs.filter((r) => r.session_name === replicaProject);

  // We should have: 1 parent, 1 child, 1 grandchild, 1 greatGrandchild in default
  // Plus: 1 child, 1 grandchild, 1 greatGrandchild in subrun (child's replicas inherited)
  // Total: 7 runs (4 in default + 3 in subrun)
  expect(runs.length).toBe(7);

  // Parent only goes to default project (no replicas)
  const parentRuns = runs.filter((r) => r.name === "parent");
  expect(parentRuns.length).toBe(1);
  expect(parentRuns[0].session_name).toBe(defaultProject);

  // Child goes to BOTH default project and subrun (child's replicas)
  const childRuns = runs.filter((r) => r.name === "child");
  expect(childRuns.length).toBe(2);
  const childProjects = childRuns.map((r) => r.session_name).sort();
  expect(childProjects).toEqual([defaultProject, replicaProject].sort());

  // Grandchild also goes to BOTH (inherits child's replicas)
  const grandchildRuns = runs.filter((r) => r.name === "grandchild");
  expect(grandchildRuns.length).toBe(2);
  const grandchildProjects = grandchildRuns.map((r) => r.session_name).sort();
  expect(grandchildProjects).toEqual([defaultProject, replicaProject].sort());

  // GreatGrandchild also goes to BOTH (inherits from grandchild which inherits from child)
  const greatGrandchildRuns = runs.filter((r) => r.name === "greatGrandchild");
  expect(greatGrandchildRuns.length).toBe(2);
  const greatGrandchildProjects = greatGrandchildRuns
    .map((r) => r.session_name)
    .sort();
  expect(greatGrandchildProjects).toEqual(
    [defaultProject, replicaProject].sort()
  );

  // Verify reroot behavior in replicaProject project
  const subrunChild = subrunRuns.find((r) => r.name === "child");
  const subrunGrandchild = subrunRuns.find((r) => r.name === "grandchild");
  const subrunGreatGrandchild = subrunRuns.find(
    (r) => r.name === "greatGrandchild"
  );

  if (!subrunChild || !subrunGrandchild || !subrunGreatGrandchild) {
    throw new Error("Expected subrun runs to be defined");
  }

  // Child should be a root in subrun (reroot: true)
  expect(subrunChild.parent_run_id).toBeUndefined();

  // Child's dotted_order should have only one segment (it's a new root)
  const childDottedSegments = subrunChild.dotted_order?.split(".") || [];
  expect(childDottedSegments.length).toBe(1);

  // Child's trace_id should be its own id (new trace root after reroot)
  expect(subrunChild.trace_id).toBe(subrunChild.id);

  // Grandchild should have child as parent (inherited replicas, reroot doesn't propagate)
  expect(subrunGrandchild.parent_run_id).toBeDefined();

  // Grandchild's trace_id should match child's id (same trace in rerooted tree)
  // This is the key fix - with ID remapping, grandchild gets the remapped child's id as trace_id
  expect(subrunGrandchild.trace_id).toBe(subrunChild.id);

  // Verify parent_run_id is the remapped child id
  expect(subrunGrandchild.parent_run_id).toBe(subrunChild.id);

  // Grandchild's dotted_order should have two segments (child.grandchild)
  const grandchildDottedSegments =
    subrunGrandchild.dotted_order?.split(".") || [];
  expect(grandchildDottedSegments.length).toBe(2);

  // GreatGrandchild should also be part of the rerooted trace
  expect(subrunGreatGrandchild.trace_id).toBe(subrunChild.id);
  expect(subrunGreatGrandchild.parent_run_id).toBe(subrunGrandchild.id);

  // GreatGrandchild's dotted_order should have three segments (child.grandchild.greatGrandchild)
  const greatGrandchildDottedSegments =
    subrunGreatGrandchild.dotted_order?.split(".") || [];
  expect(greatGrandchildDottedSegments.length).toBe(3);

  // In the default project (no reroot), verify child still has parent
  const defaultChild = defaultProjectRuns.find((r) => r.name === "child");
  const defaultGrandchild = defaultProjectRuns.find(
    (r) => r.name === "grandchild"
  );
  const defaultGreatGrandchild = defaultProjectRuns.find(
    (r) => r.name === "greatGrandchild"
  );

  if (!defaultChild || !defaultGrandchild || !defaultGreatGrandchild) {
    throw new Error("Expected default project runs to be defined");
  }

  // In default project, child should have parent (no reroot there)
  expect(defaultChild.parent_run_id).toBeDefined();

  // All runs in default project should share same trace_id (parent's trace)
  const defaultParent = defaultProjectRuns.find((r) => r.name === "parent");
  expect(defaultChild.trace_id).toBe(defaultParent?.trace_id);
  expect(defaultGrandchild.trace_id).toBe(defaultParent?.trace_id);
  expect(defaultGreatGrandchild.trace_id).toBe(defaultParent?.trace_id);
});
