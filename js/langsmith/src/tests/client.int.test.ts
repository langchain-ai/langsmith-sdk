import { Dataset, Run } from "../schemas.js";
import { FunctionMessage, HumanMessage } from "@langchain/core/messages";

import { Client } from "../client.js";
import { v4 as uuidv4 } from "uuid";
import { deleteDataset, deleteProject, toArray, waitUntil } from "./utils.js";

type CheckOutputsType = boolean | ((run: Run) => boolean);
async function waitUntilRunFound(
  client: Client,
  runId: string,
  checkOutputs: CheckOutputsType = false
) {
  return waitUntil(
    async () => {
      try {
        const run = await client.readRun(runId);
        if (checkOutputs) {
          const hasOutputs = run.outputs !== null && run.outputs !== undefined;
          if (typeof checkOutputs === "boolean") {
            return hasOutputs;
          } else if (typeof checkOutputs === "function") {
            return hasOutputs && checkOutputs(run);
          }
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    210_000,
    5_000
  );
}

// Test Dataset Creation, List, Read, Delete + upload CSV
// Test Example Creation, List, Read, Update, Delete
test.concurrent("Test LangSmith Client Dataset CRD", async () => {
  const client = new Client({ autoBatchTracing: false });

  const csvContent = `col1,col2,col3,col4\nval1,val2,val3,val4`;
  const blobData = new Blob([Buffer.from(csvContent)]);

  const description = "Test Dataset";
  const inputKeys = ["col1", "col3"];
  const outputKeys = ["col2", "col4"];
  const fileName = "__some_file.int.csv";
  await deleteDataset(client, fileName);
  const newDataset = await client.uploadCsv({
    csvFile: blobData,
    fileName: fileName,
    description,
    inputKeys,
    outputKeys,
  });
  expect(newDataset).toHaveProperty("id");
  expect(newDataset.description).toBe(description);

  const dataset = await client.readDataset({ datasetId: newDataset.id });
  const datasetId = dataset.id;
  const dataset2 = await client.readDataset({ datasetId });
  expect(dataset.id).toBe(dataset2.id);

  const datasets = await toArray(
    client.listDatasets({ datasetName: fileName })
  );
  expect(datasets.length).toBeGreaterThan(0);
  expect(datasets.map((d) => d.id)).toContain(datasetId);

  const example = await client.createExample(
    { col1: "addedExampleCol1" },
    { col2: "addedExampleCol2" },
    { datasetId: newDataset.id }
  );
  const exampleValue = await client.readExample(example.id);
  expect(exampleValue.inputs.col1).toBe("addedExampleCol1");
  expect(exampleValue.outputs?.col2).toBe("addedExampleCol2");

  const examples = await toArray(
    client.listExamples({ datasetId: newDataset.id })
  );
  expect(examples.length).toBe(2);
  expect(examples.map((e) => e.id)).toContain(example.id);

  await client.updateExample(example.id, {
    inputs: { col1: "updatedExampleCol1" },
    outputs: { col2: "updatedExampleCol2" },
  });
  // Says 'example updated' or something similar
  const newExampleValue = await client.readExample(example.id);
  expect(newExampleValue.inputs.col1).toBe("updatedExampleCol1");
  await client.deleteExample(example.id);
  const examples2 = await toArray(
    client.listExamples({ datasetId: newDataset.id })
  );
  expect(examples2.length).toBe(1);

  await client.deleteDataset({ datasetId });
  const rawDataset = await client.createDataset(fileName, {
    description: "Test Dataset",
  });
  await client.deleteDataset({ datasetId: rawDataset.id });
});

test.concurrent(
  "test create dataset",
  async () => {
    const langchainClient = new Client({ autoBatchTracing: false });
    const datasetName = "__test_create_dataset JS";
    const datasets = await toArray(
      langchainClient.listDatasets({ datasetName })
    );
    datasets.map(async (dataset: Dataset) => {
      if (dataset.name === datasetName) {
        await langchainClient.deleteDataset({ datasetName });
      }
    });
    const dataset = await langchainClient.createDataset(datasetName, {
      dataType: "llm",
    });
    await langchainClient.createExample(
      { input: "hello world" },
      { output: "hi there" },
      {
        datasetId: dataset.id,
      }
    );
    const loadedDataset = await langchainClient.readDataset({ datasetName });
    expect(loadedDataset.data_type).toEqual("llm");
    await langchainClient.deleteDataset({ datasetName });
  },
  180_000
);

test.concurrent(
  "Test share and unshare run",
  async () => {
    const langchainClient = new Client({ autoBatchTracing: false });

    // Create a new run
    const runId = uuidv4();
    await langchainClient.createRun({
      name: "Test run",
      inputs: { input: "hello world" },
      run_type: "chain",
      id: runId,
    });

    await waitUntilRunFound(langchainClient, runId);
    const sharedUrl = await langchainClient.shareRun(runId);
    const response = await fetch(sharedUrl);
    expect(response.status).toEqual(200);
    expect(await langchainClient.readRunSharedLink(runId)).toEqual(sharedUrl);

    await langchainClient.unshareRun(runId);
    const sharedLink = await langchainClient.readRunSharedLink(runId);
    expect(sharedLink).toBe(undefined);
  },
  180_000
);

test.concurrent(
  "Test list datasets",
  async () => {
    const langchainClient = new Client({ autoBatchTracing: false });
    const datasetName1 = "___TEST dataset1 JS";
    const datasetName2 = "___TEST dataset2 JS";
    await deleteDataset(langchainClient, datasetName1);
    await deleteDataset(langchainClient, datasetName2);
    // Create two new datasets
    const dataset1 = await langchainClient.createDataset(datasetName1, {
      dataType: "llm",
    });
    const dataset2 = await langchainClient.createDataset(datasetName2, {
      dataType: "kv",
    });

    // List datasets by ID
    const datasetsById: Dataset[] = [];
    const datasetsByIdIterable = langchainClient.listDatasets({
      datasetIds: [dataset1.id, dataset2.id],
    });
    for await (const dataset of datasetsByIdIterable) {
      datasetsById.push(dataset);
    }
    expect(datasetsById).toHaveLength(2);
    expect(datasetsById.map((dataset) => dataset.id)).toContain(dataset1.id);
    expect(datasetsById.map((dataset) => dataset.id)).toContain(dataset2.id);

    // List datasets by name
    const datasetsByNameIterable = langchainClient.listDatasets({
      datasetName: datasetName1,
    });
    const datasetsByName = [];
    for await (const dataset of datasetsByNameIterable) {
      datasetsByName.push(dataset);
    }
    expect(datasetsByName).toHaveLength(1);
    expect(datasetsByName.map((dataset) => dataset.id)).toContain(dataset1.id);

    await langchainClient.deleteDataset({ datasetId: dataset1.id });
    await langchainClient.deleteDataset({ datasetId: dataset2.id });
  },
  180_000
);

test.concurrent(
  "Test create feedback with source run",
  async () => {
    const langchainClient = new Client({ autoBatchTracing: false });
    const projectName = "__test_create_feedback_with_source_run JS";
    await deleteProject(langchainClient, projectName);
    const runId = uuidv4();
    await langchainClient.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { prompt: "hello world" },
      outputs: { generation: "hi there" },
      start_time: new Date().getTime(),
      end_time: new Date().getTime(),
    });

    const runId2 = uuidv4();
    await langchainClient.createRun({
      id: runId2,
      project_name: projectName,
      name: "test_run_2",
      run_type: "llm",
      inputs: { prompt: "hello world 2" },
      outputs: { generation: "hi there 2" },
      start_time: new Date().getTime(),
      end_time: new Date().getTime(),
    });

    await langchainClient.createFeedback(runId, "test_feedback", {
      score: 0.5,
      sourceRunId: runId2,
      feedbackSourceType: "app",
    });
  },
  180_000
);

test.concurrent(
  "Test create run with masked inputs/outputs",
  async () => {
    const langchainClient = new Client({
      hideInputs: true,
      hideOutputs: true,
      autoBatchTracing: false,
    });
    const projectName = "__test_create_run_with_masked_inputs_outputs JS";
    await deleteProject(langchainClient, projectName);
    const runId = uuidv4();
    await langchainClient.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { prompt: "hello world" },
      outputs: { generation: "hi there" },
      start_time: new Date().getTime(),
      end_time: new Date().getTime(),
    });

    const runId2 = uuidv4();
    await langchainClient.createRun({
      id: runId2,
      project_name: projectName,
      name: "test_run_2",
      run_type: "llm",
      inputs: { messages: "hello world 2" },
      start_time: new Date().getTime(),
    });

    await langchainClient.updateRun(runId2, {
      outputs: { generation: "hi there 2" },
      end_time: new Date().getTime(),
    });
    await waitUntilRunFound(langchainClient, runId, false);
    const run1 = await langchainClient.readRun(runId);
    expect(Object.keys(run1.inputs ?? {})).toHaveLength(0);
    expect(Object.keys(run1.outputs ?? {})).toHaveLength(0);
    await waitUntilRunFound(langchainClient, runId2, false);
    const run2 = await langchainClient.readRun(runId2);
    expect(Object.keys(run2.inputs ?? {})).toHaveLength(0);
    expect(Object.keys(run2.outputs ?? {})).toHaveLength(0);
  },
  240_000
);

