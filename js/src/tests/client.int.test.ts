import { LangChainPlusClient } from "../client.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { StringEvaluator } from "../evaluation/string_evaluator.js";

// Test Dataset Creation, List, Read, Delete + upload CSV
// Test Example Creation, List, Read, Update, Delete
test("Test LangChainPlus Client Dataset CRD", async () => {
  const client = new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });

  const csvContent = `col1,col2\nval1,val2`;
  const blobData = new Blob([Buffer.from(csvContent)]);

  const description = "Test Dataset";
  const inputKeys = ["col1"];
  const outputKeys = ["col2"];
  const fileName = "__some_file.int.csv";
  const existingDatasets = await client.listDatasets({});
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

  const datasets = await client.listDatasets({});
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

  const examples = await client.listExamples({ datasetId: newDataset.id });
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
  const deletedExample = await client.deleteExample(example.id);
  expect(deletedExample.id).toBe(example.id);
  const examples2 = await client.listExamples({ datasetId: newDataset.id });
  expect(examples2.length).toBe(1);

  const deleted = await client.deleteDataset({ datasetId });
  expect(deleted.id).toBe(datasetId);
  const rawDataset = await client.createDataset(fileName, {
    description: "Test Dataset",
  });
  const rawDeleted = await client.deleteDataset({ datasetId: rawDataset.id });
  expect(rawDeleted.id).toBe(rawDataset.id);
});

// Test Session Creation, List, Read, Delete
test("Test LangChainPlus Client Session CRD", async () => {
  const client = await new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });

  const newSession = `__some_session.int.`;
  if ((await client.listSessions()).map((s) => s.name).includes(newSession)) {
    await client.deleteSession({ sessionName: newSession });
  }

  let sessions = await client.listSessions();
  let sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).not.toContain(newSession);

  await client.createSession({ sessionName: newSession });
  const session = await client.readSession({ sessionName: newSession });
  expect(session.name).toBe(newSession);

  sessions = await client.listSessions();
  sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).toContain(newSession);

  const runs = await client.listRuns({ sessionName: newSession });
  const sessionId_runs = await client.listRuns({ sessionId: session.id });
  expect(runs.length).toBe(0);
  expect(sessionId_runs.length).toBe(0);

  await client.deleteSession({ sessionName: newSession });

  sessions = await client.listSessions();
  sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).not.toContain(newSession);

  await expect(
    client.readSession({ sessionName: newSession })
  ).rejects.toThrow();
  await expect(
    client.deleteSession({ sessionName: newSession })
  ).rejects.toThrow();
});

test("Test evaluate run", async () => {
  const langchainClient = new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });

  const sessionName = "__test_evaluate_run";
  const datasetName = "__test_evaluate_run_dataset";
  const sessions = await langchainClient.listSessions();
  const datasets = await langchainClient.listDatasets();

  if (sessions.map((session) => session.name).includes(sessionName)) {
    await langchainClient.deleteSession({ sessionName });
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
    session_name: sessionName,
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
    sessionName: sessionName,
    executionOrder: 1,
    error: false,
  });

  const session = await langchainClient.readSession({
    sessionName: sessionName,
  });
  const sessionWithStats = await langchainClient.readSession({
    sessionId: session.id,
  });
  expect(sessionWithStats.name).toBe(session.name);
  expect(sessionWithStats.run_count).toBe(1);
  expect(sessionWithStats.latency_p50).toBeGreaterThan(0);
  expect(sessionWithStats.latency_p99).toBeGreaterThan(0);
  expect(sessionWithStats.total_tokens).toBeGreaterThan(2);

  const allFeedback = [];
  for (const run of runs) {
    allFeedback.push(await langchainClient.evaluateRun(run, evaluator));
  }

  expect(allFeedback.length).toEqual(1);

  const fetchedFeedback = await langchainClient.listFeedback({
    runIds: [run.id],
  });
  expect(fetchedFeedback[0].id).toEqual(allFeedback[0].id);
  expect(fetchedFeedback[0].score).toEqual(
    jaccardChars(predicted, groundTruth)
  );
  expect(fetchedFeedback[0].value).toEqual("INCORRECT");

  await langchainClient.deleteDataset({ datasetId: dataset.id });
  await langchainClient.deleteSession({ sessionName });
});

test("Test persist update run", async () => {
  const langchainClient = new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });
  const sessionName = "__test_persist_update_run";
  const sessions = await langchainClient.listSessions();

  if (sessions.map((session) => session.name).includes(sessionName)) {
    await langchainClient.deleteSession({ sessionName });
  }
  const runId = "8bac165f-480e-4bf8-baa0-15f2de4cc706";
  await langchainClient.createRun({
    id: runId,
    session_name: sessionName,
    name: "test_run",
    run_type: "llm",
    inputs: { text: "hello world" },
  });

  await langchainClient.updateRun(runId, { outputs: { output: ["Hi"] } });

  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  expect(storedRun.outputs).toEqual({ output: ["Hi"] });

  await langchainClient.deleteSession({ sessionName });
});
