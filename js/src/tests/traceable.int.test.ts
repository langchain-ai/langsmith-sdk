import { v4 as uuidv4 } from "uuid";
// eslint-disable-next-line import/no-extraneous-dependencies
import { FakeStreamingLLM } from "@langchain/core/utils/testing";
import { Client } from "../client.js";
import {
  getCurrentRunTree,
  isTraceableFunction,
  traceable,
} from "../traceable.js";
import { RunTree } from "../run_trees.js";

async function deleteProject(langchainClient: Client, projectName: string) {
  try {
    await langchainClient.readProject({ projectName });
    await langchainClient.deleteProject({ projectName });
  } catch (e) {
    // Pass
  }
}

async function waitUntil(
  condition: () => Promise<boolean>,
  timeout: number,
  interval: number
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await condition()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw new Error("Timeout");
}

async function waitUntilRunFound(
  client: Client,
  runId: string,
  checkOutputs = false
) {
  return waitUntil(
    async () => {
      try {
        const run = await client.readRun(runId);
        if (checkOutputs) {
          return (
            run.outputs !== null &&
            run.outputs !== undefined &&
            Object.keys(run.outputs).length !== 0
          );
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    30_000,
    5_000
  );
}

test.concurrent(
  "Test traceable wrapper",
  async () => {
    const langchainClient = new Client({
      callerOptions: { maxRetries: 0 },
    });
    const runId = uuidv4();
    const projectName = "__test_traceable_wrapper";
    const addValueTraceable = traceable(
      (a: string, b: number) => {
        return a + b;
      },
      {
        name: "add_value",
        project_name: projectName,
        client: langchainClient,
        id: runId,
      }
    );

    expect(await addValueTraceable("testing", 9)).toBe("testing9");
    expect(isTraceableFunction(addValueTraceable)).toBe(true);

    await waitUntilRunFound(langchainClient, runId, true);
    const storedRun = await langchainClient.readRun(runId);
    expect(storedRun.id).toEqual(runId);

    const runId2 = uuidv4();
    const nestedAddValueTraceable = traceable(
      (a: string, b: number) => {
        return a + b;
      },
      {
        name: "nested_add_value",
        project_name: projectName,
        client: langchainClient,
      }
    );
    const entryTraceable = traceable(
      async (complex: { value: string }) => {
        const result = await nestedAddValueTraceable(complex.value, 1);
        const result2 = await nestedAddValueTraceable(result, 2);
        await nestedAddValueTraceable(
          new RunTree({
            name: "root_nested_add_value",
            project_name: projectName,
            client: langchainClient,
          }),
          result,
          2
        );
        return nestedAddValueTraceable(result2, 3);
      },
      {
        name: "run_with_nesting",
        project_name: projectName,
        client: langchainClient,
        id: runId2,
      }
    );

    expect(await entryTraceable({ value: "testing" })).toBe("testing123");
    expect(isTraceableFunction(entryTraceable)).toBe(true);

    await waitUntilRunFound(langchainClient, runId2, true);
    const storedRun2 = await langchainClient.readRun(runId2);
    expect(storedRun2.id).toEqual(runId2);

    const runId3 = uuidv4();

    const llm = new FakeStreamingLLM({ sleep: 0 });

    const iterableTraceable = traceable(llm.stream.bind(llm), {
      name: "iterable_traceable",
      project_name: projectName,
      client: langchainClient,
      id: runId3,
    });
    expect(isTraceableFunction(iterableTraceable)).toBe(true);

    const chunks = [];

    for await (const chunk of await iterableTraceable("Hello there")) {
      chunks.push(chunk);
    }
    expect(chunks.join("")).toBe("Hello there");
    await waitUntilRunFound(langchainClient, runId3, true);
    const storedRun3 = await langchainClient.readRun(runId3);
    expect(storedRun3.id).toEqual(runId3);

    await deleteProject(langchainClient, projectName);

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
      project_name: projectName,
      client: langchainClient,
    });

    expect(await wrappedOverload("testing", 123)).toBe("testing123");
    expect(await wrappedOverload({ a: "testing", b: 456 })).toBe("testing456");
    expect(isTraceableFunction(wrappedOverload)).toBe(true);
  },
  180_000
);

test.concurrent("Test get run tree method", async () => {
  const langchainClient = new Client({
    callerOptions: { maxRetries: 0 },
  });
  // Called outside a traceable function
  expect(() => getCurrentRunTree()).toThrowError();
  const runId = uuidv4();
  const projectName = "__test_traceable_wrapper";
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
      project_name: projectName,
      client: langchainClient,
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
      project_name: projectName,
      client: langchainClient,
      id: runId,
    }
  );
  expect(await addValueTraceable("testing", 9)).toBe("testing9");
});
