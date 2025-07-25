/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../../../client.js";
import { evaluate } from "../../../evaluation/index.js";
import type { Run } from "../../../schemas.js";

// Initialize basic OTEL setup
import { initializeOTEL } from "../../../experimental/otel/setup.js";

const { DEFAULT_LANGSMITH_SPAN_PROCESSOR } = initializeOTEL();

beforeAll(() => {
  process.env.LANGSMITH_TRACING = "true";
  process.env.LANGSMITH_OTEL_ENABLED = "true";
});

afterAll(async () => {
  delete process.env.LANGSMITH_OTEL_ENABLED;
  delete process.env.LANGSMITH_TRACING;

  await DEFAULT_LANGSMITH_SPAN_PROCESSOR.shutdown();
});

describe.skip("AI SDK Evaluate Integration with OTEL", () => {
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
        key: "echo",
        value: JSON.stringify(run.inputs),
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
  });
});
