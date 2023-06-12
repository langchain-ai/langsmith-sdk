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
  ValueType,
} from "./schemas.js";
import { getEnvironmentVariable, getRuntimeEnvironment } from "./utils/env.js";
import { RunEvaluator } from "./evaluation/evaluator.js";

interface LangChainPlusClientConfig {
  apiUrl?: string;
  apiKey?: string;
  callerOptions?: AsyncCallerParams;
  timeout_ms?: number;
}

interface ListRunsParams {
  sessionId?: string;
  sessionName?: string;
  executionOrder?: number;
  runType?: RunType;
  error?: boolean;
}
interface UploadCSVParams {
  csvFile: Blob;
  fileName: string;
  inputKeys: string[];
  outputKeys: string[];
  description?: string;
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
  session_name?: string;
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

export class LangChainPlusClient {
  private apiKey?: string;

  private apiUrl: string;

  private caller: AsyncCaller;

  private timeout_ms: number;

  constructor(config: LangChainPlusClientConfig = {}) {
    const defaultConfig = LangChainPlusClient.getDefaultClientConfig();

    this.apiUrl = config.apiUrl ?? defaultConfig.apiUrl;
    this.apiKey = config.apiKey ?? defaultConfig.apiKey;
    this.validateApiKeyIfHosted();
    this.timeout_ms = config.timeout_ms ?? 3000;
    this.caller = new AsyncCaller(config.callerOptions ?? {});
  }

  public static getDefaultClientConfig(): { apiUrl: string; apiKey?: string } {
    return {
      apiUrl:
        getEnvironmentVariable("LANGCHAIN_ENDPOINT") ?? "http://localhost:1984",
      apiKey: getEnvironmentVariable("LANGCHAIN_API_KEY"),
    };
  }

