import { Dataset, Feedback, Run } from "../schemas.js";
import { FunctionMessage, HumanMessage } from "langchain/schema";
import { RunTree, RunTreeConfig } from "../run_trees.js";

import { Client } from "../client.js";
import { StringEvaluator } from "../evaluation/string_evaluator.js";
import { v4 as uuidv4 } from "uuid";

async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

// Test Dataset Creation, List, Read, Delete + upload CSV
// Test Example Creation, List, Read, Update, Delete
test.concurrent("Test LangSmith Client Dataset CRD", async () => {
  const client = new Client({});

  const csvContent = `col1,col2,col3,col4\nval1,val2,val3,val4`;
  const blobData = new Blob([Buffer.from(csvContent)]);

  const description = "Test Dataset";
  const inputKeys = ["col1", "col3"];
  const outputKeys = ["col2", "col4"];
  const fileName = "__some_file.int.csv";
  const existingDatasets = await toArray(client.listDatasets());
  if (existingDatasets.map((d) => d.name).includes(fileName)) {
    await client.deleteDataset({ datasetName: fileName });
  }

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

  const datasets = await toArray(client.listDatasets({}));
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

  const newExampleResponse = await client.updateExample(example.id, {
    inputs: { col1: "updatedExampleCol1" },
    outputs: { col2: "updatedExampleCol2" },
  });
  // Says 'example updated' or something similar
  console.log(newExampleResponse);
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

// Test Project Creation, List, Read, Delete
test.concurrent("Test LangSmith Client Project CRD", async () => {
  const client = new Client({});

  const newProject = `__some_project.int.`;
  if (
    (await toArray(client.listProjects()))
      .map((s) => s.name)
      .includes(newProject)
  ) {
    await client.deleteProject({ projectName: newProject });
  }

  let projects = await toArray(client.listProjects());
  let projectNames = projects.map((project) => project.name);
  expect(projectNames).not.toContain(newProject);

  await client.createProject({ projectName: newProject });
  const project = await client.readProject({ projectName: newProject });
  expect(project.name).toBe(newProject);

  projects = await toArray(client.listProjects());
  projectNames = projects.map((project) => project.name);
  expect(projectNames).toContain(newProject);

  const runs = await toArray(client.listRuns({ projectName: newProject }));
  const projectId_runs = await toArray(
    client.listRuns({ projectId: project.id })
  );
  expect(runs.length).toBe(0);
  expect(projectId_runs.length).toBe(0);

  await client.deleteProject({ projectName: newProject });

  projects = await toArray(client.listProjects());
  projectNames = projects.map((project) => project.name);
  expect(projectNames).not.toContain(newProject);

  await expect(
    client.readProject({ projectName: newProject })
  ).rejects.toThrow();
  await expect(
    client.deleteProject({ projectName: newProject })
  ).rejects.toThrow();
});

test.concurrent("Test evaluate run", async () => {
  const langchainClient = new Client({});

  const projectName = "__test_evaluate_run";
  const datasetName = "__test_evaluate_run_dataset";
  const projects = await toArray(langchainClient.listProjects());
  const datasets = await toArray(langchainClient.listDatasets());

  if (projects.map((project) => project.name).includes(projectName)) {
    await langchainClient.deleteProject({ projectName });
  }

  if (datasets.map((dataset) => dataset.name).includes(datasetName)) {
    await langchainClient.deleteDataset({ datasetName });
  }

  const dataset = await langchainClient.createDataset(datasetName);
  const predicted = "abcd";
  const groundTruth = "bcde";
  const example = await langchainClient.createExample(
    { input: "hello world" },
    { output: groundTruth },
    {
      datasetId: dataset.id,
    }
  );

  const parentRunConfig: RunTreeConfig = {
    name: "parent_run",
    run_type: "chain",
    inputs: { input: "hello world" },
    project_name: projectName,
    serialized: {},
    client: langchainClient,
    reference_example_id: example.id,
  };

  const parentRun = new RunTree(parentRunConfig);
  await parentRun.postRun();
  await parentRun.end({ output: predicted });
  await parentRun.patchRun();

  const run = await langchainClient.readRun(parentRun.id);
  expect(run.outputs).toEqual({ output: predicted });
  const runUrl = await langchainClient.getRunUrl({ runId: run.id });
  expect(runUrl).toMatch(/http:\/\/localhost\/.*/);
  expect(runUrl).toContain(run.id);

  function jaccardChars(output: string, answer: string): number {
    const predictionChars = new Set(output.trim().toLowerCase());
    const answerChars = new Set(answer.trim().toLowerCase());
    const intersection = [...predictionChars].filter((x) => answerChars.has(x));
    const union = new Set([...predictionChars, ...answerChars]);
    return intersection.length / union.size;
  }

  async function grader(config: {
    input: string;
    prediction: string;
    answer?: string;
  }): Promise<{ score: number; value: string }> {
    let value: string;
    let score: number;
    if (config.answer === null || config.answer === undefined) {
      value = "AMBIGUOUS";
      score = -0.5;
    } else {
      score = jaccardChars(config.prediction, config.answer);
      value = score > 0.9 ? "CORRECT" : "INCORRECT";
    }
    return { score: score, value: value };
  }

  const evaluator = new StringEvaluator({
    evaluationName: "Jaccard",
    gradingFunction: grader,
  });

  const runs = await langchainClient.listRuns({
    projectName: projectName,
    executionOrder: 1,
    error: false,
  });

  const project = await langchainClient.readProject({
    projectName: projectName,
  });
  const projectWithStats = await langchainClient.readProject({
    projectId: project.id,
  });
  expect(projectWithStats.name).toBe(project.name);

  const allFeedback = [];
  for await (const run of runs) {
    allFeedback.push(await langchainClient.evaluateRun(run, evaluator));
  }

  expect(allFeedback.length).toEqual(1);

  const fetchedFeedback: Feedback[] = [];
  for await (const feedback of langchainClient.listFeedback({
    runIds: [run.id],
    feedbackKeys: ["Jaccard"],
    feedbackSourceTypes: ["model"],
  })) {
    fetchedFeedback.push(feedback);
  }
  expect(fetchedFeedback[0].id).toEqual(allFeedback[0].id);
  expect(fetchedFeedback[0].score).toEqual(
    jaccardChars(predicted, groundTruth)
  );
  expect(fetchedFeedback[0].value).toEqual("INCORRECT");

  await langchainClient.deleteDataset({ datasetId: dataset.id });
  await langchainClient.deleteProject({ projectName });
});

test.concurrent("Test persist update run", async () => {
  const langchainClient = new Client({});
  const projectName = "__test_persist_update_run";
  const projects = await langchainClient.listProjects();
  for await (const project of projects) {
    if (project.name === projectName) {
      await langchainClient.deleteProject({ projectName });
    }
  }
  const runId = "8bac165f-480e-4bf8-baa0-15f2de3cc706";
  await langchainClient.createRun({
    id: runId,
    project_name: projectName,
    name: "test_run",
    run_type: "llm",
    inputs: { text: "hello world" },
  });

  await langchainClient.updateRun(runId, { outputs: { output: ["Hi"] } });

  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  expect(storedRun.outputs).toEqual({ output: ["Hi"] });

  await langchainClient.deleteProject({ projectName });
});

test.concurrent("test create dataset", async () => {
  const langchainClient = new Client({});
  const datasetName = "__test_create_dataset";
  const datasets = await toArray(langchainClient.listDatasets());
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
});

test.concurrent("Test share and unshare run", async () => {
  const langchainClient = new Client({});

  // Create a new run
  const runId = uuidv4();
  await langchainClient.createRun({
    name: "Test run",
    inputs: { input: "hello world" },
    run_type: "chain",
    id: runId,
  });

  // Share the run and verify the shared link
  const sharedUrl = await langchainClient.shareRun(runId);
  const response = await fetch(sharedUrl);
  expect(response.status).toEqual(200);
  expect(await langchainClient.readRunSharedLink(runId)).toEqual(sharedUrl);

  await langchainClient.unshareRun(runId);
  const sharedLink = await langchainClient.readRunSharedLink(runId);
  expect(sharedLink).toBe(undefined);
});

test.concurrent("Test list datasets", async () => {
  const langchainClient = new Client({});
  const datasetName1 = "___TEST dataset1";
  const datasetName2 = "___TEST dataset2";

  // Delete any existing datasets with the same name
  const existingDatasets1 = langchainClient.listDatasets({
    datasetName: datasetName1,
  });
  for await (const dataset of existingDatasets1) {
    await langchainClient.deleteDataset({ datasetId: dataset.id });
  }
  const existingDatasets2 = langchainClient.listDatasets({
    datasetName: datasetName2,
  });
  for await (const dataset of existingDatasets2) {
    await langchainClient.deleteDataset({ datasetId: dataset.id });
  }

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

  // List datasets by data type
  const datasetsByDataTypeIterable = langchainClient.listDatasets({
    datasetName: datasetName1,
  });
  const datasetsByDataType = [];
  for await (const dataset of datasetsByDataTypeIterable) {
    datasetsByDataType.push(dataset);
  }
  expect(datasetsByDataType).toHaveLength(1);
  expect(datasetsByDataType[0].id).toBe(dataset1.id);

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

  // Delete datasets
  await langchainClient.deleteDataset({ datasetId: dataset1.id });
  await langchainClient.deleteDataset({ datasetId: dataset2.id });
  const remainingDatasetsIterable = langchainClient.listDatasets({
    datasetIds: [dataset1.id, dataset2.id],
  });
  const remainingDatasets = [];
  for await (const dataset of remainingDatasetsIterable) {
    remainingDatasets.push(dataset);
  }
  expect(remainingDatasets).toHaveLength(0);
});

test.concurrent(
  "Test create feedback with source run",
  async () => {
    const langchainClient = new Client({});
    const projectName = "__test_create_feedback_with_source_run";
    const projects = langchainClient.listProjects();
    for await (const project of projects) {
      if (project.name === projectName) {
        await langchainClient.deleteProject({ projectName });
      }
    }
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
  10000
);

test.concurrent(
  "Test create run with masked inputs/outputs",
  async () => {
    const langchainClient = new Client({});
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_HIDE_INPUTS = "true";
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_HIDE_OUTPUTS = "true";
    const projectName = "__test_create_run_with_masked_inputs_outputs";
    const projects = langchainClient.listProjects();
    for await (const project of projects) {
      if (project.name === projectName) {
        await langchainClient.deleteProject({ projectName });
      }
    }
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

    const run1 = await langchainClient.readRun(runId);
    expect(run1.inputs).toBeDefined();
    expect(Object.keys(run1.inputs)).toHaveLength(0);
    expect(run1.outputs).toBeDefined();
    expect(Object.keys(run1.outputs ?? {})).toHaveLength(0);
    const run2 = await langchainClient.readRun(runId2);
    expect(run2.inputs).toBeDefined();
    expect(Object.keys(run2.inputs)).toHaveLength(0);
    expect(run2.outputs).toBeDefined();
    expect(Object.keys(run2.outputs ?? {})).toHaveLength(0);
  },
  10000
);

test.concurrent(
  "Test create run with revision id",
  async () => {
    const langchainClient = new Client({});
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_REVISION_ID = "test_revision_id";
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_API_KEY = "fake_api_key";
    // eslint-disable-next-line no-process-env
    process.env.LANGCHAIN_OTHER_KEY = "test_other_key";
    const projectName = "__test_create_run_with_revision_id";
    const projects = langchainClient.listProjects();
    for await (const project of projects) {
      if (project.name === projectName) {
        await langchainClient.deleteProject({ projectName });
      }
    }
    const runId = "0cc29488-3b1b-4151-9476-30b5c1b24883";
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

    const runId2 = "82f19ed3-256f-4571-a078-2ccf11d0eba3";
    await langchainClient.createRun({
      id: runId2,
      project_name: projectName,
      name: "test_run_2",
      run_type: "llm",
      inputs: { messages: "hello world 2" },
      start_time: new Date().getTime(),
      revision_id: "different_revision_id",
    });

    const run1 = await langchainClient.readRun(runId);
    expect(run1.extra?.metadata?.revision_id).toEqual("test_revision_id");
    expect(run1.extra?.metadata.LANGCHAIN_OTHER_KEY).toEqual("test_other_key");
    expect(run1.extra?.metadata).not.toHaveProperty("LANGCHAIN_API_KEY");
    const run2 = await langchainClient.readRun(runId2);
    expect(run2.extra?.metadata?.revision_id).toEqual("different_revision_id");
    expect(run2.extra?.metadata.LANGCHAIN_OTHER_KEY).toEqual("test_other_key");
    expect(run2.extra?.metadata).not.toHaveProperty("LANGCHAIN_API_KEY");
  },
  10000
);

describe("createChatExample", () => {
  it("should convert LangChainBaseMessage objects to examples", async () => {
    const langchainClient = new Client({});

    const datasetName = "__createChatExample-test-dataset";
    try {
      const existingDataset = await langchainClient.readDataset({
        datasetName,
      });
      await langchainClient.deleteDataset({ datasetId: existingDataset.id });
    } catch (e) {
      console.log("Dataset does not exist");
    }

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
  }, 10000);
});

test.concurrent("Test getRunUrl with run", async () => {
  const client = new Client({});
  const run: Run = {
    id: uuidv4(),
    name: "foo",
    run_type: "llm",
    inputs: { input: "hello world" },
  };
  await client.createRun({ project_name: "foo", ...run });
  const result = await client.getRunUrl({
    run,
    projectOpts: { projectName: "foo" },
  });
  console.log(result);
});

test.concurrent("Test getRunUrl with run", async () => {
  const client = new Client({});
  const run: Run = {
    id: "123",
    name: "foo",
    run_type: "llm",
    inputs: { input: "hello world" },
  };
  const projectOpts = {
    projectId: "abcd-1234",
  };
  const result = await client.getRunUrl({ run, projectOpts });
  // Expect run.id to be in the url
  expect(result).toContain(run.id);
});

test.concurrent("Examples CRUD", async () => {
  const client = new Client({});
  const datasetName = "__test_examples_crud";
  try {
    const existingDataset = await client.readDataset({ datasetName });
    await client.deleteDataset({ datasetId: existingDataset.id });
  } catch (e) {
    console.log("Dataset does not exist");
  }
  const dataset = await client.createDataset(datasetName);
  const example = await client.createExample(
    { input: "hello world" },
    { output: "hi there" },
    {
      datasetId: dataset.id,
    }
  );
  const exampleValue = await client.readExample(example.id);
  expect(exampleValue.inputs.input).toEqual("hello world");
  expect(exampleValue?.outputs?.output).toEqual("hi there");
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
    datasetId: dataset.id,
  });
  const examplesList = await toArray(
    client.listExamples({ datasetId: dataset.id })
  );
  expect(examplesList.length).toEqual(4);
  await client.deleteExample(example.id);
  const examplesList2 = await toArray(
    client.listExamples({ datasetId: dataset.id })
  );
  expect(examplesList2.length).toEqual(3);
  await client.deleteDataset({ datasetId: dataset.id });
});
