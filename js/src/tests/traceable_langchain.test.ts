/* eslint-disable no-process-env */
import { traceable } from "../traceable.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { mockClient } from "./utils/mock_client.js";
import { FakeChatModel } from "@langchain/core/utils/testing";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { BaseMessage, HumanMessage } from "@langchain/core/messages";
import { awaitAllCallbacks } from "@langchain/core/callbacks/promises";
import { RunnableTraceable, getLangchainCallbacks } from "../langchain.js";
import { RunnableLambda } from "@langchain/core/runnables";
import {
  setContextVariable,
  getContextVariable,
} from "@langchain/core/context";

describe("to langchain", () => {
  const llm = new FakeChatModel({});
  const prompt = ChatPromptTemplate.fromMessages<{ text: string }>([
    ["human", "{text}"],
  ]);
  const parser = new StringOutputParser();
  const chain = prompt.pipe(llm).pipe(parser);

  test("invoke", async () => {
    const { client, callSpy } = mockClient();

    const main = traceable(
      async (input: { text: string }) => {
        return chain.invoke(input, {
          callbacks: await getLangchainCallbacks(),
        });
      },
      {
        name: "main",
        client,
        tracingEnabled: true,
        tags: ["welcome"],
        metadata: { hello: "world" },
      }
    );

    const result = await main({ text: "Hello world" });
    expect(result).toEqual("Hello world");

    await awaitAllCallbacks();

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "main:0",
        "RunnableSequence:1",
        "ChatPromptTemplate:2",
        "FakeChatModel:3",
        "StrOutputParser:4",
      ],
      edges: [
        ["main:0", "RunnableSequence:1"],
        ["RunnableSequence:1", "ChatPromptTemplate:2"],
        ["RunnableSequence:1", "FakeChatModel:3"],
        ["RunnableSequence:1", "StrOutputParser:4"],
      ],
      data: {
        "main:0": {
          inputs: { text: "Hello world" },
          outputs: { outputs: "Hello world" },
          tags: ["welcome"],
          extra: { metadata: { hello: "world" } },
        },
      },
    });
  });

  test("stream", async () => {
    const { client, callSpy } = mockClient();

    const main = traceable(
      async function* main(input: { text: string }) {
        for await (const token of await chain.stream(input, {
          callbacks: await getLangchainCallbacks(),
        })) {
          yield token;
        }
      },
      { client, tracingEnabled: true }
    );

    const result = [];
    for await (const token of main({ text: "Hello world" })) {
      result.push(token);
    }

    expect(result).toEqual(["Hello world"]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "main:0",
        "RunnableSequence:1",
        "ChatPromptTemplate:2",
        "FakeChatModel:3",
        "StrOutputParser:4",
      ],
      edges: [
        ["main:0", "RunnableSequence:1"],
        ["RunnableSequence:1", "ChatPromptTemplate:2"],
        ["RunnableSequence:1", "FakeChatModel:3"],
        ["RunnableSequence:1", "StrOutputParser:4"],
      ],
    });
  });

  test("batch", async () => {
    const { client, callSpy } = mockClient();

    const main = traceable(
      async (input: { texts: string[] }) => {
        return chain.batch(
          input.texts.map((text) => ({ text })),
          { callbacks: await getLangchainCallbacks() }
        );
      },
      { name: "main", client, tracingEnabled: true }
    );

    const result = await main({ texts: ["Hello world", "Who are you?"] });

    await awaitAllCallbacks();
    expect(result).toEqual(["Hello world", "Who are you?"]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "main:0",
        "RunnableSequence:1",
        "RunnableSequence:2",
        "ChatPromptTemplate:3",
        "ChatPromptTemplate:4",
        "FakeChatModel:5",
        "FakeChatModel:6",
        "StrOutputParser:7",
        "StrOutputParser:8",
      ],
      edges: [
        ["main:0", "RunnableSequence:1"],
        ["main:0", "RunnableSequence:2"],
        ["RunnableSequence:1", "ChatPromptTemplate:3"],
        ["RunnableSequence:2", "ChatPromptTemplate:4"],
        ["RunnableSequence:1", "FakeChatModel:5"],
        ["RunnableSequence:2", "FakeChatModel:6"],
        ["RunnableSequence:1", "StrOutputParser:7"],
        ["RunnableSequence:2", "StrOutputParser:8"],
      ],
    });
  });
});

