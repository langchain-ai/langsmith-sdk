import { Client } from "../client.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { StringEvaluator } from "../evaluation/string_evaluator.js";
import { Dataset, Feedback } from "../schemas.js";

async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

// Test Dataset Creation, List, Read, Delete + upload CSV
// Test Example Creation, List, Read, Update, Delete
test("Test LangSmith Client Dataset CRD", async () => {
  const client = new Client({
    apiUrl: "http://localhost:1984",
  });

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
test("Test LangSmith Client Project CRD", async () => {
  const client = new Client({
    apiUrl: "http://localhost:1984",
  });

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

test("Test evaluate run", async () => {
  const langchainClient = new Client({
    apiUrl: "http://localhost:1984",
  });

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
  expect(projectWithStats.run_count).toBe(1);
  expect(projectWithStats.latency_p50).toBeGreaterThan(0);
  expect(projectWithStats.latency_p99).toBeGreaterThan(0);

  const allFeedback = [];
  for await (const run of runs) {
    allFeedback.push(await langchainClient.evaluateRun(run, evaluator));
  }

  expect(allFeedback.length).toEqual(1);

  const fetchedFeedback: Feedback[] = [];
  for await (const feedback of langchainClient.listFeedback({
    runIds: [run.id],
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

test("Test persist update run", async () => {
  const langchainClient = new Client({
    apiUrl: "http://localhost:1984",
  });
  const projectName = "__test_persist_update_run";
  const projects = await langchainClient.listProjects();
  for await (const project of projects) {
    if (project.name === projectName) {
      await langchainClient.deleteProject({ projectName });
    }
  }
  const runId = "8bac165f-480e-4bf8-baa0-15f2de4cc706";
  if ((await toArray(langchainClient.listRuns({ id: [runId] }))).length > 0) {
    await langchainClient.deleteRun(runId);
  }
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

test("test create dataset", async () => {
  const langchainClient = new Client({
    apiUrl: "http://localhost:1984",
  });
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
});
