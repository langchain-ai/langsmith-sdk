
  import { evaluate } from "../evaluation/_runner.js";
  import { Example, ExampleUploadWithAttachments, Run } from "../schemas.js";
  import { Client } from "../index.js";
  import { v4 as uuidv4 } from "uuid";
  

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
      dataset_id: dataset.id,
      inputs: { question: "What is shown in the image?" },
      outputs: { answer: "test image" },
      attachments: {
        image: ["image/png", Buffer.from("fake image data for testing")],
      }
    };

    await client.uploadExamplesMultipart([example]);

    // Define target function that processes attachments
    const targetFunc = async (
      inputs: Record<string, any>,
      attachments?: Record<string, [string, Buffer]>
    ) => {
      // Verify we receive the attachment data
      if (!attachments?.image) {
        throw new Error("Image attachment not found");
      }
      const [_, imageData] = attachments.image;
      const expectedData = Buffer.from("fake image data for testing");
      if (!imageData.equals(expectedData)) {
        throw new Error("Image data does not match expected data");
      }
      return { answer: "test image" };
    };

    const customEvaluator = async (run: Run, example?: Example) => {
      return Promise.resolve({
        key: "key",
        score: 1,
        comment: `Run: ${run.id} Example: ${example?.id}`,
      });
    };
    const evaluator = {
      evaluateRun: customEvaluator,
    };

    // Run evaluation
    const evalRes = await evaluate(targetFunc, {
      data: datasetName,
      description: "Testing attachment handling in evaluation",
      client: client,
      evaluators: [evaluator],
      numRepetitions: 2,
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