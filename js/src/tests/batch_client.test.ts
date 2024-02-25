import { jest } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../client.js";
import { convertToDottedOrderFormat } from "../run_trees.js";

describe("Batch client tracing", () => {
  it("should create a batched run with the given input", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(true);
    const projectName = "__test_batch";

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await client.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    await new Promise((resolve) => setTimeout(resolve, 300));

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    expect(JSON.parse(calledRequestParam?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runId,
          run_type: "llm",
          inputs: {
            text: "hello world",
          },
          trace_id: runId,
          dotted_order: dottedOrder,
        }),
      ],
      patch: [],
    });

    expect(callSpy).toHaveBeenCalledWith(
      fetch,
      "https://api.smith.langchain.com/runs/batch",
      expect.objectContaining({ body: expect.any(String) })
    );
  });

  it("should not throw an error if fetch fails for batch requests", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      autoBatchTracing: true,
    });
    jest.spyOn((client as any).caller, "call").mockImplementation(() => {
      throw new Error("Totally expected mock error");
    });
    jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockImplementation(() => {
        throw new Error("Totally expected mock error");
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(true);
    const projectName = "__test_batch";

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );

    await client.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    await new Promise((resolve) => setTimeout(resolve, 300));
  });

  it("Create + update batching should merge into a single call", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(true);
    const projectName = "__test_batch";

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await client.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    const endTime = Math.floor(new Date().getTime() / 1000);

    await client.updateRun(runId, {
      outputs: { output: ["Hi"] },
      dotted_order: dottedOrder,
      trace_id: runId,
      end_time: endTime,
    });

    await new Promise((resolve) => setTimeout(resolve, 100));

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    expect(JSON.parse(calledRequestParam?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runId,
          run_type: "llm",
          inputs: {
            text: "hello world",
          },
          outputs: {
            output: ["Hi"],
          },
          end_time: endTime,
          trace_id: runId,
          dotted_order: dottedOrder,
        }),
      ],
      patch: [],
    });

    expect(callSpy).toHaveBeenCalledWith(
      fetch,
      "https://api.smith.langchain.com/runs/batch",
      expect.objectContaining({ body: expect.any(String) })
    );
  });

  it("should immediately trigger a batch on root run end", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(true);
    const projectName = "__test_batch";

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await client.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    // Wait for first batch to send
    await new Promise((resolve) => setTimeout(resolve, 300));

    const endTime = Math.floor(new Date().getTime() / 1000);

    // A root run finishing triggers the second batch
    await client.updateRun(runId, {
      outputs: { output: ["Hi"] },
      dotted_order: dottedOrder,
      trace_id: runId,
      end_time: endTime,
    });

    const runId2 = uuidv4();
    const dottedOrder2 = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId2
    );

    // Will send in a third batch, even though it's triggered around the same time as the update
    await client.createRun({
      id: runId2,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world 2" },
      trace_id: runId2,
      dotted_order: dottedOrder2,
    });

    await new Promise((resolve) => setTimeout(resolve, 300));

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    const calledRequestParam2: any = callSpy.mock.calls[1][2];
    const calledRequestParam3: any = callSpy.mock.calls[2][2];
    expect(JSON.parse(calledRequestParam?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runId,
          run_type: "llm",
          inputs: {
            text: "hello world",
          },
          trace_id: runId,
          dotted_order: dottedOrder,
        }),
      ],
      patch: [],
    });

    expect(JSON.parse(calledRequestParam2?.body)).toEqual({
      post: [],
      patch: [
        expect.objectContaining({
          id: runId,
          dotted_order: dottedOrder,
          trace_id: runId,
          end_time: endTime,
          outputs: {
            output: ["Hi"],
          },
        }),
      ],
    });
    expect(JSON.parse(calledRequestParam3?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runId2,
          run_type: "llm",
          inputs: {
            text: "hello world 2",
          },
          trace_id: runId2,
          dotted_order: dottedOrder2,
        }),
      ],
      patch: [],
    });
  });

  it("should send traces above the batch size and see even batches", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      pendingAutoBatchedRunLimit: 10,
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(true);
    const projectName = "__test_batch";

    const runIds = await Promise.all(
      [...Array(15)].map(async (_, i) => {
        const runId = uuidv4();
        const dottedOrder = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        await client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "hello world " + i },
          trace_id: runId,
          dotted_order: dottedOrder,
        });
        return runId;
      })
    );

    await new Promise((resolve) => setTimeout(resolve, 10));

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    const calledRequestParam2: any = callSpy.mock.calls[1][2];

    // Queue should drain as soon as size limit is reached,
    // sending both batches
    expect(JSON.parse(calledRequestParam?.body)).toEqual({
      post: runIds.slice(0, 10).map((runId, i) =>
        expect.objectContaining({
          id: runId,
          run_type: "llm",
          inputs: {
            text: "hello world " + i,
          },
          trace_id: runId,
        })
      ),
      patch: [],
    });

    expect(JSON.parse(calledRequestParam2?.body)).toEqual({
      post: runIds.slice(10).map((runId, i) =>
        expect.objectContaining({
          id: runId,
          run_type: "llm",
          inputs: {
            text: "hello world " + (i + 10),
          },
          trace_id: runId,
        })
      ),
      patch: [],
    });
  });

  it("should send traces above the batch size limit in bytes and see even batches", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      pendingAutoBatchedRunLimit: 10,
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest.spyOn(client as any, "_getServerInfo").mockResolvedValue({
      batch_ingest_config: {
        size_limit_bytes: 1,
      },
    });
    const projectName = "__test_batch";

    const runIds = await Promise.all(
      [...Array(4)].map(async (_, i) => {
        const runId = uuidv4();
        const dottedOrder = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        await client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "hello world " + i },
          trace_id: runId,
          dotted_order: dottedOrder,
        });
        return runId;
      })
    );

    await new Promise((resolve) => setTimeout(resolve, 300));

    expect(callSpy.mock.calls.length).toEqual(4);

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    const calledRequestParam2: any = callSpy.mock.calls[1][2];
    const calledRequestParam3: any = callSpy.mock.calls[2][2];
    const calledRequestParam4: any = callSpy.mock.calls[3][2];

    // Queue should drain as soon as byte size limit of 1 is reached,
    // sending each call individually
    expect(JSON.parse(calledRequestParam?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runIds[0],
          run_type: "llm",
          inputs: {
            text: "hello world 0",
          },
          trace_id: runIds[0],
        }),
      ],
      patch: [],
    });

    expect(JSON.parse(calledRequestParam2?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runIds[1],
          run_type: "llm",
          inputs: {
            text: "hello world 1",
          },
          trace_id: runIds[1],
        }),
      ],
      patch: [],
    });

    expect(JSON.parse(calledRequestParam3?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runIds[2],
          run_type: "llm",
          inputs: {
            text: "hello world 2",
          },
          trace_id: runIds[2],
        }),
      ],
      patch: [],
    });

    expect(JSON.parse(calledRequestParam4?.body)).toEqual({
      post: [
        expect.objectContaining({
          id: runIds[3],
          run_type: "llm",
          inputs: {
            text: "hello world 3",
          },
          trace_id: runIds[3],
        }),
      ],
      patch: [],
    });
  });

  it("If batching is unsupported, fall back to old endpoint", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      autoBatchTracing: true,
    });
    const callSpy = jest
      .spyOn((client as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    jest
      .spyOn(client as any, "batchEndpointIsSupported")
      .mockResolvedValue(false);
    const projectName = "__test_batch";

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await client.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    await new Promise((resolve) => setTimeout(resolve, 300));

    const calledRequestParam: any = callSpy.mock.calls[0][2];
    expect(JSON.parse(calledRequestParam?.body)).toMatchObject({
      id: runId,
      session_name: projectName,
      extra: expect.anything(),
      start_time: expect.any(Number),
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    expect(callSpy).toHaveBeenCalledWith(
      fetch,
      "https://api.smith.langchain.com/runs",
      expect.objectContaining({ body: expect.any(String) })
    );
  });
});
