import { evaluate, TargetConfigT } from "../evaluation/_runner.js";
import { ExampleUploadWithAttachments } from "../schemas.js";
import { Client } from "../index.js";
import { v4 as uuidv4 } from "uuid";
import { RunnableLambda } from "@langchain/core/runnables";

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
    },
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
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentMimeType = config?.attachments?.image.mime_type;
    if (attachmentMimeType !== "image/png") {
      throw new Error("Image attachment has incorrect mime type");
    }
    const attachmentData: Uint8Array | undefined = config?.attachments?.[
      "image"
    ].presigned_url
      ? new Uint8Array(
          (await fetch(config?.attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return { answer: "test image" };
  };

  const customEvaluator = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeDefined();
    expect(attachments?.image).toBeDefined();
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentMimeType = attachments?.image.mime_type;
    if (attachmentMimeType !== "image/png") {
      throw new Error("Image attachment has incorrect mime type");
    }
    const attachmentData: Uint8Array | undefined = attachments?.image
      .presigned_url
      ? new Uint8Array(
          (await fetch(attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
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
    includeAttachments: true,
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    // TODO: Uncomment when attachments are traced correctly
    // expect(result.run.attachments).toBeDefined();
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();

    // Verify evaluator results
    const evalResults = result.evaluationResults.results;
    expect(evalResults).toHaveLength(1); // Should have attachment_presence and attachment_processing results

    // Check that attachments were properly processed
    const evalResult = evalResults.find((r) => r.key === "key");
    expect(evalResult?.score).toBe(1);
  }

  // Cleanup
  await client.deleteDataset({ datasetName });
});

test("evaluate with attachments not in target function", async () => {
  const client = new Client();
  const datasetName = `test_dataset_attachments_${uuidv4()}`;
  const dataset = await client.createDataset(datasetName);

  // Create examples with attachments
  const example: ExampleUploadWithAttachments = {
    inputs: { question: "What is shown in the image?" },
    outputs: { answer: "test image" },
    attachments: {
      image: ["image/png", Buffer.from("fake image data for testing")],
    },
  };

  await client.uploadExamplesMultipart(dataset.id, [example]);

  // Define target function that processes attachments
  const targetFunc = async (_inputs: Record<string, any>) => {
    return { answer: "test image" };
  };

  const customEvaluator = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeDefined();
    expect(attachments?.image).toBeDefined();
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = attachments?.image
      .presigned_url
      ? new Uint8Array(
          (await fetch(attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
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
    includeAttachments: true,
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    // TODO: Uncomment when attachments are traced correctly
    // expect(result.run.attachments).toBeDefined();
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();

    // Verify evaluator results
    const evalResults = result.evaluationResults.results;
    expect(evalResults).toHaveLength(1); // Should have attachment_presence and attachment_processing results

    // Check that attachments were properly processed
    const evalResult = evalResults.find((r) => r.key === "key");
    expect(evalResult?.score).toBe(1);
  }

  // Cleanup
  await client.deleteDataset({ datasetName });
});

test("multiple evaluators with attachments", async () => {
  const client = new Client();
  const datasetName = `test_dataset_attachments_${uuidv4()}`;
  const dataset = await client.createDataset(datasetName);

  // Create examples with attachments
  const example: ExampleUploadWithAttachments = {
    inputs: { question: "What is shown in the image?" },
    outputs: { answer: "test image" },
    attachments: {
      image: ["image/png", Buffer.from("fake image data for testing")],
    },
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
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = config?.attachments?.[
      "image"
    ].presigned_url
      ? new Uint8Array(
          (await fetch(config?.attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return { answer: "test image" };
  };

  const customEvaluatorOne = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeDefined();
    expect(attachments?.image).toBeDefined();
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = attachments?.image
      .presigned_url
      ? new Uint8Array(
          (await fetch(attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return {
      key: "key1",
      score: 1,
    };
  };

  const customEvaluatorTwo = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeDefined();
    expect(attachments?.image).toBeDefined();
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = attachments?.image
      .presigned_url
      ? new Uint8Array(
          (await fetch(attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return {
      key: "key2",
      score: 1,
    };
  };

  // Run evaluation
  const evalRes = await evaluate(targetFunc, {
    data: datasetName,
    description: "Testing attachment handling in evaluation",
    client: client,
    evaluators: [customEvaluatorOne, customEvaluatorTwo],
    numRepetitions: 2,
    includeAttachments: true,
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    // TODO: Uncomment when attachments are traced correctly
    // expect(result.run.attachments).toBeDefined();
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();

    // Verify evaluator results
    const evalResults = result.evaluationResults.results;
    expect(evalResults).toHaveLength(2); // Should have attachment_presence and attachment_processing results

    // Check that attachments were properly processed
    const evalResult1 = evalResults.find((r) => r.key === "key1");
    expect(evalResult1?.score).toBe(1);
    const evalResult2 = evalResults.find((r) => r.key === "key2");
    expect(evalResult2?.score).toBe(1);
  }

  // Cleanup
  await client.deleteDataset({ datasetName });
});

test("evaluate with attachments runnable target function", async () => {
  const client = new Client();
  const datasetName = `test_dataset_attachments_${uuidv4()}`;
  const dataset = await client.createDataset(datasetName);

  // Create examples with attachments
  const example: ExampleUploadWithAttachments = {
    inputs: { question: "What is shown in the image?" },
    outputs: { answer: "test image" },
    attachments: {
      image: ["image/png", Buffer.from("fake image data for testing")],
    },
  };

  await client.uploadExamplesMultipart(dataset.id, [example]);

  const myFunction = async (_input: any, config?: any) => {
    if (!config?.attachments?.image) {
      throw new Error("Image attachment not found");
    }
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = config?.attachments?.[
      "image"
    ].presigned_url
      ? new Uint8Array(
          (await fetch(config?.attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
        )
      : undefined;
    if (!arraysEqual(attachmentData ?? new Uint8Array(), expectedData)) {
      throw new Error("Image data does not match expected data");
    }
    return { answer: "test image" };
  };

  // Define target function that processes attachments
  const targetFunc = RunnableLambda.from(myFunction);

  const customEvaluator = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeDefined();
    expect(attachments?.image).toBeDefined();
    const expectedData = new Uint8Array(
      Buffer.from("fake image data for testing")
    );
    const attachmentData: Uint8Array | undefined = attachments?.image
      .presigned_url
      ? new Uint8Array(
          (await fetch(attachments?.image.presigned_url).then((res) =>
            res.arrayBuffer()
          )) as ArrayBuffer
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
    includeAttachments: true,
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);

  for (const result of evalRes.results) {
    // TODO: Uncomment when attachments are traced correctly
    // expect(result.run.attachments).toBeDefined();
    expect(result.run).toBeDefined();
    expect(result.example).toBeDefined();
    expect(result.evaluationResults).toBeDefined();

    // Verify evaluator results
    const evalResults = result.evaluationResults.results;
    expect(evalResults).toHaveLength(1); // Should have attachment_presence and attachment_processing results

    // Check that attachments were properly processed
    const evalResult = evalResults.find((r) => r.key === "key");
    expect(evalResult?.score).toBe(1);
  }

  // Cleanup
  await client.deleteDataset({ datasetName });
});

test("attachments don't appear without includeAttachments", async () => {
  const client = new Client();
  const datasetName = `test_dataset_attachments_${uuidv4()}`;
  const dataset = await client.createDataset(datasetName);

  // Create examples with attachments
  const example: ExampleUploadWithAttachments = {
    inputs: { question: "What is shown in the image?" },
    outputs: { answer: "test image" },
    attachments: {
      image: ["image/png", Buffer.from("fake image data for testing")],
    },
  };

  await client.uploadExamplesMultipart(dataset.id, [example]);

  const myFunction = async (_input: any, config?: any) => {
    if (config?.attachments) {
      throw new Error("Attachments should not exist!");
    }
    return { answer: "test image" };
  };

  // Define target function that processes attachments
  const targetFunc = RunnableLambda.from(myFunction);

  const customEvaluator = async ({ attachments }: { attachments?: any }) => {
    expect(attachments).toBeUndefined();
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
  });

  // Verify results
  expect(evalRes.results).toHaveLength(2);

  // Cleanup
  await client.deleteDataset({ datasetName });
});