describe("to traceable", () => {
  test("invoke", async () => {
    const { client, callSpy } = mockClient();

    const llm = new FakeChatModel({});
    const prompt = ChatPromptTemplate.fromMessages<{ text: string }>([
      ["human", "{text}"],
    ]);
    const parser = new StringOutputParser();

    const addValueTraceable = traceable(
      (msg: BaseMessage) =>
        new HumanMessage({ content: msg.content + " world" }),
      { name: "add_negligible_value" }
    );

    const chain = prompt
      .pipe(llm)
      .pipe(RunnableTraceable.from(addValueTraceable))
      .pipe(parser);

    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore client might be of different type
    const tracer = new LangChainTracer({ client });
    const response = await chain.invoke(
      { text: "Hello" },
      { callbacks: [tracer] }
    );

    // callbacks are backgrounded by default
    await awaitAllCallbacks();

    expect(response).toEqual("Hello world");
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "RunnableSequence:0",
        "ChatPromptTemplate:1",
        "FakeChatModel:2",
        "add_negligible_value:3",
        "StrOutputParser:4",
      ],
      edges: [
        ["RunnableSequence:0", "ChatPromptTemplate:1"],
        ["RunnableSequence:0", "FakeChatModel:2"],
        ["RunnableSequence:0", "add_negligible_value:3"],
        ["RunnableSequence:0", "StrOutputParser:4"],
      ],
    });
  });

  test("array stream", async () => {
    const { client, callSpy } = mockClient();

    const source = RunnableTraceable.from(
      traceable(function (input: { text: string }) {
        return input.text.split(" ");
      })
    );

    const tokens: unknown[] = [];
    for await (const chunk of await source.stream(
      { text: "Hello world" },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore client might be of different type
      { callbacks: [new LangChainTracer({ client })] }
    )) {
      tokens.push(chunk);
    }

    expect(tokens).toEqual([["Hello", "world"]]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["<lambda>:0"],
      edges: [],
    });
  });

  test("generator stream", async () => {
    const { client, callSpy } = mockClient();

    const source = RunnableTraceable.from(
      traceable(function* (input: { text: string }) {
        const chunks = input.text.split(" ");
        for (const chunk of chunks) {
          yield chunk;
        }
      })
    );

    const tokens: unknown[] = [];
    for await (const chunk of await source.stream(
      { text: "Hello world" },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore client might be of different type
      { callbacks: [new LangChainTracer({ client })] }
    )) {
      tokens.push(chunk);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["<lambda>:0"],
      edges: [],
    });
  });

  test("readable stream", async () => {
    const { client, callSpy } = mockClient();

    const source = RunnableTraceable.from(
      traceable(async function (input: { text: string }) {
        const readStream = new ReadableStream({
          async pull(controller) {
            for (const item of input.text.split(" ")) {
              controller.enqueue(item);
            }
            controller.close();
          },
        });

        return readStream;
      })
    );

    const tokens: unknown[] = [];
    for await (const chunk of await source.stream(
      { text: "Hello world" },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore client might be of different type
      { callbacks: [new LangChainTracer({ client })] }
    )) {
      tokens.push(chunk);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["<lambda>:0"],
      edges: [],
    });
  });

  test("async generator stream", async () => {
    const { client, callSpy } = mockClient();
    const source = RunnableTraceable.from(
      traceable(async function* (input: { text: string }) {
        const chunks = input.text.split(" ");
        for (const chunk of chunks) {
          yield chunk;
        }
      })
    );

    const tokens: unknown[] = [];
    for await (const chunk of await source.stream(
      { text: "Hello world" },
      {
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore client might be of different type
        callbacks: [new LangChainTracer({ client })],
      }
    )) {
      tokens.push(chunk);
    }

    expect(tokens).toEqual(["Hello", "world"]);
    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["<lambda>:0"],
      edges: [],
    });
  });
});

