/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  jest,
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
} from "@jest/globals";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../client.js";

async function makeTmpDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), "ls-failed-traces-test-"));
}

async function listDir(dir: string): Promise<string[]> {
  return fs.readdir(dir);
}

async function readEnvelope(dir: string, filename: string) {
  const raw = await fs.readFile(path.join(dir, filename), "utf8");
  return JSON.parse(raw) as {
    version: number;
    endpoint: string;
    headers: Record<string, string>;
    body_base64: string;
  };
}

function makeRunCreate() {
  const id = uuidv4();
  return {
    id,
    name: "test_run",
    run_type: "chain" as const,
    inputs: { x: 1 },
    trace_id: id,
    dotted_order: id,
  };
}

describe("Client._writeTraceToFallbackDir", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await makeTmpDir();
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("writes a self-contained JSON envelope", async () => {
    const body = Buffer.from("hello world");
    const headers = { "Content-Type": "multipart/form-data; boundary=abc" };
    await (Client as any)._writeTraceToFallbackDir(
      tmpDir,
      body,
      headers,
      "runs/multipart"
    );

    const files = await listDir(tmpDir);
    expect(files).toHaveLength(1);
    expect(files[0]).toMatch(/\.json$/);

    const envelope = await readEnvelope(tmpDir, files[0]);
    expect(envelope.version).toBe(1);
    expect(envelope.endpoint).toBe("runs/multipart");
    expect(envelope.headers).toEqual(headers);
    expect(Buffer.from(envelope.body_base64, "base64").toString()).toBe(
      "hello world"
    );
  });

  it("swallows write errors instead of throwing", async () => {
    const blocker = path.join(tmpDir, "blocker");
    await fs.writeFile(blocker, "not a dir");
    await expect(
      (Client as any)._writeTraceToFallbackDir(
        path.join(blocker, "sub"),
        Buffer.alloc(0),
        {},
        "runs/multipart"
      )
    ).resolves.not.toThrow();
  });

  it("evicts oldest files (FIFO) when directory exceeds maxBytes", async () => {
    // Each envelope is ~149 bytes. Budget of 350 allows 2 (298 bytes) but not
    // 3 (447 bytes), so the 3rd write evicts the oldest → 2 files remain.
    const body = Buffer.from("x".repeat(20));
    const headers = { "Content-Type": "multipart/form-data; boundary=abc" };
    for (let i = 0; i < 3; i++) {
      await (Client as any)._writeTraceToFallbackDir(
        tmpDir,
        body,
        headers,
        "runs/multipart",
        350
      );
    }
    const files = await listDir(tmpDir);
    expect(files.length).toBeLessThan(3);
    expect(files.length).toBeGreaterThan(0);
  });
});

describe("Client multipart failure → fallback dir", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await makeTmpDir();
    jest.clearAllMocks();
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
    jest.restoreAllMocks();
  });

  it("writes a multipart envelope when the multipart upload fails", async () => {
    const mockFetch = jest.fn((..._args: any[]) =>
      Promise.resolve({
        ok: false,
        status: 500,
        text: () => Promise.resolve("Server error"),
      } as Response)
    ) as jest.MockedFunction<typeof fetch>;

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch,
      callerOptions: { maxRetries: 0 },
    });
    (client as any).failedTracesDir = tmpDir;

    jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
      version: "foo",
      batch_ingest_config: { use_multipart_endpoint: true },
      instance_flags: { gzip_body_enabled: false },
    });

    const run = makeRunCreate();
    await (client as any)._processBatch([
      {
        action: "create",
        item: run,
        apiKey: undefined,
        apiUrl: undefined,
        size: 100,
      },
    ]);

    const files = await listDir(tmpDir);
    expect(files).toHaveLength(1);

    const envelope = await readEnvelope(tmpDir, files[0]);
    expect(envelope.endpoint).toBe("runs/multipart");
    expect(envelope.headers["Content-Type"]).toMatch(
      /^multipart\/form-data; boundary=/
    );
    const decoded = Buffer.from(envelope.body_base64, "base64").toString();
    expect(decoded).toContain(run.id);
  });

  it("does not write a file when the multipart upload succeeds", async () => {
    const mockFetch = jest.fn((..._args: any[]) =>
      Promise.resolve({
        ok: true,
        status: 200,
        text: () => Promise.resolve(""),
      } as Response)
    ) as jest.MockedFunction<typeof fetch>;

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch,
    });
    (client as any).failedTracesDir = tmpDir;

    jest.spyOn(client as any, "_ensureServerInfo").mockResolvedValue({
      version: "foo",
      batch_ingest_config: { use_multipart_endpoint: true },
      instance_flags: { gzip_body_enabled: false },
    });

    await (client as any)._processBatch([
      {
        action: "create",
        item: makeRunCreate(),
        apiKey: undefined,
        apiUrl: undefined,
        size: 100,
      },
    ]);

    expect(await listDir(tmpDir)).toHaveLength(0);
  });
});

describe("LANGSMITH_FAILED_TRACES_DIR environment variable", () => {
  it("sets failedTracesDir from the env var", () => {
    const original = process.env.LANGSMITH_FAILED_TRACES_DIR;
    process.env.LANGSMITH_FAILED_TRACES_DIR = "/some/path";
    try {
      const client = new Client({ apiKey: "test" });
      expect((client as any).failedTracesDir).toBe("/some/path");
    } finally {
      if (original === undefined)
        delete process.env.LANGSMITH_FAILED_TRACES_DIR;
      else process.env.LANGSMITH_FAILED_TRACES_DIR = original;
    }
  });

  it("leaves failedTracesDir undefined when the env var is absent", () => {
    const original = process.env.LANGSMITH_FAILED_TRACES_DIR;
    delete process.env.LANGSMITH_FAILED_TRACES_DIR;
    try {
      const client = new Client({ apiKey: "test" });
      expect((client as any).failedTracesDir).toBeUndefined();
    } finally {
      if (original !== undefined)
        process.env.LANGSMITH_FAILED_TRACES_DIR = original;
    }
  });
});
