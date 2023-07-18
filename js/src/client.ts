import * as uuid from "uuid";
import { AsyncCaller, AsyncCallerParams } from "./utils/async_caller.js";
import {
  Dataset,
  Example,
  ExampleCreate,
  ExampleUpdate,
  Feedback,
  KVMap,
  Run,
  RunCreate,
  RunType,
  RunUpdate,
  ScoreType,
  TracerSession,
  TracerSessionResult,
  ValueType,
  DataType,
} from "./schemas.js";
import { getEnvironmentVariable, getRuntimeEnvironment } from "./utils/env.js";
import { RunEvaluator } from "./evaluation/evaluator.js";

interface ClientConfig {
  apiUrl?: string;
  apiKey?: string;
  callerOptions?: AsyncCallerParams;
  timeout_ms?: number;
}

interface ListRunsParams {
  projectId?: string;
  projectName?: string;
  executionOrder?: number;
  parentRunId?: string;
  referenceExampleId?: string;
  datasetId?: string;
  startTime?: Date;
  endTime?: Date;
  runType?: RunType;
  error?: boolean;
  id?: string[];
  limit?: number;
  offset?: number;
  query?: string;
  filter?: string;
  orderBy?: string[];
}
interface UploadCSVParams {
  csvFile: Blob;
  fileName: string;
  inputKeys: string[];
  outputKeys: string[];
  description?: string;
  dataType?: DataType;
  name?: string;
}

interface feedback_source {
  type: string;
  metadata?: KVMap;
}

interface FeedbackCreate {
  id: string;
  run_id: string;
  key: string;
  score?: ScoreType;
  value?: ValueType;
  correction?: string | object | null;
  comment?: string | null;
  feedback_source?: feedback_source | KVMap | null;
}

interface CreateRunParams {
  name: string;
  inputs: KVMap;
  run_type: RunType;
  execution_order?: number;
  id?: string;
  start_time?: number;
  end_time?: number;
  extra?: KVMap;
  error?: string;
  serialized?: object;
  outputs?: KVMap;
  reference_example_id?: string;
  child_runs?: RunCreate[];
  parent_run_id?: string;
  project_name?: string;
}
// utility functions
const isLocalhost = (url: string): boolean => {
  const strippedUrl = url.replace("http://", "").replace("https://", "");
  const hostname = strippedUrl.split("/")[0].split(":")[0];
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1"
  );
};

const raiseForStatus = async (response: Response, operation: string) => {
  // consume the response body to release the connection
  // https://undici.nodejs.org/#/?id=garbage-collection
  const body = await response.text();
  if (!response.ok) {
    throw new Error(
      `Failed to ${operation}: ${response.status} ${response.statusText} ${body}`
    );
  }
};

async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

function trimQuotes(str?: string): string | undefined {
  if (str === undefined) {
    return undefined;
  }
  return str
    .trim()
    .replace(/^"(.*)"$/, "$1")
    .replace(/^'(.*)'$/, "$1");
}

export class Client {
  private apiKey?: string;

  private apiUrl: string;

  private caller: AsyncCaller;

  private timeout_ms: number;

  constructor(config: ClientConfig = {}) {
    const defaultConfig = Client.getDefaultClientConfig();

    this.apiUrl = trimQuotes(config.apiUrl ?? defaultConfig.apiUrl) ?? "";
    this.apiKey = trimQuotes(config.apiKey ?? defaultConfig.apiKey);
    this.validateApiKeyIfHosted();
    this.timeout_ms = config.timeout_ms ?? 4000;
    this.caller = new AsyncCaller(config.callerOptions ?? {});
  }

  public static getDefaultClientConfig(): { apiUrl: string; apiKey?: string } {
    const apiKey = getEnvironmentVariable("LANGCHAIN_API_KEY");
    const apiUrl =
      getEnvironmentVariable("LANGCHAIN_ENDPOINT") ??
      (apiKey ? "https://api.smith.langchain.com" : "http://localhost:1984");
    return {
      apiUrl: apiUrl,
      apiKey: apiKey,
    };
  }

  private validateApiKeyIfHosted(): void {
    const isLocal = isLocalhost(this.apiUrl);
    if (!isLocal && !this.apiKey) {
      throw new Error(
        "API key must be provided when using hosted LangSmith API"
      );
    }
  }

  private get headers(): { [header: string]: string } {
    const headers: { [header: string]: string } = {};
    if (this.apiKey) {
      headers["x-api-key"] = `${this.apiKey}`;
    }
    return headers;
  }

