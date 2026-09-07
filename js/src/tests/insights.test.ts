import { jest } from "@jest/globals";

import { Client } from "../client.js";

const PROJECT_ID = "55555555-5555-5555-5555-555555555555";
const TENANT_ID = "44444444-4444-4444-4444-444444444444";
const JOB_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    statusText: "OK",
    headers: { "content-type": "application/json" },
  });
}

const secretsPayload = [{ key: "OPENAI_API_KEY" }];
const jobPayload = {
  id: JOB_ID,
  name: "test-report",
  status: "queued",
  error: null,
};
const projectPayload = {
  id: PROJECT_ID,
  name: "my-agent",
  tenant_id: TENANT_ID,
  start_time: "2026-02-12T22:14:48.648851Z",
  reference_dataset_id: null,
};

function makeClient(responses: unknown[]) {
  const mockFetch = jest.fn<typeof fetch>();
  for (const payload of responses) {
    mockFetch.mockResolvedValueOnce(jsonResponse(payload));
  }
  const client = new Client({
    apiUrl: "http://localhost:1984",
    apiKey: "test-api-key",
    fetchImplementation: mockFetch,
  });
  return { client, mockFetch };
}

describe("generateInsights", () => {
  it("posts to an existing project and omits unset run selection", async () => {
    // secrets -> create job -> resolve tenant
    const { client, mockFetch } = makeClient([
      secretsPayload,
      jobPayload,
      [projectPayload],
    ]);

    const report = await client.generateInsights({
      projectId: PROJECT_ID,
      name: "Conversation Topics",
      instructions: "What do users ask about?",
      lastNHours: 24,
      filter: "eq(is_root, true)",
      sample: 0.1,
    });

    const [url, init] = mockFetch.mock.calls[1];
    expect(url).toBe(`http://localhost:1984/sessions/${PROJECT_ID}/insights`);
    expect(init?.method).toBe("POST");

    const body = JSON.parse(init?.body as string);
    expect(body.last_n_hours).toBe(24);
    expect(body.filter).toBe("eq(is_root, true)");
    expect(body.sample).toBe(0.1);
    expect(body).not.toHaveProperty("start_time");
    expect(body).not.toHaveProperty("end_time");
    expect(
      body.user_context["What would you like to learn about your agent?"],
    ).toBe("What do users ask about?");

    expect(report.id).toBe(JOB_ID);
    expect(report.project_id).toBe(PROJECT_ID);
    expect(report.link).toBe(
      `http://localhost:3000/o/${TENANT_ID}/projects/p/${PROJECT_ID}` +
        `?tab=3&clusterJobId=${JOB_ID}`,
    );
  });

  it("resolves projectName to a project id", async () => {
    // secrets -> read project -> create job -> resolve tenant
    const { client, mockFetch } = makeClient([
      secretsPayload,
      [projectPayload],
      jobPayload,
      [projectPayload],
    ]);

    await client.generateInsights({ projectName: "my-agent" });

    expect(mockFetch.mock.calls[1][0]).toBe(
      "http://localhost:1984/sessions?name=my-agent",
    );
    expect(mockFetch.mock.calls[2][0]).toBe(
      `http://localhost:1984/sessions/${PROJECT_ID}/insights`,
    );
  });

  it("serializes Date run selection bounds", async () => {
    const { client, mockFetch } = makeClient([
      secretsPayload,
      jobPayload,
      [projectPayload],
    ]);

    await client.generateInsights({
      projectId: PROJECT_ID,
      startTime: new Date("2026-01-01T00:00:00.000Z"),
      endTime: "2026-01-02T00:00:00.000Z",
    });

    const body = JSON.parse(mockFetch.mock.calls[1][1]?.body as string);
    expect(body.start_time).toBe("2026-01-01T00:00:00.000Z");
    expect(body.end_time).toBe("2026-01-02T00:00:00.000Z");
  });

  it("uses the supplied trace structure", async () => {
    const { client, mockFetch } = makeClient([
      secretsPayload,
      jobPayload,
      [projectPayload],
    ]);

    await client.generateInsights({
      projectId: PROJECT_ID,
      traceStructure: "Look at outputs.answer.",
    });

    const body = JSON.parse(mockFetch.mock.calls[1][1]?.body as string);
    expect(body.user_context["How are your agent traces structured?"]).toBe(
      "Look at outputs.answer.",
    );
  });

  it.each([
    [{}],
    [{ projectId: PROJECT_ID, projectName: "my-agent" }],
    [{ chatHistories: [], projectName: "my-agent" }],
  ])("requires exactly one source (%j)", async (args) => {
    const { client, mockFetch } = makeClient([]);

    await expect(client.generateInsights(args)).rejects.toThrow(
      "Must provide exactly one of chatHistories, projectName, or projectId",
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects run selection alongside chatHistories", async () => {
    const { client, mockFetch } = makeClient([]);

    await expect(
      client.generateInsights({ chatHistories: [], lastNHours: 24 }),
    ).rejects.toThrow("cannot be used with chatHistories");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("pollInsights", () => {
  it("polls until the job succeeds", async () => {
    const { client, mockFetch } = makeClient([
      { ...jobPayload, status: "running" },
      { ...jobPayload, status: "success" },
      [projectPayload],
    ]);

    const report = await client.pollInsights({
      id: JOB_ID,
      projectId: PROJECT_ID,
      rate: 0.01,
    });

    expect(report.status).toBe("success");
    expect(mockFetch.mock.calls[0][0]).toBe(
      `http://localhost:1984/sessions/${PROJECT_ID}/insights/${JOB_ID}?`,
    );
    expect(mockFetch.mock.calls[1][1]?.method).toBe("GET");
  });

  it("throws the job error", async () => {
    const { client } = makeClient([
      { ...jobPayload, status: "error", error: "boom" },
    ]);

    await expect(
      client.pollInsights({ id: JOB_ID, projectId: PROJECT_ID, rate: 0.01 }),
    ).rejects.toThrow("Failed to generate insights: boom");
  });

  it("requires report or both id and projectId", async () => {
    const { client } = makeClient([]);

    await expect(client.pollInsights({ id: JOB_ID })).rejects.toThrow(
      "Must provide either report or both id and projectId",
    );
  });
});

describe("getInsightsReport", () => {
  it("skips run fetching when includeRuns is false", async () => {
    const { client, mockFetch } = makeClient([
      {
        id: JOB_ID,
        name: "test-report",
        status: "success",
        clusters: [
          {
            id: "33333333-3333-3333-3333-333333333333",
            level: 0,
            name: "cluster-a",
            description: "Cluster A",
            num_runs: 2,
          },
        ],
      },
    ]);

    const result = await client.getInsightsReport({
      id: JOB_ID,
      projectId: PROJECT_ID,
      includeRuns: false,
    });

    expect(result.clusters).toHaveLength(1);
    expect(result.runs).toEqual([]);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("paginates runs when includeRuns is true", async () => {
    const page = (n: number) => ({
      runs: [{ id: `run-${n}-1` }, { id: `run-${n}-2` }],
    });
    const { client, mockFetch } = makeClient([
      { id: JOB_ID, name: "test-report", status: "success", clusters: [] },
      page(1),
    ]);

    const result = await client.getInsightsReport({
      id: JOB_ID,
      projectId: PROJECT_ID,
    });

    // Short page ends pagination, so exactly one runs request is made.
    expect(result.runs).toHaveLength(2);
    expect(mockFetch.mock.calls[1][0]).toContain(
      `/sessions/${PROJECT_ID}/insights/${JOB_ID}/runs`,
    );
  });
});
