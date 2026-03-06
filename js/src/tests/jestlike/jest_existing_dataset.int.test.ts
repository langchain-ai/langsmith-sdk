import { describe } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";

import { Client } from "../../client.js";
import * as ls from "../../jest/index.js";

describe("Existing dataset", () => {
  const client = new Client({ callerOptions: { maxRetries: 6 } });
  const datasetName = `__test_existing_dataset${uuidv4().slice(0, 4)}`;
  const exampleIds = [uuidv4(), uuidv4()];
  const exampleParams = [
    {
      id: exampleIds[0],
      inputs: { foo: "bar" },
      outputs: { foo: "bar" },
    },
    {
      id: exampleIds[1],
      inputs: { foo: "bar" },
      outputs: { foo: "bar" },
    },
  ];

  beforeAll(async () => {
    // Clean up existing dataset if it exists
    if (await client.hasDataset({ datasetName })) {
      await client.deleteDataset({ datasetName });
    }

    // Create actual dataset
    const dataset = await client.createDataset(datasetName, {
      description: "Test dataset for multipart example upload",
      dataType: "kv",
    });

    await client.createExamples([
      {
        ...exampleParams[0],
        dataset_id: dataset.id,
      },
      {
        ...exampleParams[1],
        dataset_id: dataset.id,
      },
    ]);
  });

  afterAll(async () => {
    await client.deleteDataset({ datasetName });
  });

  ls.describe(datasetName, () => {
    ls.test.each(exampleParams)(
      "Runs over existing dataset",
      async (example) => {
        expect(example.inputs.foo).toBe("bar");
        expect(example.outputs.foo).toBe("bar");
      }
    );
  });
});