test("explicit nested", async () => {
  const { client, callSpy } = mockClient();

  const llm = new FakeChatModel({});
  const prompt = ChatPromptTemplate.fromMessages<{ text: string }>([
    ["human", "{text}"],
  ]);
  const parser = new StringOutputParser();
  const chain = prompt.pipe(llm).pipe(parser).withConfig({ runName: "chain" });

  const wrappedModel = new RunnableTraceable({
    func: traceable(
      async (value: { input: string }) => {
        const callbacks = await getLangchainCallbacks();

        return chain.invoke(
          { text: `Wrapped input: ${value.input}` },
          { callbacks }
        );
      },
      { name: "wrappedModel" }
    ),
  });

  const main = traceable(
    async () => {
      return {
        response: [
          await wrappedModel.invoke(
            { input: "Are you ready?" },
            { callbacks: await getLangchainCallbacks() }
          ),
          await wrappedModel.invoke(
            { input: "I said, Are. You. Ready?" },
            { callbacks: await getLangchainCallbacks() }
          ),
        ],
      };
    },
    { name: "main", client, tracingEnabled: true }
  );

  const result = await main();
  await awaitAllCallbacks();

  expect(result).toEqual({
    response: [
      "Wrapped input: Are you ready?",
      "Wrapped input: I said, Are. You. Ready?",
    ],
  });

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client)
  ).toMatchObject({
    nodes: [
      "main:0",
      "wrappedModel:1",
      "chain:2",
      "ChatPromptTemplate:3",
      "FakeChatModel:4",
      "StrOutputParser:5",
      "wrappedModel:6",
      "chain:7",
      "ChatPromptTemplate:8",
      "FakeChatModel:9",
      "StrOutputParser:10",
    ],
    edges: [
      ["main:0", "wrappedModel:1"],
      ["wrappedModel:1", "chain:2"],
      ["chain:2", "ChatPromptTemplate:3"],
      ["chain:2", "FakeChatModel:4"],
      ["chain:2", "StrOutputParser:5"],
      ["main:0", "wrappedModel:6"],
      ["wrappedModel:6", "chain:7"],
      ["chain:7", "ChatPromptTemplate:8"],
      ["chain:7", "FakeChatModel:9"],
      ["chain:7", "StrOutputParser:10"],
    ],
  });
});

describe("LangChain context variables", () => {
  test.each(["true", "false"])(
    "set and get context variables at top level with tracingEnabled=%s",
    async (tracingEnabled) => {
      process.env.LANGSMITH_TRACING = tracingEnabled;
      const { client } = mockClient();
      setContextVariable("foo", "bar");
      expect(getContextVariable("foo")).toEqual("bar");

      const main = traceable(
        async () => {
          expect(getContextVariable("foo")).toEqual("bar");
          return "Something";
        },
        {
          client,
        }
      );
      await main();
      await awaitAllCallbacks();
    }
  );

  test.each(["true", "false"])(
    "set and get context variables from runnable nested in traceable with tracingEnabled=%s",
    async (tracingEnabled) => {
      process.env.LANGSMITH_TRACING = tracingEnabled;
      const { client } = mockClient();

      const nested = RunnableLambda.from(async () => {
        expect(getContextVariable("foo")).toEqual("baz");

        return "Something";
      });

      const main = traceable(
        async () => {
          setContextVariable("foo", "baz");
          expect(getContextVariable("foo")).toEqual("baz");
          return nested.invoke({});
        },
        {
          client,
        }
      );
      await main();
      await awaitAllCallbacks();
    }
  );

  test.each(["true", "false"])(
    "set and get context variables from traceable nested in runnable with tracingEnabled=%s",
    async (tracingEnabled) => {
      process.env.LANGSMITH_TRACING = tracingEnabled;
      const { client } = mockClient();

      const nested = traceable(
        async () => {
          expect(getContextVariable("foo")).toEqual("qux");
          return "Something";
        },
        {
          client,
        }
      );

      const main = RunnableLambda.from(async () => {
        setContextVariable("foo", "qux");
        expect(getContextVariable("foo")).toEqual("qux");
        return nested();
      });
      await main.invoke({});
      await awaitAllCallbacks();
    }
  );
});

