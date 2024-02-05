import * as uuid from "uuid";

import { AsyncCaller, AsyncCallerParams } from "./utils/async_caller.js";
import {
  DataType,
  Dataset,
  DatasetShareSchema,
  Example,
  ExampleCreate,
  ExampleUpdate,
  Feedback,
  KVMap,
  LangChainBaseMessage,
  Run,
  RunCreate,
  RunUpdate,
  ScoreType,
  TracerSession,
  TracerSessionResult,
  ValueType,
} from "./schemas.js";
import {
  convertLangChainMessageToExample,
  isLangChainMessage,
} from "./utils/messages.js";
import {
  getEnvironmentVariable,
  getLangChainEnvVarsMetadata,
  getRuntimeEnvironment,
} from "./utils/env.js";

import { RunEvaluator } from "./evaluation/evaluator.js";
import { __version__ } from "./index.js";

interface ClientConfig {
  apiUrl?: string;
  apiKey?: string;
  callerOptions?: AsyncCallerParams;
  timeout_ms?: number;
  webUrl?: string;
  hideInputs?: boolean;
  hideOutputs?: boolean;
}

interface ListRunsParams {
  projectId?: string;
  projectName?: string;
  executionOrder?: number;
  parentRunId?: string;
  referenceExampleId?: string;
  startTime?: Date;
  runType?: string;
  error?: boolean;
  id?: string[];
  limit?: number;
  query?: string;
  filter?: string;
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
  correction?: object | null;
  comment?: string | null;
  feedback_source?: feedback_source | KVMap | null;
}

interface FeedbackUpdate {
  score?: ScoreType;
  value?: ValueType;
  correction?: object | null;
  comment?: string | null;
}

interface CreateRunParams {
  name: string;
  inputs: KVMap;
  run_type: string;
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
  revision_id?: string;
}

interface projectOptions {
  projectName?: string;
  projectId?: string;
}

export type FeedbackSourceType = "model" | "api" | "app";

export type CreateExampleOptions = {
  datasetId?: string;
  datasetName?: string;
  createdAt?: Date;
  exampleId?: string;
};

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

function assertUuid(str: string): void {
  if (!uuid.validate(str)) {
    throw new Error(`Invalid UUID: ${str}`);
  }
}

export class Client {
  private apiKey?: string;

  private apiUrl: string;

  private webUrl?: string;

  private caller: AsyncCaller;

  private timeout_ms: number;

  private _tenantId: string | null = null;

  private hideInputs?: boolean;

  private hideOutputs?: boolean;

  constructor(config: ClientConfig = {}) {
    const defaultConfig = Client.getDefaultClientConfig();

    this.apiUrl = trimQuotes(config.apiUrl ?? defaultConfig.apiUrl) ?? "";
    this.apiKey = trimQuotes(config.apiKey ?? defaultConfig.apiKey);
    this.webUrl = trimQuotes(config.webUrl ?? defaultConfig.webUrl);
    this.validateApiKeyIfHosted();
    this.timeout_ms = config.timeout_ms ?? 12_000;
    this.caller = new AsyncCaller(config.callerOptions ?? {});
    this.hideInputs = config.hideInputs ?? defaultConfig.hideInputs;
    this.hideOutputs = config.hideOutputs ?? defaultConfig.hideOutputs;
  }