test.concurrent(
  "Test create run with revision id",
  async () => {
    const langchainClient = new Client({ autoBatchTracing: false });
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_REVISION_ID = "test_revision_id";
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_OTHER_FIELD = "test_other_field";
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_OTHER_KEY = "test_other_key";
    const projectName = "__test_create_run_with_revision_id JS";
    await deleteProject(langchainClient, projectName);
    const runId = uuidv4();
    await langchainClient.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run_with_revision",
      run_type: "llm",
      inputs: { prompt: "hello world" },
      outputs: { generation: "hi there" },
      start_time: new Date().getTime(),
      end_time: new Date().getTime(),
    });

    const runId2 = uuidv4();
    await langchainClient.createRun({
      id: runId2,
      project_name: projectName,
      name: "test_run_2_with_revision",
      run_type: "llm",
      inputs: { messages: "hello world 2" },
      start_time: new Date().getTime(),
      revision_id: "different_revision_id",
    });
    await waitUntilRunFound(
      langchainClient,
      runId,
      (run: Run | undefined) => Object.keys(run?.outputs || {}).length !== 0
    );
    const run1 = await langchainClient.readRun(runId);
    expect(run1.extra?.metadata?.revision_id).toEqual("test_revision_id");
    expect(run1.extra?.metadata.LANGCHAIN_OTHER_FIELD).toEqual(
      "test_other_field"
    );
    expect(run1.extra?.metadata.LANGCHAIN_OTHER_KEY).toBeUndefined();
    expect(run1.extra?.metadata).not.toHaveProperty("LANGCHAIN_API_KEY");
    await waitUntilRunFound(langchainClient, runId2);
    const run2 = await langchainClient.readRun(runId2);
    expect(run2.extra?.metadata?.revision_id).toEqual("different_revision_id");
    expect(run2.extra?.metadata.LANGCHAIN_OTHER_FIELD).toEqual(
      "test_other_field"
    );
    expect(run2.extra?.metadata.LANGCHAIN_OTHER_KEY).toBeUndefined();
    expect(run2.extra?.metadata).not.toHaveProperty("LANGCHAIN_API_KEY");
  },
  180_000
);