// skip until the @langchain/core 0.2.17 is out
describe.skip("automatic tracing", () => {
  it("root langchain", async () => {
    const { callSpy, langChainTracer, client } = mockClient();

    const lc = RunnableLambda.from(async () => "Hello from LangChain");
    const ls = traceable(() => "Hello from LangSmith", { name: "traceable" });

    const childA = RunnableLambda.from(async () => {
      const results: string[] = [];
      results.push(await lc.invoke({}));
      results.push(await ls());
      return results.join("\n");
    });

    const childB = traceable(
      async () => [await lc.invoke({}), await ls()].join("\n"),
      { name: "childB" }
    );

    const rootLC = RunnableLambda.from(async () => {
      return [
        await childA.invoke({}, { runName: "childA" }),
        await childB(),
      ].join("\n");
    });

    expect(
      await rootLC.invoke(
        {},
        { callbacks: [langChainTracer], runName: "rootLC" }
      )
    ).toEqual(
      [
        "Hello from LangChain",
        "Hello from LangSmith",
        "Hello from LangChain",
        "Hello from LangSmith",
      ].join("\n")
    );

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "rootLC:0",
        "childA:1",
        "RunnableLambda:2",
        "traceable:3",
        "childB:4",
        "RunnableLambda:5",
        "traceable:6",
      ],
      edges: [
        ["rootLC:0", "childA:1"],
        ["childA:1", "RunnableLambda:2"],
        ["childA:1", "traceable:3"],
        ["rootLC:0", "childB:4"],
        ["childB:4", "RunnableLambda:5"],
        ["childB:4", "traceable:6"],
      ],
    });
  });

  it("root traceable", async () => {
    const { client, callSpy } = mockClient();

    const lc = RunnableLambda.from(async () => "Hello from LangChain");
    const ls = traceable(() => "Hello from LangSmith", { name: "traceable" });

    const childA = RunnableLambda.from(async () => {
      const results: string[] = [];
      results.push(await lc.invoke({}));
      results.push(await ls());
      return results.join("\n");
    });

    const childB = traceable(
      async () => [await lc.invoke({}), await ls()].join("\n"),
      { name: "childB" }
    );

    const rootLS = traceable(
      async () => {
        return [
          await childA.invoke({}, { runName: "childA" }),
          await childB(),
        ].join("\n");
      },
      { name: "rootLS", client, tracingEnabled: true }
    );

    expect(await rootLS()).toEqual(
      [
        "Hello from LangChain",
        "Hello from LangSmith",
        "Hello from LangChain",
        "Hello from LangSmith",
      ].join("\n")
    );

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "rootLS:0",
        "childA:1",
        "RunnableLambda:2",
        "traceable:3",
        "childB:4",
        "RunnableLambda:5",
        "traceable:6",
      ],
      edges: [
        ["rootLS:0", "childA:1"],
        ["childA:1", "RunnableLambda:2"],
        ["childA:1", "traceable:3"],
        ["rootLS:0", "childB:4"],
        ["childB:4", "RunnableLambda:5"],
        ["childB:4", "traceable:6"],
      ],
    });
  });
});
