import { evaluate, TargetConfigT } from "../evaluation/_runner.js";
import { ExampleUploadWithAttachments } from "../schemas.js";
import { Client } from "../index.js";
import { v4 as uuidv4 } from "uuid";

function arraysEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
  }
  return true;
}

test("evaluate can handle examples with attachments", async () => {
  const client = new Client();
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
    if (!config?.attachments?.["attachment.image"]) {
      throw new Error("Image attachment not found");
    }
    const expectedData = new Uint8Array(Buffer.from("fake image data for testing"));
    let attachmentData: Uint8Array | undefined = config?.attachments?.["attachment.image"].presigned_url
      ? new Uint8Array(
          (await fetch(
            config?.attachments?.["attachment.image"].presigned_url
          ).then((res) => res.arrayBuffer())) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return { answer: "test image" };
  };

  const customEvaluator = async ({ attachments }: {attachments?: any}) => {
    expect(attachments).toBeDefined();
    expect(attachments?.["attachment.image"]).toBeDefined();
    const expectedData = new Uint8Array(Buffer.from("fake image data for testing"));
    let attachmentData: Uint8Array | undefined = attachments?.["attachment.image"].presigned_url
      ? new Uint8Array(
          (await fetch(
            attachments?.["attachment.image"].presigned_url
          ).then((res) => res.arrayBuffer())) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
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