  public static getDefaultClientConfig(): {
    apiUrl: string;
    apiKey?: string;
    webUrl?: string;
    hideInputs?: boolean;
    hideOutputs?: boolean;
  } {
    const apiKey = getEnvironmentVariable("LANGCHAIN_API_KEY");
    const apiUrl =
      getEnvironmentVariable("LANGCHAIN_ENDPOINT") ??
      "https://api.smith.langchain.com";
    const hideInputs =
      getEnvironmentVariable("LANGCHAIN_HIDE_INPUTS") === "true";
    const hideOutputs =
      getEnvironmentVariable("LANGCHAIN_HIDE_OUTPUTS") === "true";
    return {
      apiUrl: apiUrl,
      apiKey: apiKey,
      webUrl: undefined,
      hideInputs: hideInputs,
      hideOutputs: hideOutputs,
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

  private getHostUrl(): string {
    if (this.webUrl) {
      return this.webUrl;
    } else if (isLocalhost(this.apiUrl)) {
      this.webUrl = "http://localhost";
      return "http://localhost";
    } else if (
      this.apiUrl.includes("/api") &&
      !this.apiUrl.split(".", 1)[0].endsWith("api")
    ) {
      this.webUrl = this.apiUrl.replace("/api", "");
      return this.webUrl;
    } else if (this.apiUrl.split(".", 1)[0].includes("dev")) {
      this.webUrl = "https://dev.smith.langchain.com";
      return "https://dev.smith.langchain.com";
    } else {
      this.webUrl = "https://smith.langchain.com";
      return "https://smith.langchain.com";
    }
  }

  private get headers(): { [header: string]: string } {
    const headers: { [header: string]: string } = {
      "User-Agent": `langsmith-js/${__version__}`,
    };
    if (this.apiKey) {
      headers["x-api-key"] = `${this.apiKey}`;
    }
    return headers;
  }

  private processInputs(inputs: KVMap): KVMap {
    if (this.hideInputs) {
      return {};
    }
    return inputs;
  }

  private processOutputs(outputs: KVMap): KVMap {
    if (this.hideOutputs) {
      return {};
    }
    return outputs;
  }

  private async _getResponse(
    path: string,
    queryParams?: URLSearchParams
  ): Promise<Response> {
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
    return response;
  }

  private async _get<T>(
    path: string,
    queryParams?: URLSearchParams
  ): Promise<T> {
    const response = await this._getResponse(path, queryParams);
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
  private async *_getCursorPaginatedList<T>(
    path: string,
    body: Record<string, any> | null = null,
    requestMethod = "POST",
    dataKey = "runs"
  ): AsyncIterable<T[]> {
    const bodyParams = body ? { ...body } : {};
    while (true) {
      const response = await this.caller.call(fetch, `${this.apiUrl}${path}`, {
        method: requestMethod,
        headers: { ...this.headers, "Content-Type": "application/json" },
        signal: AbortSignal.timeout(this.timeout_ms),
        body: JSON.stringify(bodyParams),
      });
      const responseBody = await response.json();
      if (!responseBody) {
        break;
      }
      if (!responseBody[dataKey]) {
        break;
      }
      yield responseBody[dataKey];
      const cursors = responseBody.cursors;
      if (!cursors) {
        break;
      }
      if (!cursors.next) {
        break;
      }
      bodyParams.cursor = cursors.next;
    }
  }

  public async createRun(run: CreateRunParams): Promise<void> {
    const headers = { ...this.headers, "Content-Type": "application/json" };
    const extra = run.extra ?? {};
    const metadata = extra.metadata;
    const runtimeEnv = await getRuntimeEnvironment();
    const envVars = getLangChainEnvVarsMetadata();
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
        metadata: {
          ...envVars,
          ...(envVars.revision_id || run.revision_id
            ? { revision_id: run.revision_id ?? envVars.revision_id }
            : {}),
          ...metadata,
        },
      },
    };
    runCreate.inputs = this.processInputs(runCreate.inputs);
    if (runCreate.outputs) {
      runCreate.outputs = this.processOutputs(runCreate.outputs);
    }
    runCreate.start_time = run.start_time ?? Date.now();

    const response = await this.caller.call(fetch, `${this.apiUrl}/runs`, {
      method: "POST",
      headers,
      body: JSON.stringify(runCreate),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    await raiseForStatus(response, "create run");
  }

  public async updateRun(runId: string, run: RunUpdate): Promise<void> {
    assertUuid(runId);
    if (run.inputs) {
      run.inputs = this.processInputs(run.inputs);
    }

    if (run.outputs) {
      run.outputs = this.processOutputs(run.outputs);
    }
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
    assertUuid(runId);
    let run = await this._get<Run>(`/runs/${runId}`);
    if (loadChildRuns && run.child_run_ids) {
      run = await this._loadChildRuns(run);
    }
    return run;
  }

  public async getRunUrl({
    runId,
    run,
    projectOpts,
  }: {
    runId?: string;
    run?: Run;
    projectOpts?: projectOptions;
  }): Promise<string> {
    if (run !== undefined) {
      let sessionId: string;
      if (run.session_id) {
        sessionId = run.session_id;
      } else if (projectOpts?.projectName) {
        sessionId = (
          await this.readProject({ projectName: projectOpts?.projectName })
        ).id;
      } else if (projectOpts?.projectId) {
        sessionId = projectOpts?.projectId;
      } else {
        const project = await this.readProject({
          projectName: getEnvironmentVariable("LANGCHAIN_PROJECT") || "default",
        });
        sessionId = project.id;
      }
      const tenantId = await this._getTenantId();
      return `${this.getHostUrl()}/o/${tenantId}/projects/p/${sessionId}/r/${
        run.id
      }?poll=true`;
    } else if (runId !== undefined) {
      const run_ = await this.readRun(runId);
      if (!run_.app_path) {
        throw new Error(`Run ${runId} has no app_path`);
      }
      const baseUrl = this.getHostUrl();
      return `${baseUrl}${run_.app_path}`;
    } else {
      throw new Error("Must provide either runId or run");
    }
  }

  private async _loadChildRuns(run: Run): Promise<Run> {
    const childRuns = await toArray(this.listRuns({ id: run.child_run_ids }));
    const treemap: { [key: string]: Run[] } = {};
    const runs: { [key: string]: Run } = {};
    // TODO: make dotted order required when the migration finishes
    childRuns.sort((a, b) =>
      (a?.dotted_order ?? "").localeCompare(b?.dotted_order ?? "")
    );
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
    startTime,
    executionOrder,
    runType,
    error,
    id,
    query,
    filter,
    limit,
  }: ListRunsParams): AsyncIterable<Run> {
    let projectId_ = projectId;
    if (projectName) {
      if (projectId) {
        throw new Error("Only one of projectId or projectName may be given");
      }
      projectId_ = (await this.readProject({ projectName })).id;
    }
    const body = {
      session: projectId_ ? [projectId_] : null,
      run_type: runType,
      reference_example: referenceExampleId,
      query,
      filter,
      execution_order: executionOrder,
      parent_run: parentRunId ? [parentRunId] : null,
      start_time: startTime ? startTime.toISOString() : null,
      error,
      id,
      limit,
    };

    for await (const runs of this._getCursorPaginatedList<Run>(
      "/runs/query",
      body
    )) {
      yield* runs;
    }
  }

  public async shareRun(
    runId: string,
    { shareId }: { shareId?: string } = {}
  ): Promise<string> {
    const data = {
      run_id: runId,
      share_token: shareId || uuid.v4(),
    };
    assertUuid(runId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/runs/${runId}/share`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const result = await response.json();
    if (result === null || !("share_token" in result)) {
      throw new Error("Invalid response from server");
    }
    return `${this.getHostUrl()}/public/${result["share_token"]}/r`;
  }

  public async unshareRun(runId: string): Promise<void> {
    assertUuid(runId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/runs/${runId}/share`,
      {
        method: "DELETE",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(response, "unshare run");
  }

  public async readRunSharedLink(runId: string): Promise<string | undefined> {
    assertUuid(runId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/runs/${runId}/share`,
      {
        method: "GET",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const result = await response.json();
    if (result === null || !("share_token" in result)) {
      return undefined;
    }
    return `${this.getHostUrl()}/public/${result["share_token"]}/r`;
  }

  public async listSharedRuns(
    shareToken: string,
    {
      runIds,
    }: {
      runIds?: string[];
    } = {}
  ): Promise<Run[]> {
    const queryParams = new URLSearchParams({
      share_token: shareToken,
    });
    if (runIds !== undefined) {
      for (const runId of runIds) {
        queryParams.append("id", runId);
      }
    }
    assertUuid(shareToken);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/public/${shareToken}/runs${queryParams}`,
      {
        method: "GET",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const runs = await response.json();
    return runs as Run[];
  }

  public async readDatasetSharedSchema(
    datasetId?: string,
    datasetName?: string
  ): Promise<DatasetShareSchema> {
    if (!datasetId && !datasetName) {
      throw new Error("Either datasetId or datasetName must be given");
    }
    if (!datasetId) {
      const dataset = await this.readDataset({ datasetName });
      datasetId = dataset.id;
    }
    assertUuid(datasetId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/datasets/${datasetId}/share`,
      {
        method: "GET",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const shareSchema = await response.json();
    shareSchema.url = `${this.getHostUrl()}/public/${
      shareSchema.share_token
    }/d`;
    return shareSchema as DatasetShareSchema;
  }

  public async shareDataset(
    datasetId?: string,
    datasetName?: string
  ): Promise<DatasetShareSchema> {
    if (!datasetId && !datasetName) {
      throw new Error("Either datasetId or datasetName must be given");
    }
    if (!datasetId) {
      const dataset = await this.readDataset({ datasetName });
      datasetId = dataset.id;
    }
    const data = {
      dataset_id: datasetId,
    };
    assertUuid(datasetId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/datasets/${datasetId}/share`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const shareSchema = await response.json();
    shareSchema.url = `${this.getHostUrl()}/public/${
      shareSchema.share_token
    }/d`;
    return shareSchema as DatasetShareSchema;
  }

  public async unshareDataset(datasetId: string): Promise<void> {
    assertUuid(datasetId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/datasets/${datasetId}/share`,
      {
        method: "DELETE",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(response, "unshare dataset");
  }

  public async readSharedDataset(shareToken: string): Promise<Dataset> {
    assertUuid(shareToken);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/public/${shareToken}/datasets`,
      {
        method: "GET",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    const dataset = await response.json();
    return dataset as Dataset;
  }

  public async createProject({
    projectName,
    description = null,
    metadata = null,
    upsert = false,
    projectExtra = null,
    referenceDatasetId = null,
  }: {
    projectName: string;
    description?: string | null;
    metadata?: Record<string, any> | null;
    upsert?: boolean;
    projectExtra?: Record<string, any> | null;
    referenceDatasetId?: string | null;
  }): Promise<TracerSession> {
    const upsert_ = upsert ? `?upsert=true` : "";
    const endpoint = `${this.apiUrl}/sessions${upsert_}`;
    const extra: Record<string, any> = projectExtra || {};
    if (metadata) {
      extra["metadata"] = metadata;
    }
    const body: Record<string, any> = {
      name: projectName,
      extra,
      description,
    };
    if (referenceDatasetId !== null) {
      body["reference_dataset_id"] = referenceDatasetId;
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

  public async updateProject(
    projectId: string,
    {
      name = null,
      description = null,
      metadata = null,
      projectExtra = null,
      endTime = null,
    }: {
      name?: string | null;
      description?: string | null;
      metadata?: Record<string, any> | null;
      projectExtra?: Record<string, any> | null;
      endTime?: string | null;
    }
  ): Promise<TracerSession> {
    const endpoint = `${this.apiUrl}/sessions/${projectId}`;
    let extra = projectExtra;
    if (metadata) {
      extra = { ...(extra || {}), metadata };
    }
    const body: Record<string, any> = {
      name,
      extra,
      description,
      end_time: endTime ? new Date(endTime).toISOString() : null,
    };
    const response = await this.caller.call(fetch, endpoint, {
      method: "PATCH",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(
        `Failed to update project ${projectId}: ${response.status} ${response.statusText}`
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
      assertUuid(projectId);
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

  private async _getTenantId(): Promise<string> {
    if (this._tenantId !== null) {
      return this._tenantId;
    }
    const queryParams = new URLSearchParams({ limit: "1" });
    for await (const projects of this._getPaginated<TracerSession>(
      "/sessions",
      queryParams
    )) {
      this._tenantId = projects[0].tenant_id;
      return projects[0].tenant_id;
    }
    throw new Error("No projects found to resolve tenant.");
  }

  public async *listProjects({
    projectIds,
    name,
    nameContains,
    referenceDatasetId,
    referenceDatasetName,
    referenceFree,
  }: {
    projectIds?: string[];
    name?: string;
    nameContains?: string;
    referenceDatasetId?: string;
    referenceDatasetName?: string;
    referenceFree?: boolean;
  } = {}): AsyncIterable<TracerSession> {
    const params = new URLSearchParams();
    if (projectIds !== undefined) {
      for (const projectId of projectIds) {
        params.append("id", projectId);
      }
    }
    if (name !== undefined) {
      params.append("name", name);
    }
    if (nameContains !== undefined) {
      params.append("name_contains", nameContains);
    }
    if (referenceDatasetId !== undefined) {
      params.append("reference_dataset", referenceDatasetId);
    } else if (referenceDatasetName !== undefined) {
      const dataset = await this.readDataset({
        datasetName: referenceDatasetName,
      });
      params.append("reference_dataset", dataset.id);
    }
    if (referenceFree !== undefined) {
      params.append("reference_free", referenceFree.toString());
    }
    for await (const projects of this._getPaginated<TracerSession>(
      "/sessions",
      params
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
    assertUuid(projectId_);
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
      assertUuid(datasetId);
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

  public async readDatasetOpenaiFinetuning({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  }): Promise<any[]> {
    const path = "/datasets";
    if (datasetId !== undefined) {
      // do nothing
    } else if (datasetName !== undefined) {
      datasetId = (await this.readDataset({ datasetName })).id;
    } else {
      throw new Error("Must provide datasetName or datasetId");
    }
    const response = await this._getResponse(`${path}/${datasetId}/openai_ft`);
    const datasetText = await response.text();
    const dataset = datasetText
      .trim()
      .split("\n")
      .map((line: string) => JSON.parse(line));
    return dataset;
  }

  public async *listDatasets({
    limit = 100,
    offset = 0,
    datasetIds,
    datasetName,
    datasetNameContains,
  }: {
    limit?: number;
    offset?: number;
    datasetIds?: string[];
    datasetName?: string;
    datasetNameContains?: string;
  } = {}): AsyncIterable<Dataset> {
    const path = "/datasets";
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (datasetIds !== undefined) {
      for (const id_ of datasetIds) {
        params.append("id", id_);
      }
    }
    if (datasetName !== undefined) {
      params.append("name", datasetName);
    }
    if (datasetNameContains !== undefined) {
      params.append("name_contains", datasetNameContains);
    }
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
      assertUuid(datasetId_);
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
    { datasetId, datasetName, createdAt, exampleId }: CreateExampleOptions
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
      created_at: createdAt_?.toISOString(),
      id: exampleId,
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

  public async createExamples(props: {
    inputs: Array<KVMap>;
    outputs?: Array<KVMap>;
    sourceRunIds?: Array<string>;
    exampleIds?: Array<string>;
    datasetId?: string;
    datasetName?: string;
  }): Promise<Example[]> {
    const {
      inputs,
      outputs,
      sourceRunIds,
      exampleIds,
      datasetId,
      datasetName,
    } = props;
    let datasetId_ = datasetId;
    if (datasetId_ === undefined && datasetName === undefined) {
      throw new Error("Must provide either datasetName or datasetId");
    } else if (datasetId_ !== undefined && datasetName !== undefined) {
      throw new Error("Must provide either datasetName or datasetId, not both");
    } else if (datasetId_ === undefined) {
      const dataset = await this.readDataset({ datasetName });
      datasetId_ = dataset.id;
    }

    const formattedExamples = inputs.map((input, idx) => {
      return {
        dataset_id: datasetId_,
        inputs: input,
        outputs: outputs ? outputs[idx] : undefined,
        id: exampleIds ? exampleIds[idx] : undefined,
        source_run_id: sourceRunIds ? sourceRunIds[idx] : undefined,
      };
    });

    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/examples/bulk`,
      {
        method: "POST",
        headers: { ...this.headers, "Content-Type": "application/json" },
        body: JSON.stringify(formattedExamples),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );

    if (!response.ok) {
      throw new Error(
        `Failed to create examples: ${response.status} ${response.statusText}`
      );
    }

    const result = await response.json();
    return result as Example[];
  }

  public async createLLMExample(
    input: string,
    generation: string | undefined,
    options: CreateExampleOptions
  ) {
    return this.createExample({ input }, { output: generation }, options);
  }

  public async createChatExample(
    input: KVMap[] | LangChainBaseMessage[],
    generations: KVMap | LangChainBaseMessage | undefined,
    options: CreateExampleOptions
  ) {
    const finalInput = input.map((message) => {
      if (isLangChainMessage(message)) {
        return convertLangChainMessageToExample(message);
      }
      return message;
    });
    const finalOutput = isLangChainMessage(generations)
      ? convertLangChainMessageToExample(generations)
      : generations;
    return this.createExample(
      { input: finalInput },
      { output: finalOutput },
      options
    );
  }

  public async readExample(exampleId: string): Promise<Example> {
    assertUuid(exampleId);
    const path = `/examples/${exampleId}`;
    return await this._get<Example>(path);
  }

  public async *listExamples({
    datasetId,
    datasetName,
    exampleIds,
  }: {
    datasetId?: string;
    datasetName?: string;
    exampleIds?: string[];
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
    if (exampleIds !== undefined) {
      for (const id_ of exampleIds) {
        params.append("id", id_);
      }
    }
    for await (const examples of this._getPaginated<Example>(
      "/examples",
      params
    )) {
      yield* examples;
    }
  }

  public async deleteExample(exampleId: string): Promise<void> {
    assertUuid(exampleId);
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
    assertUuid(exampleId);
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
      referenceExample,
    }: {
      sourceInfo?: KVMap;
      loadChildRuns: boolean;
      referenceExample?: Example;
    } = { loadChildRuns: false }
  ): Promise<Feedback> {
    let run_: Run;
    if (typeof run === "string") {
      run_ = await this.readRun(run, { loadChildRuns });
    } else if (typeof run === "object" && "id" in run) {
      run_ = run as Run;
    } else {
      throw new Error(`Invalid run type: ${typeof run}`);
    }
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
    const runId = feedbackResult.targetRunId ?? run_.id;
    return await this.createFeedback(runId, feedbackResult.key, {
      score: feedbackResult?.score,
      value: feedbackResult?.value,
      comment: feedbackResult?.comment,
      correction: feedbackResult?.correction,
      sourceInfo: sourceInfo_,
      feedbackSourceType: "model",
      sourceRunId: feedbackResult?.sourceRunId,
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
      feedbackSourceType = "api",
      sourceRunId,
      feedbackId,
      eager = false,
    }: {
      score?: ScoreType;
      value?: ValueType;
      correction?: object;
      comment?: string;
      sourceInfo?: object;
      feedbackSourceType?: FeedbackSourceType;
      sourceRunId?: string;
      feedbackId?: string;
      eager?: boolean;
    }
  ): Promise<Feedback> {
    const feedback_source: feedback_source = {
      type: feedbackSourceType ?? "api",
      metadata: sourceInfo ?? {},
    };
    if (
      sourceRunId !== undefined &&
      feedback_source?.metadata !== undefined &&
      !feedback_source.metadata["__run"]
    ) {
      feedback_source.metadata["__run"] = { run_id: sourceRunId };
    }
    if (
      feedback_source?.metadata !== undefined &&
      feedback_source.metadata["__run"]?.run_id !== undefined
    ) {
      assertUuid(feedback_source.metadata["__run"].run_id);
    }
    const feedback: FeedbackCreate = {
      id: feedbackId ?? uuid.v4(),
      run_id: runId,
      key,
      score,
      value,
      correction,
      comment,
      feedback_source: feedback_source,
    };
    const url = `${this.apiUrl}/feedback` + (eager ? "/eager" : "");
    const response = await this.caller.call(fetch, url, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(feedback),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    await raiseForStatus(response, "create feedback");
    return feedback as Feedback;
  }

  public async updateFeedback(
    feedbackId: string,
    {
      score,
      value,
      correction,
      comment,
    }: {
      score?: number | boolean | null;
      value?: number | boolean | string | object | null;
      correction?: object | null;
      comment?: string | null;
    }
  ): Promise<void> {
    const feedbackUpdate: FeedbackUpdate = {};
    if (score !== undefined && score !== null) {
      feedbackUpdate["score"] = score;
    }
    if (value !== undefined && value !== null) {
      feedbackUpdate["value"] = value;
    }
    if (correction !== undefined && correction !== null) {
      feedbackUpdate["correction"] = correction;
    }
    if (comment !== undefined && comment !== null) {
      feedbackUpdate["comment"] = comment;
    }
    assertUuid(feedbackId);
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/feedback/${feedbackId}`,
      {
        method: "PATCH",
        headers: { ...this.headers, "Content-Type": "application/json" },
        body: JSON.stringify(feedbackUpdate),
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(response, "update feedback");
  }

  public async readFeedback(feedbackId: string): Promise<Feedback> {
    assertUuid(feedbackId);
    const path = `/feedback/${feedbackId}`;
    const response = await this._get<Feedback>(path);
    return response;
  }

  public async deleteFeedback(feedbackId: string): Promise<void> {
    assertUuid(feedbackId);
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
    feedbackKeys,
    feedbackSourceTypes,
  }: {
    runIds?: string[];
    feedbackKeys?: string[];
    feedbackSourceTypes?: FeedbackSourceType[];
  } = {}): AsyncIterable<Feedback> {
    const queryParams = new URLSearchParams();
    if (runIds) {
      queryParams.append("run", runIds.join(","));
    }
    if (feedbackKeys) {
      for (const key of feedbackKeys) {
        queryParams.append("key", key);
      }
    }
    if (feedbackSourceTypes) {
      for (const type of feedbackSourceTypes) {
        queryParams.append("source", type);
      }
    }
    for await (const feedbacks of this._getPaginated<Feedback>(
      "/feedback",
      queryParams
    )) {
      yield* feedbacks;
    }
  }
}
