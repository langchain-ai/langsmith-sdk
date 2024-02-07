import { jest } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../client.js";
import { convertToDottedOrderFormat } from "../run_trees.js";

describe("Batch client tracing", () => {
  it("should create a batched run with the given input", async () => {
    const client = new Client({ apiKey: "test-api-key" });
    const callSpy = jest
      .spyOn((client as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
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

  it("Create + update batching should merge into a single call", async () => {
    const client = new Client({ apiKey: "test-api-key" });
    const callSpy = jest
      .spyOn((client as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
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

  it("should create an example with the given input and generation", async () => {
    const client = new Client({ apiKey: "test-api-key" });
    const callSpy = jest
      .spyOn((client as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
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

    const endTime = Math.floor(new Date().getTime() / 1000);

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
  });

  it("should send traces above the batch size and see even batches", async () => {
    const client = new Client({
      apiKey: "test-api-key",
      pendingAutoBatchedRunLimit: 10,
    });
    const callSpy = jest
      .spyOn((client as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
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
    // Second batch should still be pending
    expect(callSpy.mock.calls[1]).toBeUndefined();
    // First batch should fire as soon as it hits 10
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

    // Wait for the aggregation delay
    await new Promise((resolve) => setTimeout(resolve, 100));

    const calledRequestParam2: any = callSpy.mock.calls[1][2];

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
});