  private async _get<T>(
    path: string,
    queryParams?: URLSearchParams
  ): Promise<T> {
    const paramsString = queryParams?.toString() ?? "";
    const url = `${this.apiUrl}${path}?${paramsString}`;
    const response = await this.caller.call(fetch, url, {
      method: "GET",
      headers: this.headers,
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to fetch ${path}: ${response.status} ${response.statusText}`
      );
    }
    return response.json() as T;
  }
  private async *_getPaginated<T>(
    path: string,
    queryParams: URLSearchParams = new URLSearchParams()
  ): AsyncIterable<T[]> {
    let offset = Number(queryParams.get("offset")) || 0;
    const limit = Number(queryParams.get("limit")) || 100;
    while (true) {
      queryParams.set("offset", String(offset));
      queryParams.set("limit", String(limit));

      const url = `${this.apiUrl}${path}?${queryParams}`;
      const response = await this.caller.call(fetch, url, {
        method: "GET",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      });
      if (!response.ok) {
        throw new Error(
          `Failed to fetch ${path}: ${response.status} ${response.statusText}`
        );
      }
      const items: T[] = await response.json();

      if (items.length === 0) {
        break;
      }
      yield items;

      if (items.length < limit) {
        break;
      }
      offset += items.length;
    }
  }

  public async createRun(run: CreateRunParams): Promise<void> {
    const headers = { ...this.headers, "Content-Type": "application/json" };
    const extra = run.extra ?? {};
    const runtimeEnv = await getRuntimeEnvironment();
    const session_name = run.project_name;
    delete run.project_name;
    const runCreate: RunCreate = {
      session_name,
      ...run,
      extra: {
        ...run.extra,
        runtime: {
          ...runtimeEnv,
          ...extra.runtime,
        },
      },
    };
    const response = await this.caller.call(fetch, `${this.apiUrl}/runs`, {
      method: "POST",
      headers,
      body: JSON.stringify(runCreate),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    await raiseForStatus(response, "create run");
  }

  public async updateRun(runId: string, run: RunUpdate): Promise<void> {
    const headers = { ...this.headers, "Content-Type": "application/json" };
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/runs/${runId}`,
      {
        method: "PATCH",
        headers,
        body: JSON.stringify(run),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(response, "update run");
  }

  public async readRun(
    runId: string,
    { loadChildRuns }: { loadChildRuns: boolean } = { loadChildRuns: false }
  ): Promise<Run> {
    let run = await this._get<Run>(`/runs/${runId}`);
    if (loadChildRuns && run.child_run_ids) {
      run = await this._loadChildRuns(run);
    }
    return run;
  }

  private async _loadChildRuns(run: Run): Promise<Run> {
    const childRuns = await toArray(this.listRuns({ id: run.child_run_ids }));
    const treemap: { [key: string]: Run[] } = {};
    const runs: { [key: string]: Run } = {};
    childRuns.sort((a, b) => a.execution_order - b.execution_order);
    for (const childRun of childRuns) {
      if (
        childRun.parent_run_id === null ||
        childRun.parent_run_id === undefined
      ) {
        throw new Error(`Child run ${childRun.id} has no parent`);
      }
      if (!(childRun.parent_run_id in treemap)) {
        treemap[childRun.parent_run_id] = [];
      }
      treemap[childRun.parent_run_id].push(childRun);
      runs[childRun.id] = childRun;
    }
    run.child_runs = treemap[run.id] || [];
    for (const runId in treemap) {
      if (runId !== run.id) {
        runs[runId].child_runs = treemap[runId];
      }
    }
    return run;
  }

  public async *listRuns({
    projectId,
    projectName,
    parentRunId,
    referenceExampleId,
    datasetId,
    startTime,
    endTime,
    executionOrder,
    runType,
    error,
    id,
    limit,
    offset,
    query,
    filter,
    orderBy,
  }: ListRunsParams): AsyncIterable<Run> {
    const queryParams = new URLSearchParams();
    let projectId_ = projectId;
    if (projectName) {
      if (projectId) {
        throw new Error("Only one of projectId or projectName may be given");
      }
      projectId_ = (await this.readProject({ projectName })).id;
    }
    if (projectId_) {
      queryParams.append("session", projectId_);
    }
    if (parentRunId) {
      queryParams.append("parent_run", parentRunId);
    }
    if (referenceExampleId) {
      queryParams.append("reference_example", referenceExampleId);
    }
    if (datasetId) {
      queryParams.append("dataset", datasetId);
    }
    if (startTime) {
      queryParams.append("start_time", startTime.toISOString());
    }
    if (endTime) {
      queryParams.append("end_time", endTime.toISOString());
    }
    if (executionOrder) {
      queryParams.append("execution_order", executionOrder.toString());
    }
    if (runType) {
      queryParams.append("run_type", runType);
    }
    if (error !== undefined) {
      queryParams.append("error", error.toString());
    }
    if (id !== undefined) {
      for (const id_ of id) {
        queryParams.append("id", id_);
      }
    }
    if (limit !== undefined) {
      queryParams.append("limit", limit.toString());
    }
    if (offset !== undefined) {
      queryParams.append("offset", offset.toString());
    }
    if (query !== undefined) {
      queryParams.append("query", query);
    }
    if (filter !== undefined) {
      queryParams.append("filter", filter);
    }
    if (orderBy !== undefined) {
      orderBy.map((order) => queryParams.append("order_by", order));
    }

    for await (const runs of this._getPaginated<Run>("/runs", queryParams)) {
      yield* runs;
    }
  }

  public async deleteRun(runId: string): Promise<void> {
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/runs/${runId}`,
      {
        method: "DELETE",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(response, "delete run");
  }

  public async createProject({
    projectName,
    projectExtra,
    upsert,
  }: {
    projectName: string;
    projectExtra?: object;
    upsert?: boolean;
  }): Promise<TracerSession> {
    const upsert_ = upsert ? `?upsert=true` : "";
    const endpoint = `${this.apiUrl}/sessions${upsert_}`;
    const body: Record<string, object | string> = {
      name: projectName,
    };
    if (projectExtra !== undefined) {
      body["extra"] = projectExtra;
    }
    const response = await this.caller.call(fetch, endpoint, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(
        `Failed to create session ${projectName}: ${response.status} ${response.statusText}`
      );
    }
    return result as TracerSession;
  }

  public async readProject({
    projectId,
    projectName,
  }: {
    projectId?: string;
    projectName?: string;
  }): Promise<TracerSessionResult> {
    let path = "/sessions";
    const params = new URLSearchParams();
    if (projectId !== undefined && projectName !== undefined) {
      throw new Error("Must provide either projectName or projectId, not both");
    } else if (projectId !== undefined) {
      path += `/${projectId}`;
    } else if (projectName !== undefined) {
      params.append("name", projectName);
    } else {
      throw new Error("Must provide projectName or projectId");
    }

    const response = await this._get<TracerSession | TracerSession[]>(
      path,
      params
    );
    let result: TracerSession;
    if (Array.isArray(response)) {
      if (response.length === 0) {
        throw new Error(
          `Project[id=${projectId}, name=${projectName}] not found`
        );
      }
      result = response[0] as TracerSessionResult;
    } else {
      result = response as TracerSessionResult;
    }
    return result;
  }

  public async *listProjects(): AsyncIterable<TracerSession> {
    for await (const projects of this._getPaginated<TracerSession>(
      "/sessions"
    )) {
      yield* projects;
    }
  }

  public async deleteProject({
    projectId,
    projectName,
  }: {
    projectId?: string;
    projectName?: string;
  }): Promise<void> {
    let projectId_: string | undefined;
    if (projectId === undefined && projectName === undefined) {
      throw new Error("Must provide projectName or projectId");
    } else if (projectId !== undefined && projectName !== undefined) {
      throw new Error("Must provide either projectName or projectId, not both");
    } else if (projectId === undefined) {
      projectId_ = (await this.readProject({ projectName })).id;
    } else {
      projectId_ = projectId;
    }
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/sessions/${projectId_}`,
      {
        method: "DELETE",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(
      response,
      `delete session ${projectId_} (${projectName})`
    );
  }

  public async uploadCsv({
    csvFile,
    fileName,
    inputKeys,
    outputKeys,
    description,
    dataType,
    name,
  }: UploadCSVParams): Promise<Dataset> {
    const url = `${this.apiUrl}/datasets/upload`;
    const formData = new FormData();
    formData.append("file", csvFile, fileName);
    inputKeys.forEach((key) => {
      formData.append("input_keys", key);
    });

    outputKeys.forEach((key) => {
      formData.append("output_keys", key);
    });
    if (description) {
      formData.append("description", description);
    }
    if (dataType) {
      formData.append("data_type", dataType);
    }
    if (name) {
      formData.append("name", name);
    }

    const response = await this.caller.call(fetch, url, {
      method: "POST",
      headers: this.headers,
      body: formData,
      signal: AbortSignal.timeout(this.timeout_ms),
    });

    if (!response.ok) {
      const result = await response.json();
      if (result.detail && result.detail.includes("already exists")) {
        throw new Error(`Dataset ${fileName} already exists`);
      }
      throw new Error(
        `Failed to upload CSV: ${response.status} ${response.statusText}`
      );
    }

    const result = await response.json();
    return result as Dataset;
  }

  public async createDataset(
    name: string,
    {
      description,
      dataType,
    }: { description?: string; dataType?: DataType } = {}
  ): Promise<Dataset> {
    const body: KVMap = {
      name,
      description,
    };
    if (dataType) {
      body.data_type = dataType;
    }
    const response = await this.caller.call(fetch, `${this.apiUrl}/datasets`, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeout_ms),
    });

    if (!response.ok) {
      const result = await response.json();
      if (result.detail && result.detail.includes("already exists")) {
        throw new Error(`Dataset ${name} already exists`);
      }
      throw new Error(
        `Failed to create dataset ${response.status} ${response.statusText}`
      );
    }

    const result = await response.json();
    return result as Dataset;
  }

  public async readDataset({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  }): Promise<Dataset> {
    let path = "/datasets";
    // limit to 1 result
    const params = new URLSearchParams({ limit: "1" });
    if (datasetId !== undefined && datasetName !== undefined) {
      throw new Error("Must provide either datasetName or datasetId, not both");
    } else if (datasetId !== undefined) {
      path += `/${datasetId}`;
    } else if (datasetName !== undefined) {
      params.append("name", datasetName);
    } else {
      throw new Error("Must provide datasetName or datasetId");
    }
    const response = await this._get<Dataset | Dataset[]>(path, params);
    let result: Dataset;
    if (Array.isArray(response)) {
      if (response.length === 0) {
        throw new Error(
          `Dataset[id=${datasetId}, name=${datasetName}] not found`
        );
      }
      result = response[0] as Dataset;
    } else {
      result = response as Dataset;
    }
    return result;
  }

  public async *listDatasets({
    limit = 100,
    offset = 0,
  }: {
    limit?: number;
    offset?: number;
  } = {}): AsyncIterable<Dataset> {
    const path = "/datasets";
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    for await (const datasets of this._getPaginated<Dataset>(path, params)) {
      yield* datasets;
    }
  }

  public async deleteDataset({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  }): Promise<void> {
    let path = "/datasets";
    let datasetId_ = datasetId;
    if (datasetId !== undefined && datasetName !== undefined) {
      throw new Error("Must provide either datasetName or datasetId, not both");
    } else if (datasetName !== undefined) {
      const dataset = await this.readDataset({ datasetName });
      datasetId_ = dataset.id;
    }
    if (datasetId_ !== undefined) {
      path += `/${datasetId_}`;
    } else {
      throw new Error("Must provide datasetName or datasetId");
    }
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to delete ${path}: ${response.status} ${response.statusText}`
      );
    }
    await response.json();
  }

  public async createExample(
    inputs: KVMap,
    outputs: KVMap,
    {
      datasetId,
      datasetName,
      createdAt,
    }: {
      datasetId?: string;
      datasetName?: string;
      createdAt?: Date;
    }
  ): Promise<Example> {
    let datasetId_ = datasetId;
    if (datasetId_ === undefined && datasetName === undefined) {
      throw new Error("Must provide either datasetName or datasetId");
    } else if (datasetId_ !== undefined && datasetName !== undefined) {
      throw new Error("Must provide either datasetName or datasetId, not both");
    } else if (datasetId_ === undefined) {
      const dataset = await this.readDataset({ datasetName });
      datasetId_ = dataset.id;
    }

    const createdAt_ = createdAt || new Date();
    const data: ExampleCreate = {
      dataset_id: datasetId_,
      inputs,
      outputs,
      created_at: createdAt_.toISOString(),
    };

    const response = await this.caller.call(fetch, `${this.apiUrl}/examples`, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(data),
      signal: AbortSignal.timeout(this.timeout_ms),
    });

    if (!response.ok) {
      throw new Error(
        `Failed to create example: ${response.status} ${response.statusText}`
      );
    }

    const result = await response.json();
    return result as Example;
  }

  public async readExample(exampleId: string): Promise<Example> {
    const path = `/examples/${exampleId}`;
    return await this._get<Example>(path);
  }

  public async *listExamples({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  } = {}): AsyncIterable<Example> {
    let datasetId_;
    if (datasetId !== undefined && datasetName !== undefined) {
      throw new Error("Must provide either datasetName or datasetId, not both");
    } else if (datasetId !== undefined) {
      datasetId_ = datasetId;
    } else if (datasetName !== undefined) {
      const dataset = await this.readDataset({ datasetName });
      datasetId_ = dataset.id;
    } else {
      throw new Error("Must provide a datasetName or datasetId");
    }
    const params = new URLSearchParams({ dataset: datasetId_ });
    for await (const examples of this._getPaginated<Example>(
      "/examples",
      params
    )) {
      yield* examples;
    }
  }

  public async deleteExample(exampleId: string): Promise<void> {
    const path = `/examples/${exampleId}`;
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to delete ${path}: ${response.status} ${response.statusText}`
      );
    }
    await response.json();
  }

