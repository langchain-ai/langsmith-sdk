/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../../../client.js";
import { evaluate } from "../../../evaluation/index.js";
import { getLangSmithEnvironmentVariable } from "../../../utils/env.js";
import { toArray, waitUntilRunFoundByMetaField } from "../../utils.js";
import type { Run } from "../../../schemas.js";

// Initialize basic OTEL setup
import { initializeOTEL } from "../../../experimental/otel/setup.js";

initializeOTEL();

describe.skip("AI SDK Evaluate Integration with OTEL", () => {
  beforeAll(() => {
    process.env.LANGSMITH_TRACING = "true";
    process.env.OTEL_ENABLED = "true";
  });

  afterAll(() => {
    delete process.env.OTEL_ENABLED;
    delete process.env.LANGSMITH_TRACING;
  });

  it("works with evaluate() using generateText target function", async () => {
    const meta = uuidv4();
    const client = new Client();

    // Create a dataset for this test
    const datasetName = `ai-sdk-generatetext-${meta}`;
    const dataset = await client.createDataset(datasetName);

    // Create examples in the dataset
    const examples = [
      {
        inputs: { prompt: "Say hello in exactly 2 words" },
        outputs: { response: "Hello there" },
      },
      {
        inputs: { prompt: "Count to 3" },
        outputs: { response: "1, 2, 3" },
      },
    ];

    for (const example of examples) {
      await client.createExample({
        inputs: example.inputs,
        outputs: example.outputs,
        dataset_id: dataset.id,
      });
    }

    // Create a target function that uses AI SDK generateText
    const generateTextTarget = async (input: { prompt: string }) => {
      const { text } = await generateText({
        model: openai("gpt-4.1-nano"),
        prompt: input.prompt,
        experimental_telemetry: {
          isEnabled: true,
        },
      });

      return { response: text };
    };

    // Create a simple evaluator
    const evaluator = async (run: Run) => {
      return {
        key: "response_present",
        score: run.outputs?.response ? 1 : 0,
        comment: `Response present: ${!!run.outputs?.response}`,
      };
    };

    // Run evaluation with metadata for tracking
    const results = await evaluate(generateTextTarget, {
      data: datasetName,
      evaluators: [evaluator],
      description: "AI SDK generateText evaluation test",
      metadata: { testKey: meta },
      client,
    });

    // Verify results
    expect(results.results.length).toBe(2);
    expect(results.results.every((r) => r.run.outputs?.response)).toBe(true);

    await client.awaitPendingTraceBatches();
    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(client, projectName, "testKey", meta);

    // Verify traces were created
    const storedRuns = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "testKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRuns.length).toBeGreaterThan(0);

    // Check that AI SDK traces are present
    const runWithChildren = await client.readRun(storedRuns[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBeGreaterThan(0);
    expect(
      runWithChildren.child_runs?.some((run) => run.name === "ai.generateText")
    ).toBe(true);

    // Cleanup
    await client.deleteDataset({ datasetId: dataset.id });
  });
});
