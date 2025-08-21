/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import { openai } from "@ai-sdk/openai";
import { generateObject, streamObject, streamText } from "ai";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../../../client.js";
import { traceable } from "../../../traceable.js";
import { getLangSmithEnvironmentVariable } from "../../../utils/env.js";
import { toArray, waitUntilRunFoundByMetaField } from "../../utils.js";

// Initialize basic OTEL setup
import { initializeOTEL } from "../../../experimental/otel/setup.js";

const { DEFAULT_LANGSMITH_SPAN_PROCESSOR } = initializeOTEL();

describe.skip("AI SDK Streaming Integration", () => {
  beforeAll(() => {
    process.env.LANGSMITH_TRACING = "true";
  });

  afterAll(async () => {
    delete process.env.LANGSMITH_OTEL_ENABLED;
    delete process.env.LANGSMITH_TRACING;
    await DEFAULT_LANGSMITH_SPAN_PROCESSOR.shutdown();
  });

  it("works with streamText", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";
    const meta = uuidv4();
    const client = new Client();

    const wrappedStreamText = traceable(
      async (prompt: string) => {
        const { textStream } = await streamText({
          model: openai("gpt-4.1-nano"),
          prompt,
          experimental_telemetry: {
            isEnabled: true,
          },
        });

        let fullText = "";
        for await (const textPart of textStream) {
          fullText += textPart;
        }

        return { text: fullText };
      },
      { name: "streamTextTest", metadata: { testKey: meta }, client }
    );

    const result = await wrappedStreamText("Say hello in exactly 3 words");
    expect(result.text).toBeTruthy();

    await client.awaitPendingTraceBatches();
    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(client, projectName, "testKey", meta);

    const storedRuns = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "testKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRuns.length).toBe(1);

    const runWithChildren = await client.readRun(storedRuns[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBeGreaterThan(0);
    expect(
      runWithChildren.child_runs?.some((run) => run.name === "ai.streamText")
    ).toBe(true);
    expect(runWithChildren.prompt_tokens).toBeGreaterThan(0);
    expect(runWithChildren.completion_tokens).toBeGreaterThan(0);
    expect(runWithChildren.total_tokens).toBeGreaterThan(0);
  });

  it("works with generateObject", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";
    const meta = uuidv4();
    const client = new Client();

    const schema = z.object({
      name: z.string(),
      age: z.number(),
      city: z.string(),
    });

    const wrappedGenerateObject = traceable(
      async (prompt: string) => {
        const { object } = await generateObject({
          model: openai("gpt-4.1-nano"),
          prompt,
          schema,
          experimental_telemetry: {
            isEnabled: true,
          },
        });

        return object;
      },
      { name: "generateObjectTest", metadata: { testKey: meta }, client }
    );

    const result = await wrappedGenerateObject(
      "Generate a person with name John, age 30, and city New York"
    );
    expect(result.name).toBe("John");
    expect(result.age).toBe(30);
    expect(result.city).toBe("New York");

    await client.awaitPendingTraceBatches();
    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(client, projectName, "testKey", meta);

    const storedRuns = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "testKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRuns.length).toBe(1);

    const runWithChildren = await client.readRun(storedRuns[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBeGreaterThan(0);
    expect(
      runWithChildren.child_runs?.some(
        (run) => run.name === "ai.generateObject"
      )
    ).toBe(true);
  });

  it("works with streamObject", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";
    const meta = uuidv4();
    const client = new Client();

    const schema = z.object({
      characters: z.array(
        z.object({
          name: z.string(),
          trait: z.string(),
        })
      ),
    });

    const wrappedStreamObject = traceable(
      async (prompt: string) => {
        const { partialObjectStream } = await streamObject({
          model: openai("gpt-4.1-nano"),
          prompt,
          schema,
          experimental_telemetry: {
            isEnabled: true,
          },
        });

        let finalObject: any = {};
        for await (const partialObject of partialObjectStream) {
          finalObject = partialObject;
        }

        return finalObject;
      },
      { name: "streamObjectTest", metadata: { testKey: meta }, client }
    );

    const result = await wrappedStreamObject(
      "Generate 2 fantasy characters with names and traits"
    );
    expect(result.characters).toBeDefined();
    expect(Array.isArray(result.characters)).toBe(true);

    await client.awaitPendingTraceBatches();
    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(client, projectName, "testKey", meta);

    const storedRuns = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "testKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRuns.length).toBe(1);

    const runWithChildren = await client.readRun(storedRuns[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBeGreaterThan(0);
    expect(
      runWithChildren.child_runs?.some((run) => run.name === "ai.streamObject")
    ).toBe(true);
  });
});