  public async updateExample(
    exampleId: string,
    update: ExampleUpdate
  ): Promise<object> {
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/examples/${exampleId}`,
      {
        method: "PATCH",
        headers: { ...this.headers, "Content-Type": "application/json" },
        body: JSON.stringify(update),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    if (!response.ok) {
      throw new Error(
        `Failed to update example ${exampleId}: ${response.status} ${response.statusText}`
      );
    }
    const result = await response.json();
    return result;
  }

  public async evaluateRun(
    run: Run | string,
    evaluator: RunEvaluator,
    {
      sourceInfo,
      loadChildRuns,
    }: { sourceInfo?: KVMap; loadChildRuns: boolean } = { loadChildRuns: false }
  ): Promise<Feedback> {
    let run_: Run;
    if (typeof run === "string") {
      run_ = await this.readRun(run, { loadChildRuns });
    } else if (typeof run === "object" && "id" in run) {
      run_ = run as Run;
    } else {
      throw new Error(`Invalid run type: ${typeof run}`);
    }
    let referenceExample: Example | undefined = undefined;
    if (
      run_.reference_example_id !== null &&
      run_.reference_example_id !== undefined
    ) {
      referenceExample = await this.readExample(run_.reference_example_id);
    }
    const feedbackResult = await evaluator.evaluateRun(run_, referenceExample);
    let sourceInfo_ = sourceInfo ?? {};
    if (feedbackResult.evaluatorInfo) {
      sourceInfo_ = { ...sourceInfo_, ...feedbackResult.evaluatorInfo };
    }
    return await this.createFeedback(run_.id, feedbackResult.key, {
      score: feedbackResult.score,
      value: feedbackResult.value,
      comment: feedbackResult.comment,
      correction: feedbackResult.correction,
      sourceInfo: sourceInfo_,
      feedbackSourceType: "MODEL",
    });
  }

  public async createFeedback(
    runId: string,
    key: string,
    {
      score,
      value,
      correction,
      comment,
      sourceInfo,
      feedbackSourceType = "API",
    }: {
      score?: ScoreType;
      value?: ValueType;
      correction?: string | object;
      comment?: string;
      sourceInfo?: object;
      feedbackSourceType?: "API" | "MODEL";
    }
  ): Promise<Feedback> {
    let feedback_source: feedback_source;
    if (feedbackSourceType === "API") {
      feedback_source = { type: "api", metadata: sourceInfo ?? {} };
    } else if (feedbackSourceType === "MODEL") {
      feedback_source = { type: "model", metadata: sourceInfo ?? {} };
    } else {
      throw new Error(`Unknown feedback source type ${feedbackSourceType}`);
    }
    const feedback: FeedbackCreate = {
      id: uuid.v4(),
      run_id: runId,
      key,
      score,
      value,
      correction,
      comment,
      feedback_source: feedback_source,
    };
    const response = await this.caller.call(fetch, `${this.apiUrl}/feedback`, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(feedback),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to create feedback for run ${runId}: ${response.status} ${response.statusText}`
      );
    }
    const result = await response.json();
    return result as Feedback;
  }

  public async readFeedback(feedbackId: string): Promise<Feedback> {
    const path = `/feedback/${feedbackId}`;
    const response = await this._get<Feedback>(path);
    return response;
  }

  public async deleteFeedback(feedbackId: string): Promise<void> {
    const path = `/feedback/${feedbackId}`;
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to delete ${path}: ${response.status} ${response.statusText}`
      );
    }
    await response.json();
  }

  public async *listFeedback({
    runIds,
  }: {
    runIds?: string[];
  } = {}): AsyncIterable<Feedback> {
    const queryParams = new URLSearchParams();
    if (runIds) {
      queryParams.append("run", runIds.join(","));
    }
    for await (const feedbacks of this._getPaginated<Feedback>(
      "/feedback",
      queryParams
    )) {
      yield* feedbacks;
    }
  }
}