  private validateApiKeyIfHosted(): void {
    const isLocal = isLocalhost(this.apiUrl);
    if (!isLocal && !this.apiKey) {
      throw new Error(
        "API key must be provided when using hosted LangChain+ API"
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

  public async createRun(run: CreateRunParams): Promise<void> {
    const headers = { ...this.headers, "Content-Type": "application/json" };
    const extra = run.extra ?? {};
    const runtimeEnv = await getRuntimeEnvironment();
    const runCreate: RunCreate = {
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

  public async readRun(runId: string): Promise<Run> {
    return await this._get<Run>(`/runs/${runId}`);
  }

  public async listRuns({
    sessionId,
    sessionName,
    executionOrder,
    runType,
    error,
  }: ListRunsParams): Promise<Run[]> {
    const queryParams = new URLSearchParams();
    let sessionId_ = sessionId;
    if (sessionName) {
      if (sessionId) {
        throw new Error("Only one of sessionId or sessionName may be given");
      }
      sessionId_ = (await this.readSession({ sessionName })).id;
    }
    if (sessionId_) {
      queryParams.append("session", sessionId_);
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

    return this._get<Run[]>("/runs", queryParams);
  }

  public async createSession({
    sessionName,
    sessionExtra,
  }: {
    sessionName: string;
    sessionExtra?: object;
  }): Promise<TracerSession> {
    const endpoint = `${this.apiUrl}/sessions?upsert=true`;
    const body = {
      name: sessionName,
      extra: sessionExtra,
    };
    const response = await this.caller.call(fetch, endpoint, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeout_ms),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(
        `Failed to create session ${sessionName}: ${response.status} ${response.statusText}`
      );
    }
    return result as TracerSession;
  }

  public async readSession({
    sessionId,
    sessionName,
  }: {
    sessionId?: string;
    sessionName?: string;
  }): Promise<TracerSession> {
    let path = "/sessions";
    const params = new URLSearchParams();
    if (sessionId !== undefined && sessionName !== undefined) {
      throw new Error("Must provide either sessionName or sessionId, not both");
    } else if (sessionId !== undefined) {
      path += `/${sessionId}`;
    } else if (sessionName !== undefined) {
      params.append("name", sessionName);
    } else {
      throw new Error("Must provide sessionName or sessionId");
    }

    const response = await this._get<TracerSession | TracerSession[]>(
      path,
      params
    );
    let result: TracerSession;
    if (Array.isArray(response)) {
      if (response.length === 0) {
        throw new Error(
          `Session[id=${sessionId}, name=${sessionName}] not found`
        );
      }
      result = response[0] as TracerSession;
    } else {
      result = response as TracerSession;
    }
    return result;
  }

  public async listSessions(): Promise<TracerSession[]> {
    return this._get<TracerSession[]>("/sessions");
  }

  public async deleteSession({
    sessionId,
    sessionName,
  }: {
    sessionId?: string;
    sessionName?: string;
  }): Promise<void> {
    let sessionId_: string | undefined;
    if (sessionId === undefined && sessionName === undefined) {
      throw new Error("Must provide sessionName or sessionId");
    } else if (sessionId !== undefined && sessionName !== undefined) {
      throw new Error("Must provide either sessionName or sessionId, not both");
    } else if (sessionId === undefined) {
      sessionId_ = (await this.readSession({ sessionName })).id;
    } else {
      sessionId_ = sessionId;
    }
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/sessions/${sessionId_}`,
      {
        method: "DELETE",
        headers: this.headers,
        signal: AbortSignal.timeout(this.timeout_ms),
      }
    );
    await raiseForStatus(
      response,
      `delete session ${sessionId_} (${sessionName})`
    );
  }

  public async uploadCsv({
    csvFile,
    fileName,
    inputKeys,
    outputKeys,
    description,
  }: UploadCSVParams): Promise<Dataset> {
    const url = `${this.apiUrl}/datasets/upload`;
    const formData = new FormData();
    formData.append("file", csvFile, fileName);
    formData.append("input_keys", inputKeys.join(","));
    formData.append("output_keys", outputKeys.join(","));
    if (description) {
      formData.append("description", description);
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
    { description }: { description?: string } = {}
  ): Promise<Dataset> {
    const response = await this.caller.call(fetch, `${this.apiUrl}/datasets`, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        description,
      }),
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

  public async listDatasets({
    limit = 100,
  }: {
    limit?: number;
  } = {}): Promise<Dataset[]> {
    const path = "/datasets";
    const params = new URLSearchParams({ limit: limit.toString() });
    const response = await this._get<Dataset[]>(path, params);
    if (!Array.isArray(response)) {
      throw new Error(
        `Expected ${path} to return an array, but got ${response}`
      );
    }
    return response as Dataset[];
  }

  public async deleteDataset({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  }): Promise<Dataset> {
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
    const results = await response.json();
    return results as Dataset;
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

  public async listExamples({
    datasetId,
    datasetName,
  }: {
    datasetId?: string;
    datasetName?: string;
  } = {}): Promise<Example[]> {
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
    const response = await this._get<Example[]>(
      "/examples",
      new URLSearchParams({ dataset: datasetId_ })
    );
    if (!Array.isArray(response)) {
      throw new Error(
        `Expected /examples to return an array, but got ${response}`
      );
    }
    return response as Example[];
  }

  public async deleteExample(exampleId: string): Promise<Example> {
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
    const result = await response.json();
    return result as Example;
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
    { sourceInfo }: { sourceInfo?: KVMap } = {}
  ): Promise<Feedback> {
    let run_: Run;
    if (typeof run === "string") {
      run_ = await this.readRun(run);
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

  public async deleteFeedback(feedbackId: string): Promise<Feedback> {
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
    const result = await response.json();
    return result as Feedback;
  }

  public async listFeedback({
    runIds,
  }: {
    runIds?: string[];
  } = {}): Promise<Feedback[]> {
    const queryParams = new URLSearchParams();
    if (runIds) {
      queryParams.append("run", runIds.join(","));
    }
    const response = await this._get<Feedback[]>("/feedback", queryParams);
    return response;
  }
}