describe("createChatExample", () => {
  it("should convert LangChainBaseMessage objects to examples", async () => {
    const langchainClient = new Client({
      autoBatchTracing: false,
      // Test the fetch options option
      fetchOptions: { cache: "no-store" },
    });

    const datasetName = "__createChatExample-test-dataset JS";
    await deleteDataset(langchainClient, datasetName);
    const dataset = await langchainClient.createDataset(datasetName);

    const input = [new HumanMessage({ content: "Hello, world!" })];
    const generation = new FunctionMessage({
      name: "foo",
      content: "",
      additional_kwargs: {
        function_call: { arguments: "args", name: "foo" },
      },
    });
    const options = { datasetId: dataset.id };

    // Create the example from messages
    await langchainClient.createChatExample(input, generation, options);

    // Read the example
    const examples = [];
    for await (const example of langchainClient.listExamples({
      datasetId: dataset.id,
    })) {
      examples.push(example);
    }
    expect(examples.length).toBe(1);
    expect(examples[0].inputs).toEqual({
      input: [
        {
          type: "human",
          data: { content: "Hello, world!" },
        },
      ],
    });
    expect(examples[0].outputs).toEqual({
      output: {
        type: "function",
        data: {
          content: "",
          additional_kwargs: {
            function_call: { arguments: "args", name: "foo" },
          },
        },
      },
    });

    // Delete dataset
    await langchainClient.deleteDataset({ datasetId: dataset.id });
  }, 180_000);
});

