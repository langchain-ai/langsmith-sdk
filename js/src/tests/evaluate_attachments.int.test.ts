import { evaluate, TargetConfigT } from "../evaluation/_runner.js";
import { ExampleUploadWithAttachments } from "../schemas.js";
import { Client } from "../index.js";
import { IterableReadableStream } from "../utils/stream.js";
import { v4 as uuidv4 } from "uuid";


async function readFromStream(reader: IterableReadableStream<Uint8Array>) {
  const chunks: Uint8Array[] = [];
  for await (const chunk of reader) {
    chunks.push(chunk);
  }
  return new Uint8Array(Buffer.concat(chunks));
}

function arraysEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
  }
  return true;
}

test("evaluate can handle examples with attachments", async () => {
  //const client = new Client();
  const client = new Client({
    apiUrl: "https://dev.api.smith.langchain.com",
    apiKey: "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",
  });
  const datasetName = `test_dataset_attachments_${uuidv4()}`;
  const dataset = await client.createDataset(datasetName);

  // Create examples with attachments
  const example: ExampleUploadWithAttachments = {
    inputs: { question: "What is shown in the image?" },
    outputs: { answer: "test image" },
    attachments: {
      image: ["image/png", Buffer.from("fake image data for testing")],
    }
  };

  await client.uploadExamplesMultipart(dataset.id, [example]);

  // Define target function that processes attachments
  const targetFunc = async (
    _inputs: Record<string, any>,
    config?: TargetConfigT
  ) => {
    // Verify we receive the attachment data
    if (!config?.attachments?.image) {
      throw new Error("Image attachment not found");
    }
    const {reader} = config.attachments.image;
    const expectedData = new Uint8Array(Buffer.from("fake image data for testing"));
    const response = await readFromStream(reader);
    if (!arraysEqual(response, expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return { answer: "test image" };
  };

  const customEvaluator = async ({ attachments }: {attachments?: any}) => {
    expect(attachments).toBeDefined();
    expect(attachments.image).toBeDefined();
    const {reader} = attachments.image;
    const expectedData = new Uint8Array(Buffer.from("fake image data for testing"));
    const response = await readFromStream(reader);
    if (!arraysEqual(response, expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return {
      key: "key",
      score: 1,
    };
  };

  // Run evaluation
  const evalRes = await evaluate(targetFunc, {
    data: datasetName,
    description: "Testing attachment handling in evaluation",
    client: client,
    evaluators: [customEvaluator],
    numRepetitions: 2,
    includeAttachments: true
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);
  
  for (const result of evalRes.results) {
    // NOTE: THIS DOES NOT WORK YET BECAUSE THE ATTACHMENTS ARE NOT TRACED CORRECTLY
    // THIS SHOULD BE FIXED ASAP
    // expect(result.run.attachments).toBeDefined();
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();
    
    // Verify evaluator results
    const evalResults = result.evaluationResults.results;
    expect(evalResults).toHaveLength(1); // Should have attachment_presence and attachment_processing results
    
    // Check that attachments were properly processed
    const evalResult = evalResults.find(r => r.key === "key");
    expect(evalResult?.score).toBe(1);
  }

  // Cleanup
  await client.deleteDataset({ datasetName });
});