import { jest } from "@jest/globals";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { _LC_CONTEXT_VARIABLES_KEY } from "../singletons/constants.js";
import { ROOT, traceable, withRunTree } from "../traceable.js";
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
              result: "[Circular]",
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

  const processInputs = jest.fn((inputs: Readonly<KVMap>) => {
    return { ...inputs, password: "****" };
  });

  const func = traceable(
    async function func(input: { username: string; password: string }) {
      // The function should receive the original inputs
      expect(input.password).toBe("secret");
      return `Welcome, ${input.username}`;
    },
    {
      client,
      tracingEnabled: true,
      processInputs,
    }
  );

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

  const processOutputs = jest.fn((_outputs: Readonly<KVMap>) => {
    return { outputs: "Modified Output" };
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
  // Verify that the tracing data shows the modified output
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["func:0"],
    edges: [],
    data: {
      "func:0": {
        inputs: { input: "test" },
        outputs: { outputs: "Modified Output" },
      },
    },
  });
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