test.concurrent(
  "Test getRunUrl with run",
  async () => {
    const client = new Client({ autoBatchTracing: false });
    const runId = uuidv4();
    const run: Run = {
      id: runId,
      name: "foo",
      run_type: "llm",
      inputs: { input: "hello world" },
      outputs: { output: "hi there" },
    };
    await client.createRun({ project_name: "foo", ...run });
    await waitUntilRunFound(
      client,
      runId,
      (run: Run | undefined) => Object.keys(run?.outputs || {}).length !== 0
    );
    const result = await client.getRunUrl({
      run,
      projectOpts: { projectName: "foo" },
    });
    expect(result).toContain(runId);
  },
  180_000
);

test.concurrent(
  "Examples CRUD",
  async () => {
    const client = new Client({ autoBatchTracing: false });
    const datasetName = "__test_examples_crud JS" + Date.now();
    await deleteDataset(client, datasetName);
    const dataset = await client.createDataset(datasetName);
    const example = await client.createExample(
      { input: "hello world" },
      { output: "hi there" },
      {
        datasetId: dataset.id,
        metadata: { key: "value" },
      }
    );
    const exampleValue = await client.readExample(example.id);
    const initialVersion = exampleValue.modified_at;
    expect(exampleValue.inputs.input).toEqual("hello world");
    expect(exampleValue?.outputs?.output).toEqual("hi there");
    expect(exampleValue?.metadata?.key).toEqual("value");

    // Update the example by modifying the metadata
    await client.updateExample(example.id, {
      metadata: { key: "new value" },
    });
    const updatedExampleValue = await client.readExample(example.id);
    expect(updatedExampleValue?.metadata?.key).toEqual("new value");

    // Create multiple
    await client.createExamples({
      inputs: [
        { input: "hello world 1" },
        { input: "hello world 2" },
        { input: "hello world 3" },
      ],
      outputs: [
        { output: "hi there 1" },
        { output: "hi there 2" },
        { output: "hi there 3" },
      ],
      metadata: [{ key: "value 1" }, { key: "value 2" }, { key: "value 3" }],
      datasetId: dataset.id,
    });
    const initialExamplesList = await toArray(
      client.listExamples({ datasetId: dataset.id, asOf: initialVersion })
    );
    expect(initialExamplesList.length).toEqual(1);
    const examplesList = await toArray(
      client.listExamples({ datasetId: dataset.id })
    );
    expect(examplesList.length).toEqual(4);
    await client.deleteExample(example.id);
    const examplesList2 = await toArray(
      client.listExamples({ datasetId: dataset.id })
    );
    expect(examplesList2.length).toEqual(3);
    const datasetDiff = await client.diffDatasetVersions({
      datasetId: dataset.id,
      fromVersion: initialVersion,
      toVersion: "latest",
    });
    expect(datasetDiff.examples_added.length).toEqual(3);
    expect(datasetDiff.examples_modified.length).toEqual(0);
    expect(datasetDiff.examples_removed.length).toEqual(1);

    // verify the example inputs, outputs, and metadata
    const example1 = examplesList2.find(
      (e) => e.inputs.input === "hello world 1"
    );
    expect(example1?.outputs?.output).toEqual("hi there 1");
    expect(example1?.metadata?.key).toEqual("value 1");
    const example2 = examplesList2.find(
      (e) => e.inputs.input === "hello world 2"
    );
    expect(example2?.outputs?.output).toEqual("hi there 2");
    expect(example2?.metadata?.key).toEqual("value 2");
    const example3 = examplesList2.find(
      (e) => e.inputs.input === "hello world 3"
    );
    expect(example3?.outputs?.output).toEqual("hi there 3");
    expect(example3?.metadata?.key).toEqual("value 3");

    await client.deleteDataset({ datasetId: dataset.id });
  },
  180_000
);
