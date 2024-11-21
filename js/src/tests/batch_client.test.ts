/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable prefer-const */
import { jest } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
import { Client, mergeRuntimeEnvIntoRunCreate } from "../client.js";
import { convertToDottedOrderFormat } from "../run_trees.js";
import { _getFetchImplementation } from "../singletons/fetch.js";
import { RunCreate } from "../schemas.js";

const parseMockRequestBody = async (body: string | ArrayBuffer) => {
  if (typeof body === "string") {
    return JSON.parse(body);
  }
  // Typing is missing
  const rawMultipart = new TextDecoder().decode(body);
  // Parse the multipart form data boundary from the raw text
  const boundary = rawMultipart.split("\r\n")[0].trim();
  // Split the multipart body into individual parts
  const parts = rawMultipart.split(boundary).slice(1, -1);

  const entries: [string, any][] = parts.map((part) => {
    const [headers, ...contentParts] = part.trim().split("\r\n\r\n");
    const content = contentParts.join("\r\n\r\n");
    // Extract the name from Content-Disposition header
    const nameMatch = headers.match(/name="([^"]+)"/);
    const name = nameMatch ? nameMatch[1] : "";
    return [name, content.trim()];
  });
  const reconstructedBody: any = {
    post: [],
    patch: [],
  };
  for (const [key, value] of entries) {
    let [method, id, type] = key.split(".");
    let parsedValue;
    try {
      parsedValue = JSON.parse(value);
    } catch (e) {
      parsedValue = value;
    }
    // if (method === "attachment") {
    //   for (const item of reconstructedBody.post) {
    //     if (item.id === id) {
    //       if (item.attachments === undefined) {
    //         item.attachments = [];
    //       }

    //       item[type] = parsedValue;
    //     }
    //   }
    //   return;
    // }
    if (!(method in reconstructedBody)) {
      throw new Error(`${method} must be "post" or "patch"`);
    }
    if (!type) {
      reconstructedBody[method as keyof typeof reconstructedBody].push(
        parsedValue
      );
    } else {
      for (const item of reconstructedBody[method]) {
        if (item.id === id) {
          item[type] = parsedValue;
        }
      }
    }
  }
  return reconstructedBody;
};

// prettier-ignore
const ENDPOINT_TYPES = [
  "batch",
  "multipart",
];

