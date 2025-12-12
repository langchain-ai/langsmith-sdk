/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable prefer-const */
/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { jest, describe, expect, afterEach, it } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
import { Client, mergeRuntimeEnvIntoRun } from "../client.js";
import { convertToDottedOrderFormat } from "../run_trees.js";
import { RunCreate } from "../schemas.js";

const parseMockRequestBody = async (
  body: string | Uint8Array | ReadableStream
) => {
  if (typeof body === "string") {
    return JSON.parse(body);
  }

  let rawMultipart;
  // eslint-disable-next-line no-instanceof/no-instanceof
  if (body instanceof ReadableStream) {
    // Clone the stream in case we need to retry without decompression
    const [stream1, stream2] = body.tee();
    try {
      rawMultipart = await new Response(
        stream1.pipeThrough(new DecompressionStream("gzip"))
      ).text();
    } catch {
      // If gzip decompression fails, try reading as plain text
      rawMultipart = await new Response(stream2).text();
    }
  } else {
    rawMultipart = new TextDecoder().decode(body);
  }

  if (rawMultipart.trim().startsWith("{")) {
    return JSON.parse(rawMultipart);
  }
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
    } catch {
      parsedValue = value;
    }
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
        ? {
            use_multipart_endpoint: false,
          }
        : {
            use_multipart_endpoint: true,
          };
    const extraInstanceFlags = {
      gzip_body_enabled: true,
    };
    const expectedTraceURL =
      endpointType === "batch"
        ? "https://api.smith.langchain.com/runs/batch"
        : "https://api.smith.langchain.com/runs/multipart";

    let testClients: any[] = [];

    const createClient = (
      config: any,
      mockFetch?: jest.MockedFunction<typeof fetch>
    ) => {
      const client = new Client({
        ...config,
        fetchImplementation: mockFetch,
      });
      testClients.push(client);
      return client;
    };

    const createMockFetch = (callsArray: any[]) => {
      return jest.fn((...args: any[]) => {
        // Only count calls to batch/multipart endpoints, not info calls
        if (args[0]?.includes("/runs/")) {
          callsArray.push(args);
        }
        return Promise.resolve({
          ok: true,
          text: () => Promise.resolve(""),
        } as Response);
      });
    };

    afterEach(async () => {
      // Clean up all clients created during the test
      for (const client of testClients) {
        try {
          await client.awaitPendingTraceBatches();
        } catch {
          // Ignore cleanup errors
        }
      }
      testClients = [];

      // Wait for any pending async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 100));
      jest.clearAllMocks();
      jest.clearAllTimers();
      jest.useRealTimers();
    });

    it("should create a batched run with the given input", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
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
    });

    it("should hide inputs and outputs", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          hideInputs: () => ({ hidden: "inputs" }),
          hideOutputs: () => ({ hidden: "outputs" }),
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
        new Date().getTime() / 1000,
        runId
      );
      await client.createRun({
        id: runId,
        project_name: projectName,
        name: "test_run",
        run_type: "llm",
        inputs: { text: "hello world" },
        outputs: { text: "hello world" },
        trace_id: runId,
        dotted_order: dottedOrder,
      });

      await new Promise((resolve) => setTimeout(resolve, 300));

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
        post: [
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              hidden: "inputs",
            },
            outputs: {
              hidden: "outputs",
            },
            trace_id: runId,
            dotted_order: dottedOrder,
          }),
        ],
        patch: [],
      });
    });

    it("should hide inputs and outputs with an async function", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          hideInputs: async () => ({ hidden: "inputs" }),
          hideOutputs: async () => ({ hidden: "outputs" }),
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
        new Date().getTime() / 1000,
        runId
      );
      await client.createRun({
        id: runId,
        project_name: projectName,
        name: "test_run",
        run_type: "llm",
        inputs: { text: "hello world" },
        outputs: { text: "hello world" },
        trace_id: runId,
        dotted_order: dottedOrder,
      });

      await new Promise((resolve) => setTimeout(resolve, 300));

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(await parseMockRequestBody(calledRequestParam?.body)).toEqual({
        post: [
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              hidden: "inputs",
            },
            outputs: {
              hidden: "outputs",
            },
            trace_id: runId,
            dotted_order: dottedOrder,
          }),
        ],
        patch: [],
      });
    });

    it("should not throw an error if fetch fails for batch requests", async () => {
      const calls: any[] = [];
      const mockFetch = jest.fn((...args: any[]) => {
        calls.push(args);
        throw new Error("Totally expected mock error");
      });

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
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
    });

    it("server info fetch should retry even if initial call fails", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      let serverInfoFailedOnce = false;
      jest
        .spyOn(client as any, "_ensureServerInfo")
        .mockImplementationOnce(async () => {
          serverInfoFailedOnce = true;
          throw new Error("[MOCK] Connection error.");
        });
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
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
    });

    it("should immediately trigger a batch on root run end if blockOnRootRunFinalization is set", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          blockOnRootRunFinalization: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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
      const { dottedOrder: dottedOrder2 } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      const calledRequestParam3: any = calls[2][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);
      expect(calls[2][0]).toBe(expectedTraceURL);
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

      // Clean up any pending batches
      await client.awaitPendingTraceBatches();
    });

    it("should not trigger a batch on root run end and instead batch call with previous batch if blockOnRootRunFinalization is false", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          blockOnRootRunFinalization: false,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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
      const { dottedOrder: dottedOrder2 } = convertToDottedOrderFormat(
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

      expect(calls.length).toEqual(2);
      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);
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

      // Clean up any pending batches
      await client.awaitPendingTraceBatches();
    });

    it("should send traces above the batch size and see even batches", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          batchSizeBytesLimit: 10000,
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runIds = await Promise.all(
        [...Array(15)].map(async (_, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRun({
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

      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);

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

    it("should send more traces than the size limit and see even batches", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          batchSizeBytesLimit: 1000000,
          batchSizeLimit: 5,
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runIds = await Promise.all(
        [...Array(9)].map(async (_, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRun({
            id: runId,
            project_name: projectName,
            name: "test_run " + i,
            run_type: "llm",
            inputs: { text: "hello world " + i },
            trace_id: runId,
            dotted_order: dottedOrder,
          } as RunCreate);
          await client.createRun(params);
          return runId;
        })
      );

      await client.awaitPendingTraceBatches();

      expect(calls.length).toBe(2);

      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);

      const firstBatchBody = await parseMockRequestBody(
        calledRequestParam?.body
      );
      const secondBatchBody = await parseMockRequestBody(
        calledRequestParam2?.body
      );

      const initialBatchBody =
        firstBatchBody.post.length === 5 ? firstBatchBody : secondBatchBody;
      const followupBatchBody =
        firstBatchBody.post.length === 5 ? secondBatchBody : firstBatchBody;

      // Queue should drain as soon as size limit is reached,
      // sending both batches
      expect(initialBatchBody).toEqual({
        post: runIds.slice(0, 5).map((runId, i) =>
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
        post: runIds.slice(5).map((runId, i) =>
          expect.objectContaining({
            id: runId,
            run_type: "llm",
            inputs: {
              text: expect.stringContaining("hello world " + (i + 5)),
            },
            trace_id: runId,
          })
        ),
        patch: [],
      });
    });

    it("should sample and see proper batching", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          tracingSamplingRate: 0.5,
        },
        mockFetch
      );
      let counter = 0;
      jest.spyOn(client as any, "_shouldSample").mockImplementation(() => {
        counter += 1;
        return counter % 2 !== 0;
      });
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runParams = await Promise.all(
        [...Array(4)].map(async (_, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRun({
            id: runId,
            project_name: projectName,
            name: "test_run " + i,
            run_type: "llm",
            inputs: { text: "hello world " + i },
            trace_id: runId,
            dotted_order: dottedOrder,
          } as RunCreate);
          await client.createRun(params);
          return params;
        })
      );

      await client.awaitPendingTraceBatches();

      const calledRequestParam: any = calls[0][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      const batchBody = await parseMockRequestBody(calledRequestParam?.body);

      const childRunParams = await Promise.all(
        runParams.map(async (runParam, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRun({
            id: runId,
            project_name: projectName,
            name: "test_child_run " + i,
            run_type: "llm",
            inputs: { text: "child world " + i },
            trace_id: runParam.id,
            dotted_order: [runParam.dotted_order, dottedOrder].join("."),
          } as RunCreate);
          await client.createRun(params);
          await client.updateRun(runParam.id!, {
            outputs: { output: ["Hi"] },
            dotted_order: dottedOrder,
            trace_id: runParam.id,
            end_time: Math.floor(new Date().getTime() / 1000),
          });
          return params;
        })
      );

      await client.awaitPendingTraceBatches();

      const calledRequestParam2: any = calls[1][1];
      expect(calls[1][0]).toBe(expectedTraceURL);

      const batchBody2 = await parseMockRequestBody(calledRequestParam2?.body);

      expect(batchBody).toEqual({
        post: runParams
          .map((runParam, i) => {
            if (i % 2 === 0) {
              return expect.objectContaining({
                id: runParam.id,
                run_type: "llm",
                inputs: {
                  text: expect.stringContaining("hello world " + i),
                },
                trace_id: runParam.id,
              });
            } else {
              return undefined;
            }
          })
          .filter((item) => item !== undefined),
        patch: [],
      });

      expect(batchBody2).toEqual({
        post: childRunParams
          .map((childRunParam, i) => {
            if (i % 2 === 0) {
              return expect.objectContaining({
                id: childRunParam.id,
                run_type: "llm",
                inputs: {
                  text: expect.stringContaining("child world " + i),
                },
                trace_id: runParams[i].id,
              });
            } else {
              return undefined;
            }
          })
          .filter((item) => item !== undefined),
        patch: runParams
          .map((runParam, i) => {
            if (i % 2 === 0) {
              return expect.objectContaining({
                id: runParam.id,
                trace_id: runParam.id,
              });
            } else {
              return undefined;
            }
          })
          .filter((item) => item !== undefined),
      });
    });

    it("should flush traces in batches with manualFlushMode enabled", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          batchSizeBytesLimit: 10000,
          autoBatchTracing: true,
          manualFlushMode: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runIds = await Promise.all(
        [...Array(15)].map(async (_, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
            new Date().getTime() / 1000,
            runId
          );
          const params = mergeRuntimeEnvIntoRun({
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

      await new Promise((resolve) => setTimeout(resolve, 500));

      expect(calls.length).toBe(0);

      await client.flush();

      expect(calls.length).toBe(2);

      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);

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
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          batchSizeBytesLimit: 1,
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: {
          ...extraBatchIngestConfig,
        },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      const runIds = await Promise.all(
        [...Array(4)].map(async (_, i) => {
          const runId = uuidv4();
          const { dottedOrder } = convertToDottedOrderFormat(
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

      expect(calls.length).toEqual(4);

      const calledRequestParam: any = calls[0][1];
      const calledRequestParam2: any = calls[1][1];
      const calledRequestParam3: any = calls[2][1];
      const calledRequestParam4: any = calls[3][1];
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);
      expect(calls[2][0]).toBe(expectedTraceURL);
      expect(calls[3][0]).toBe(expectedTraceURL);

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

    it("Use multipart endpoint if info call fails", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest
        .spyOn(client as any, "_ensureServerInfo")
        .mockResolvedValue(undefined);
      const projectName = "__test_batch";

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];

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
      // When server info is unavailable, client defaults to multipart endpoint (the new default)
      expect(calls[0][0]).toBe(
        "https://api.smith.langchain.com/runs/multipart"
      );

      expect(calls.length).toBe(1);
    });

    it("Should handle circular values", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";
      const a: Record<string, any> = {};
      const b: Record<string, any> = {};
      a.b = b;
      b.a = a;

      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      const calledRequestParam: any = calls[0][1];
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
      expect(calls[0][0]).toBe(expectedTraceURL);

      expect(calls.length).toBe(1);
    });

    it("should retry multipart requests on 5xx errors", async () => {
      const calls: any[] = [];
      let callCount = 0;

      const mockFetch = jest.fn((...args: any[]) => {
        callCount++;
        // Only count calls to multipart endpoints, not info calls
        if (args[0]?.includes("/runs/")) {
          calls.push(args);

          // Fail first two attempts with 500, succeed on third
          if (callCount <= 2) {
            return Promise.resolve({
              ok: false,
              status: 500,
              statusText: "Internal Server Error",
              text: () => Promise.resolve("Server error"),
            } as Response);
          }
        }

        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve(""),
        } as Response);
      });

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );

      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });

      const projectName = "__test_batch";
      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      // Should have made 3 calls (2 failures + 1 success)
      expect(calls.length).toBe(3);
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);
      expect(calls[2][0]).toBe(expectedTraceURL);
    });

    it("should not retry multipart requests on 422 errors", async () => {
      const calls: any[] = [];

      const mockFetch = jest.fn((...args: any[]) => {
        // Only count calls to multipart endpoints, not info calls
        if (args[0]?.includes("/runs/")) {
          calls.push(args);

          // Always return 422 (should not retry)
          return Promise.resolve({
            ok: false,
            status: 422,
            statusText: "Unprocessable Entity",
            text: () => Promise.resolve("Validation error"),
          } as Response);
        }

        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve(""),
        } as Response);
      });

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );

      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });

      const projectName = "__test_batch";
      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      // Wait for batch processing to complete (and fail)
      await client.awaitPendingTraceBatches();

      // Should have made only 1 call (no retries for 422)
      expect(calls.length).toBe(1);
      expect(calls[0][0]).toBe(expectedTraceURL);
    });

    it("should retry multipart requests on 429 errors", async () => {
      const calls: any[] = [];
      let callCount = 0;

      const mockFetch = jest.fn((...args: any[]) => {
        callCount++;
        // Only count calls to multipart endpoints, not info calls
        if (args[0]?.includes("/runs/")) {
          calls.push(args);

          // Fail first two attempts with 429, succeed on third
          if (callCount <= 2) {
            return Promise.resolve({
              ok: false,
              status: 429,
              statusText: "Too Many Requests",
              text: () => Promise.resolve("Rate limited"),
              headers: {
                get: (name: string) => (name === "retry-after" ? "1" : null),
              },
            } as Response);
          }
        }

        return Promise.resolve({
          ok: true,
          status: 200,
          text: () => Promise.resolve(""),
        } as Response);
      });

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
        },
        mockFetch
      );

      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });

      const projectName = "__test_batch";
      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
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

      // Should have made 3 calls (2 failures + 1 success)
      expect(calls.length).toBe(3);
      expect(calls[0][0]).toBe(expectedTraceURL);
      expect(calls[1][0]).toBe(expectedTraceURL);
      expect(calls[2][0]).toBe(expectedTraceURL);
    });

    it("should drop runs when maxIngestMemoryBytes is exceeded in AutoBatchQueue", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);
      const consoleSpy = jest
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      // Set a very low queue size limit (1000 bytes)
      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          maxIngestMemoryBytes: 1000,
          manualFlushMode: true, // Prevent auto-flushing so we can test the limit
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      // Create runs until we exceed the queue size limit
      const runIds: string[] = [];
      const createPromises: Promise<void>[] = [];
      for (let i = 0; i < 10; i++) {
        const runId = uuidv4();
        const { dottedOrder } = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        const promise = client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "x".repeat(200) }, // Make each run ~200+ bytes
          trace_id: runId,
          dotted_order: dottedOrder,
        });
        createPromises.push(promise);
        runIds.push(runId);
      }

      // All promises should resolve immediately without blocking, even dropped ones
      await Promise.all(createPromises);

      // Should have warned about dropped runs
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining("AutoBatchQueue size limit")
      );
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining("Dropping run")
      );

      // Clean up
      consoleSpy.mockRestore();
      await client.flush();
    });

    it("should allow a single large run that exceeds the queue size limit", async () => {
      const calls: any[] = [];
      const mockFetch = createMockFetch(calls);
      const consoleSpy = jest
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      // Set a low queue size limit (1000 bytes)
      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          maxIngestMemoryBytes: 1000,
          manualFlushMode: true,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      // Create a single large run that exceeds the limit (queue is empty)
      const runId = uuidv4();
      const { dottedOrder } = convertToDottedOrderFormat(
        new Date().getTime() / 1000,
        runId
      );
      await client.createRun({
        id: runId,
        project_name: projectName,
        name: "large_run",
        run_type: "llm",
        inputs: { text: "x".repeat(2000) }, // 2000+ bytes, exceeds 1000 byte limit
        trace_id: runId,
        dotted_order: dottedOrder,
      });

      // Should NOT have warned since the queue was empty
      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining("AutoBatchQueue size limit")
      );

      // The run should be in the queue
      expect((client as any).autoBatchQueue.items.length).toBe(1);
      expect((client as any).autoBatchQueue.sizeBytes).toBeGreaterThan(1000);

      // Clean up
      consoleSpy.mockRestore();
      await client.flush();
    });

    it("should drop batches when maxIngestMemoryBytes is exceeded", async () => {
      const calls: any[] = [];
      let callCount = 0;
      const mockFetch = jest.fn(
        async (url: string | URL | Request, init?: RequestInit) => {
          calls.push([url, init]);
          callCount++;
          // Block first few requests to simulate slow network and cause queue buildup
          if (callCount <= 2) {
            await new Promise((resolve) => setTimeout(resolve, 2000));
          }
          return {
            ok: true,
            status: 200,
            json: async () => ({}),
            text: async () => "{}",
          } as Response;
        }
      );

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const consoleWarnSpy = jest
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      // Set a low maxIngestMemoryBytes limit (2000 bytes)
      // This will allow ~4-5 batches before dropping
      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          maxIngestMemoryBytes: 2000,
          traceBatchConcurrency: 1, // Low concurrency to cause queue buildup
          batchSizeBytesLimit: 500, // Small batches
          batchSizeLimit: 3, // Few items per batch
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      // Create many runs to trigger multiple batches
      const runIds: string[] = [];
      for (let i = 0; i < 20; i++) {
        const runId = uuidv4();
        const { dottedOrder } = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        await client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "x".repeat(200) }, // Make each run ~200+ bytes
          trace_id: runId,
          dotted_order: dottedOrder,
        });
        runIds.push(runId);
      }

      // Wait a bit for batches to start processing
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Should have rejected some batches due to queue size limit
      // Errors can appear in either console.error (from _processBatch) or console.warn (from _sendMultipartRequest)
      const errorCalled = consoleErrorSpy.mock.calls.some(
        (call) =>
          call[0]?.includes?.("Error exporting batch") &&
          call[1]?.message?.includes?.("Queue size limit")
      );
      const warnCalled = consoleWarnSpy.mock.calls.some((call) =>
        call[0]?.includes?.("Queue size limit")
      );

      expect(errorCalled || warnCalled).toBe(true);

      // Clean up
      consoleErrorSpy.mockRestore();
      consoleWarnSpy.mockRestore();
      await client.awaitPendingTraceBatches();
    });

    it("should decrement queue size after batches complete", async () => {
      const calls: any[] = [];
      let completedCalls = 0;
      const mockFetch = jest.fn(
        async (url: string | URL | Request, init?: RequestInit) => {
          calls.push([url, init]);
          await new Promise((resolve) => setTimeout(resolve, 50));
          completedCalls++;
          return {
            ok: true,
            status: 200,
            json: async () => ({}),
            text: async () => "{}",
          } as Response;
        }
      );

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          maxIngestMemoryBytes: 10000,
          traceBatchConcurrency: 2,
          batchSizeBytesLimit: 500,
          batchSizeLimit: 3,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      // Create runs to build up queue
      for (let i = 0; i < 10; i++) {
        const runId = uuidv4();
        const { dottedOrder } = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        await client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "x".repeat(200) },
          trace_id: runId,
          dotted_order: dottedOrder,
        });
      }

      // Wait for some batches to start processing
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Check that queue size is non-zero while processing
      const queueSizeDuringProcessing = (client as any).batchIngestCaller
        .queueSizeBytes;
      expect(queueSizeDuringProcessing).toBeGreaterThan(0);

      // Wait for all batches to complete
      await client.awaitPendingTraceBatches();

      // Queue size should be zero after all complete
      const queueSizeAfterCompletion = (client as any).batchIngestCaller
        .queueSizeBytes;
      expect(queueSizeAfterCompletion).toBe(0);
      expect(completedCalls).toBeGreaterThan(0);
    });

    it("should decrement queue size even when requests timeout", async () => {
      const calls: any[] = [];
      const mockFetch = jest.fn(
        async (
          url: string | URL | Request,
          init?: RequestInit
        ): Promise<Response> => {
          calls.push([url, init]);
          // Respect the abort signal from timeout
          const signal = init?.signal;
          if (signal) {
            return new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                resolve({
                  ok: true,
                  status: 200,
                  json: async () => ({}),
                  text: async () => "{}",
                } as Response);
              }, 120000);

              signal.addEventListener("abort", () => {
                clearTimeout(timeoutId);
                reject(new Error("TimeoutError: The operation was aborted"));
              });
            });
          }
          return {
            ok: true,
            status: 200,
            json: async () => ({}),
            text: async () => "{}",
          } as Response;
        }
      );

      const consoleErrorSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const consoleWarnSpy = jest
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      const client = createClient(
        {
          apiKey: "test-api-key",
          autoBatchTracing: true,
          maxIngestMemoryBytes: 10000,
          timeout_ms: 100, // Very short timeout to trigger quickly
          traceBatchConcurrency: 2,
          batchSizeBytesLimit: 500,
          batchSizeLimit: 3,
        },
        mockFetch
      );
      jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
        version: "foo",
        batch_ingest_config: { ...extraBatchIngestConfig },
        instance_flags: { ...extraInstanceFlags },
      });
      const projectName = "__test_batch";

      // Create runs that will timeout
      for (let i = 0; i < 5; i++) {
        const runId = uuidv4();
        const { dottedOrder } = convertToDottedOrderFormat(
          new Date().getTime() / 1000,
          runId
        );
        await client.createRun({
          id: runId,
          project_name: projectName,
          name: "test_run " + i,
          run_type: "llm",
          inputs: { text: "x".repeat(200) },
          trace_id: runId,
          dotted_order: dottedOrder,
        });
      }

      // Wait for requests to timeout and batches to complete (with errors)
      await client.awaitPendingTraceBatches();

      // Queue size should be zero even though requests timed out
      const queueSizeAfterTimeout = (client as any).batchIngestCaller
        .queueSizeBytes;
      expect(queueSizeAfterTimeout).toBe(0);

      // Should have logged timeout errors (in either console.error or console.warn)
      const errorCalled = consoleErrorSpy.mock.calls.some(
        (call) =>
          call[0]?.includes?.("Error exporting batch") &&
          call[1]?.message?.includes?.("TimeoutError")
      );
      const warnCalled = consoleWarnSpy.mock.calls.some((call) =>
        call[0]?.includes?.("TimeoutError")
      );

      expect(errorCalled || warnCalled).toBe(true);

      consoleErrorSpy.mockRestore();
      consoleWarnSpy.mockRestore();
    });
  }
);
