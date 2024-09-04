import { KVMap, ExampleSearch } from "../schemas.js";
import { Client } from "../index.js";
import { v4 as uuidv4 } from "uuid";

const TESTING_DATASET_NAME = `test_dataset_few_shot_js_${uuidv4()}`;

test("few shot search", async () => {
  const client = new Client();

  const schema: KVMap = {
    type: "object",
    properties: {
      name: { type: "string" },
    },
    required: ["name"],
    additionalProperties: false,
  };

  const has_dataset = await client.hasDataset({
    datasetName: TESTING_DATASET_NAME,
  });
  if (has_dataset === true) {
    await client.deleteDataset({ datasetName: TESTING_DATASET_NAME });
  }

  const dataset = await client.createDataset(TESTING_DATASET_NAME, {
    description:
      "For testing purposed. Is created & deleted for each test run.",
    inputsSchema: schema,
  });

  // create examples
  const res = await client.createExamples({
    inputs: [{ name: "foo" }, { name: "bar" }],
    outputs: [{ output: 2 }, { output: 3 }],
    metadata: [{ somekey: "somevalue" }, { somekey: "someothervalue" }],
    datasetName: TESTING_DATASET_NAME,
  });
  if (res.length !== 2) {
    throw new Error("Failed to create examples");
  }

  await client.indexDataset({ datasetId: dataset.id });

  let i = 0;
  let examples: ExampleSearch[] = [];
  while (i < 10) {
    examples = await client.similarExamples(
      { name: "foo" },
      dataset.id,
      // specify limit of 5 so you return all examples
      5
    );
    if (examples.length === 2) {
      break;
    }

    // sleep for one second
    await new Promise((r) => setTimeout(r, 1000));
    i++;
  }

  expect(examples.length).toBe(2);
  expect(examples[0].inputs).toEqual({ name: "foo" });
  expect(examples[1].inputs).toEqual({ name: "bar" });

  const filtered_examples = await client.similarExamples(
    { name: "foo" },
    dataset.id,
    1,
    {
      filter: "eq(metadata.somekey, 'somevalue')",
    }
  );

  expect(filtered_examples.length).toBe(1);
  expect(filtered_examples[0].inputs).toEqual({ name: "foo" });
});