describe.each(ENDPOINT_TYPES)(
  "Batch client tracing with %s endpoint",
  (endpointType) => {
    const extraBatchIngestConfig =
      endpointType === "batch"
        ? {}
        : {
            use_multipart_endpoint: true,
          };
    const expectedTraceURL =
      endpointType === "batch"
        ? "https://api.smith.langchain.com/runs/batch"
        : "https://api.smith.langchain.com/runs/multipart";
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
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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
        _getFetchImplementation(),
        expectedTraceURL,
        expect.objectContaining({
          body: expect.any(endpointType === "batch" ? String : ArrayBuffer),
        })
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
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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

      await client.awaitPendingTraceBatches();

      const calledRequestParam: any = callSpy.mock.calls[0][2];
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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
        _getFetchImplementation(),
        expectedTraceURL,
        expect.objectContaining({
          body: expect.any(endpointType === "batch" ? String : ArrayBuffer),
        })
      );
    });

    it("server info fetch should retry even if initial call fails", async () => {
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
      let serverInfoFailedOnce = false;
      jest.spyOn(client as any, "_getServerInfo").mockImplementationOnce(() => {
        serverInfoFailedOnce = true;
        throw new Error("[MOCK] Connection error.");
      });
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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

      await client.awaitPendingTraceBatches();

      expect(serverInfoFailedOnce).toBe(true);

      const calledRequestParam: any = callSpy.mock.calls[0][2];
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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
        _getFetchImplementation(),
        expectedTraceURL,
        expect.objectContaining({
          body: expect.any(endpointType === "batch" ? String : ArrayBuffer),
        })
      );
    });

    it("should immediately trigger a batch on root run end if blockOnRootRunFinalization is set", async () => {
      const client = new Client({
        apiKey: "test-api-key",
        autoBatchTracing: true,
        blockOnRootRunFinalization: true,
      });
      const callSpy = jest
        .spyOn((client as any).batchIngestCaller, "call")
        .mockResolvedValue({
          ok: true,
          text: () => "",
        });
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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

      expect(await parseMockRequestBody(calledRequestParam2?.body)).toEqual({
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
      expect(await parseMockRequestBody(calledRequestParam3?.body)).toEqual({
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

    it("should not trigger a batch on root run end and instead batch call with previous batch if blockOnRootRunFinalization is false", async () => {
      const client = new Client({
        apiKey: "test-api-key",
        autoBatchTracing: true,
        blockOnRootRunFinalization: false,
      });
      const callSpy = jest
        .spyOn((client as any).batchIngestCaller, "call")
        .mockResolvedValue({
          ok: true,
          text: () => "",
        });
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
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

      expect((client as any).autoBatchQueue.items.length).toBe(1);
      // Wait for first batch to send
      await new Promise((resolve) => setTimeout(resolve, 300));
      expect((client as any).autoBatchQueue.items.length).toBe(0);

      const endTime = Math.floor(new Date().getTime() / 1000);

      // Start the the second batch
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

      // Should aggregate on the second batch
      await client.createRun({
        id: runId2,
        project_name: projectName,
        name: "test_run",
        run_type: "llm",
        inputs: { text: "hello world 2" },
        trace_id: runId2,
        dotted_order: dottedOrder2,
      });

      // 2 runs in the queue
      expect((client as any).autoBatchQueue.items.length).toBe(2);
      await client.awaitPendingTraceBatches();
      expect((client as any).autoBatchQueue.items.length).toBe(0);

      expect(callSpy.mock.calls.length).toEqual(2);
      const calledRequestParam: any = callSpy.mock.calls[0][2];
      const calledRequestParam2: any = callSpy.mock.calls[1][2];
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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

      expect(await parseMockRequestBody(calledRequestParam2?.body)).toEqual({
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
        batchSizeBytesLimit: 10000,
        autoBatchTracing: true,
      });
      const callSpy = jest
        .spyOn((client as any).batchIngestCaller, "call")
        .mockResolvedValue({
          ok: true,
          text: () => "",
        });
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
      });
      const projectName = "__test_batch";

      const runIds = await Promise.all(
        [...Array(15)].map(async (_, i) => {
          const runId = uuidv4();
          const dottedOrder = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRunCreate({
            id: runId,
            project_name: projectName,
            name: "test_run " + i,
            run_type: "llm",
            inputs: { text: "hello world " + i },
            trace_id: runId,
            dotted_order: dottedOrder,
          } as RunCreate);
          // Allow some extra space for other request properties
          const mockRunSize = 950;
          const padCount = mockRunSize - JSON.stringify(params).length;
          params.inputs.text = params.inputs.text + "x".repeat(padCount);
          await client.createRun(params);
          return runId;
        })
      );

      await new Promise((resolve) => setTimeout(resolve, 10));

      const calledRequestParam: any = callSpy.mock.calls[0][2];
      const calledRequestParam2: any = callSpy.mock.calls[1][2];

      const firstBatchBody = await parseMockRequestBody(
        calledRequestParam?.body
      );
      const secondBatchBody = await parseMockRequestBody(
        calledRequestParam2?.body
      );

      const initialBatchBody =
        firstBatchBody.post.length === 10 ? firstBatchBody : secondBatchBody;
      const followupBatchBody =
        firstBatchBody.post.length === 10 ? secondBatchBody : firstBatchBody;

      // Queue should drain as soon as size limit is reached,
      // sending both batches
      expect(initialBatchBody).toEqual({
        post: runIds.slice(0, 10).map((runId, i) =>
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              text: expect.stringContaining("hello world " + i),
            },
            trace_id: runId,
          })
        ),
        patch: [],
      });

      expect(followupBatchBody).toEqual({
        post: runIds.slice(10).map((runId, i) =>
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              text: expect.stringContaining("hello world " + (i + 10)),
            },
            trace_id: runId,
          })
        ),
        patch: [],
      });
    });

    it("a very low batch size limit should be equivalent to single calls", async () => {
      const client = new Client({
        apiKey: "test-api-key",
        batchSizeBytesLimit: 1,
        autoBatchTracing: true,
      });
      const callSpy = jest
        .spyOn((client as any).batchIngestCaller, "call")
        .mockResolvedValue({
          ok: true,
          text: () => "",
        });
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: {
            ...extraBatchIngestConfig,
          },
        };
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
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
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

      expect(await parseMockRequestBody(calledRequestParam2?.body)).toEqual({
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

      expect(await parseMockRequestBody(calledRequestParam3?.body)).toEqual({
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

      expect(await parseMockRequestBody(calledRequestParam4?.body)).toEqual({
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

    it("Use batch endpoint if info call fails", async () => {
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
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        throw new Error("Totally expected mock error");
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

      await client.awaitPendingTraceBatches();

      const calledRequestParam: any = callSpy.mock.calls[0][2];

      expect(
        await parseMockRequestBody(calledRequestParam?.body)
      ).toMatchObject({
        post: [
          {
            id: runId,
            session_name: projectName,
            extra: expect.anything(),
            start_time: expect.any(Number),
            name: "test_run",
            run_type: "llm",
            inputs: { text: "hello world" },
            trace_id: runId,
            dotted_order: dottedOrder,
          },
        ],
        patch: [],
      });

      expect(callSpy).toHaveBeenCalledWith(
        _getFetchImplementation(),
        "https://api.smith.langchain.com/runs/batch",
        expect.objectContaining({
          body: expect.any(String),
        })
      );
    });

    it("Should handle circular values", async () => {
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
      jest.spyOn(client as any, "_getServerInfo").mockImplementation(() => {
        return {
          version: "foo",
          batch_ingest_config: { ...extraBatchIngestConfig },
        };
      });
      const projectName = "__test_batch";
      const a: Record<string, any> = {};
      const b: Record<string, any> = {};
      a.b = b;
      b.a = a;

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
        inputs: a,
        trace_id: runId,
        dotted_order: dottedOrder,
      });

      const endTime = Math.floor(new Date().getTime() / 1000);

      await client.updateRun(runId, {
        outputs: b,
        dotted_order: dottedOrder,
        trace_id: runId,
        end_time: endTime,
      });

      await client.awaitPendingTraceBatches();

      const calledRequestParam: any = callSpy.mock.calls[0][2];
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
        post: [
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              b: {
                a: {
                  result: "[Circular]",
                },
              },
            },
            outputs: {
              a:
                // Stringification happens at a different level
                endpointType === "batch"
                  ? {
                      result: "[Circular]",
                    }
                  : {
                      b: {
                        result: "[Circular]",
                      },
                    },
            },
            end_time: endTime,
            trace_id: runId,
            dotted_order: dottedOrder,
          }),
        ],
        patch: [],
      });

      expect(callSpy).toHaveBeenCalledWith(
        _getFetchImplementation(),
        expectedTraceURL,
        expect.objectContaining({
          body: expect.any(endpointType === "batch" ? String : ArrayBuffer),
        })
      );
    });
  }
);
