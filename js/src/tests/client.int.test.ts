import { LangChainPlusClient } from "../client.js";

// Test Dataset Creation, List, Read, Delete + upload CSV
// Test Example Creation, List, Read, Update, Delete
test("Test LangChainPlus Client Dataset CRD", async () => {
  const client = await new LangChainPlusClient({
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
    await client.deleteDataset({ dataset_name: fileName });
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

  const dataset = await client.readDataset({ dataset_id: newDataset.id });
  const dataset_id = dataset.id;
  const dataset2 = await client.readDataset({ dataset_id });
  expect(dataset.id).toBe(dataset2.id);

  const datasets = await client.listDatasets({});
  expect(datasets.length).toBeGreaterThan(0);
  expect(datasets.map((d) => d.id)).toContain(dataset_id);

  const example = await client.createExample(
    { col1: "addedExampleCol1" },
    { col2: "addedExampleCol2" },
    { dataset_id: newDataset.id }
  );
  const exampleValue = await client.readExample(example.id);
  expect(exampleValue.inputs.col1).toBe("addedExampleCol1");
  expect(exampleValue.outputs.col2).toBe("addedExampleCol2");

  const examples = await client.listExamples({ dataset_id: newDataset.id });
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
  const examples2 = await client.listExamples({ dataset_id: newDataset.id });
  expect(examples2.length).toBe(1);

  const deleted = await client.deleteDataset({ dataset_id });
  expect(deleted.id).toBe(dataset_id);
  const rawDataset = await client.createDataset(fileName, {
    description: "Test Dataset",
  });
  const rawDeleted = await client.deleteDataset({ dataset_id: rawDataset.id });
  expect(rawDeleted.id).toBe(rawDataset.id);
});

// Test Session Creation, List, Read, Delete
test("Test LangChainPlus Client Session CRD", async () => {
  const client = await new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });

  const newSession = `__some_session.int.`;
  if ((await client.listSessions()).map((s) => s.name).includes(newSession)) {
    await client.deleteSession({ session_name: newSession });
  }

  let sessions = await client.listSessions();
  let sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).not.toContain(newSession);

  await client.createSession({ session_name: newSession });
  const session = await client.readSession({ session_name: newSession });
  expect(session.name).toBe(newSession);

  sessions = await client.listSessions();
  sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).toContain(newSession);

  const runs = await client.listRuns({ session_name: newSession });
  const sessionId_runs = await client.listRuns({ session_id: session.id });
  expect(runs.length).toBe(0);
  expect(sessionId_runs.length).toBe(0);

  await client.deleteSession({ session_name: newSession });

  sessions = await client.listSessions();
  sessionNames = sessions.map((session) => session.name);
  expect(sessionNames).not.toContain(newSession);

  await expect(
    client.readSession({ session_name: newSession })
  ).rejects.toThrow();
  await expect(
    client.deleteSession({ session_name: newSession })
  ).rejects.toThrow();
});
