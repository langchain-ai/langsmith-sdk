import { v4 as uuidv4 } from "uuid";
import { FakeStreamingLLM } from "@langchain/core/utils/testing";
import { Client } from "../client.js";
import { traceable } from "../traceable.js";
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

    const chunks = [];

    for await (const chunk of await iterableTraceable("Hello there")) {
      chunks.push(chunk);
    }
    expect(chunks.join("")).toBe("Hello there");
    await waitUntilRunFound(langchainClient, runId3, true);
    const storedRun3 = await langchainClient.readRun(runId3);
    expect(storedRun3.id).toEqual(runId3);

    await deleteProject(langchainClient, projectName);
  },
  180_000
);
