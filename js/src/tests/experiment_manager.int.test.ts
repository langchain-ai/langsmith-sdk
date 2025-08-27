import { _ExperimentManager } from "../evaluation/_runner.js";
import { Client } from "../index.js";
import { v4 as uuidv4 } from "uuid";

const TESTING_DATASET_NAME = `test_experiment_manager_${uuidv4()}`;

beforeAll(async () => {
  const client = new Client();

  if (!(await client.hasDataset({ datasetName: TESTING_DATASET_NAME }))) {
    await client.createDataset(TESTING_DATASET_NAME, {
      description: "For testing pruposes",
    });

    await client.createExamples({
      inputs: [{ input: 1 }, { input: 2 }],
      outputs: [{ output: 2 }, { output: 3 }],
      datasetName: TESTING_DATASET_NAME,
    });
  }
});

afterAll(async () => {
  const client = new Client();
  await client.deleteDataset({ datasetName: TESTING_DATASET_NAME });
});

describe("experiment manager", () => {
  test("can recover from collisions", async () => {
    const client = new Client();
    const ds = await client.readDataset({ datasetName: TESTING_DATASET_NAME });
    const manager = new _ExperimentManager({
      data: TESTING_DATASET_NAME,
      client,
      numRepetitions: 1,
    });
    const experimentName = manager._experimentName;
    await client.createProject({
      projectName: experimentName,
      referenceDatasetId: ds.id,
    });
    await manager.start();
    expect(manager._experimentName).not.toEqual(experimentName);
  });
});
