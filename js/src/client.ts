import * as uuid from "uuid";
import { AsyncCaller, AsyncCallerParams } from "./utils/async_caller.js";
import {
  Dataset,
  Example,
  ExampleCreate,
  Feedback,
  KVMap,
  Run,
  RunType,
  TracerSession,
} from "./schemas.js";
import { getEnvironmentVariable } from "./utils/env.js";

interface LangChainPlusClientConfig {
  apiUrl: string;
  apiKey?: string;
  callerOptions?: AsyncCallerParams;
}

interface ListRunsParams {
  session_id?: string;
  session_name?: string;
  execution_order?: number;
  run_type?: RunType;
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
  score?: number | boolean | undefined;
  value?: number | boolean | string | object | null;
  correction?: string | object | null;
  comment?: string | null;
  feedback_source?: feedback_source | KVMap | null;
}

// utility functions
const isLocalhost = (url: string): boolean => {
  const strippedUrl = url.replace("http://", "").replace("https://", "");
  const hostname = strippedUrl.split("/")[0].split(":")[0];
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1"
  );
};

export class LangChainPlusClient {
  private apiKey?: string;

  private apiUrl: string;

  private caller: AsyncCaller;

  constructor(config: LangChainPlusClientConfig) {
    const defaultConfig = LangChainPlusClient.getDefaultClientConfig();

    this.apiUrl = config.apiUrl ?? defaultConfig.apiUrl;
    this.apiKey = config.apiKey ?? defaultConfig.apiKey;
    this.validateApiKeyIfHosted();
    this.caller = new AsyncCaller(config.callerOptions ?? {});
  }

  public static getDefaultClientConfig(): LangChainPlusClientConfig {
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
    });
    if (!response.ok) {
      throw new Error(
        `Failed to fetch ${path}: ${response.status} ${response.statusText}`
      );
    }
    return response.json() as T;
  }

  public async readRun(run_id: string): Promise<Run> {
    return await this._get<Run>(`/runs/${run_id}`);
  }

  public async listRuns({
    session_id,
    session_name,
    execution_order,
    run_type,
    error,
  }: ListRunsParams): Promise<Run[]> {
    const queryParams = new URLSearchParams();
    let sessionId_ = session_id;
    if (session_name) {
      if (session_id) {
        throw new Error("Only one of session_id or session_name may be given");
      }
      sessionId_ = (await this.readSession({ session_name })).id;
    }
    if (sessionId_) {
      queryParams.append("session", sessionId_);
    }
    if (execution_order) {
      queryParams.append("execution_order", execution_order.toString());
    }
    if (run_type) {
      queryParams.append("run_type", run_type);
    }
    if (error !== undefined) {
      queryParams.append("error", error.toString());
    }

    return this._get<Run[]>("/runs", queryParams);
  }

  public async createSession({
    session_name,
    session_extra,
  }: {
    session_name: string;
    session_extra?: object;
  }): Promise<TracerSession> {
    const endpoint = `${this.apiUrl}/sessions?upsert=true`;
    const body = {
      name: session_name,
      extra: session_extra,
    };
    const response = await this.caller.call(fetch, endpoint, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(
        `Failed to create session ${session_name}: ${response.status} ${response.statusText}`
      );
    }
    return result as TracerSession;
  }

  public async readSession({
    session_id,
    session_name,
  }: {
    session_id?: string;
    session_name?: string;
  }): Promise<TracerSession> {
    let path = "/sessions";
    const params = new URLSearchParams();
    if (session_id !== undefined && session_name !== undefined) {
      throw new Error(
        "Must provide either session_name or session_id, not both"
      );
    } else if (session_id !== undefined) {
      path += `/${session_id}`;
    } else if (session_name !== undefined) {
      params.append("name", session_name);
    } else {
      throw new Error("Must provide session_name or session_id");
    }

    const response = await this._get<TracerSession | TracerSession[]>(
      path,
      params
    );
    let result: TracerSession;
    if (Array.isArray(response)) {
      if (response.length === 0) {
        throw new Error(
          `Session[id=${session_id}, name=${session_name}] not found`
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
    session_id,
    session_name,
  }: {
    session_id?: string;
    session_name?: string;
  }): Promise<void> {
    let sessionId_: string | undefined;
    if (session_id === undefined && session_name === undefined) {
      throw new Error("Must provide session_name or session_id");
    } else if (session_id !== undefined && session_name !== undefined) {
      throw new Error(
        "Must provide either session_name or session_id, not both"
      );
    } else if (session_id === undefined) {
      sessionId_ = (await this.readSession({ session_name })).id;
    } else {
      sessionId_ = session_id;
    }
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/sessions/${sessionId_}`,
      {
        method: "DELETE",
        headers: this.headers,
      }
    );
    if (!response.ok) {
      throw new Error(
        `Failed to delete session ${sessionId_}: ${response.status} ${response.statusText}`
      );
    }
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
    { description }: { description?: string }
  ): Promise<Dataset> {
    const response = await this.caller.call(fetch, `${this.apiUrl}/datasets`, {
      method: "POST",
      headers: { ...this.headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        description,
      }),
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
    dataset_id,
    dataset_name,
  }: {
    dataset_id?: string;
    dataset_name?: string;
  }): Promise<Dataset> {
    let path = "/datasets";
    // limit to 1 result
    const params = new URLSearchParams({ limit: "1" });
    if (dataset_id !== undefined && dataset_name !== undefined) {
      throw new Error(
        "Must provide either dataset_name or dataset_id, not both"
      );
    } else if (dataset_id !== undefined) {
      path += `/${dataset_id}`;
    } else if (dataset_name !== undefined) {
      params.append("name", dataset_name);
    } else {
      throw new Error("Must provide dataset_name or dataset_id");
    }
    const response = await this._get<Dataset | Dataset[]>(path, params);
    let result: Dataset;
    if (Array.isArray(response)) {
      if (response.length === 0) {
        throw new Error(
          `Dataset[id=${dataset_id}, name=${dataset_name}] not found`
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
    dataset_id,
    dataset_name,
  }: {
    dataset_id?: string;
    dataset_name?: string;
  }): Promise<Dataset> {
    let path = "/datasets";
    let datasetId_ = dataset_id;
    if (dataset_id !== undefined && dataset_name !== undefined) {
      throw new Error(
        "Must provide either dataset_name or dataset_id, not both"
      );
    } else if (dataset_name !== undefined) {
      const dataset = await this.readDataset({ dataset_name });
      datasetId_ = dataset.id;
    }
    if (datasetId_ !== undefined) {
      path += `/${datasetId_}`;
    } else {
      throw new Error("Must provide dataset_name or dataset_id");
    }
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
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
      dataset_id,
      dataset_name,
      created_at,
    }: {
      dataset_id?: string;
      dataset_name?: string;
      created_at?: Date;
    }
  ): Promise<Example> {
    let datasetId_ = dataset_id;
    if (datasetId_ === undefined && dataset_name === undefined) {
      throw new Error("Must provide either dataset_name or dataset_id");
    } else if (datasetId_ !== undefined && dataset_name !== undefined) {
      throw new Error(
        "Must provide either dataset_name or dataset_id, not both"
      );
    } else if (datasetId_ === undefined) {
      const dataset = await this.readDataset({ dataset_name });
      datasetId_ = dataset.id;
    }

    const createdAt_ = created_at || new Date();
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
    });

    if (!response.ok) {
      throw new Error(
        `Failed to create example: ${response.status} ${response.statusText}`
      );
    }

    const result = await response.json();
    return result as Example;
  }

  public async readExample(example_id: string): Promise<Example> {
    const path = `/examples/${example_id}`;
    return await this._get<Example>(path);
  }

  public async listExamples({
    dataset_id,
    dataset_name,
  }: {
    dataset_id?: string;
    dataset_name?: string;
  } = {}): Promise<Example[]> {
    let datasetId_;
    if (dataset_id !== undefined && dataset_name !== undefined) {
      throw new Error(
        "Must provide either dataset_name or dataset_id, not both"
      );
    } else if (dataset_id !== undefined) {
      datasetId_ = dataset_id;
    } else if (dataset_name !== undefined) {
      const dataset = await this.readDataset({ dataset_name });
      datasetId_ = dataset.id;
    } else {
      throw new Error("Must provide a dataset_name or dataset_id");
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

  public async deleteExample(example_id: string): Promise<Example> {
    const path = `/examples/${example_id}`;
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
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
    example_id: string,
    {
      inputs,
      outputs,
      dataset_id,
    }: {
      inputs?: object;
      outputs?: object;
      dataset_id?: string;
    }
  ): Promise<object> {
    const example: any = {
      inputs,
      outputs,
      dataset_id: dataset_id,
    };
    const response = await this.caller.call(
      fetch,
      `${this.apiUrl}/examples/${example_id}`,
      {
        method: "PATCH",
        headers: { ...this.headers, "Content-Type": "application/json" },
        body: JSON.stringify(example),
      }
    );
    if (!response.ok) {
      throw new Error(
        `Failed to update example ${example_id}: ${response.status} ${response.statusText}`
      );
    }
    const result = await response.json();
    return result;
  }

  public async createFeedback(
    run_id: string,
    key: string,
    {
      score,
      value,
      correction,
      comment,
      sourceInfo,
      feedbackSourceType = "API",
    }: {
      score?: number | boolean;
      value?: number | boolean | string | object;
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
      run_id: run_id,
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
    });
    if (!response.ok) {
      throw new Error(
        `Failed to create feedback for run ${run_id}: ${response.status} ${response.statusText}`
      );
    }
    const result = await response.json();
    return result as Feedback;
  }

  public async readFeedback(feedback_id: string): Promise<Feedback> {
    const path = `/feedback/${feedback_id}`;
    const response = await this._get<Feedback>(path);
    return response;
  }

  public async deleteFeedback(feedback_id: string): Promise<Feedback> {
    const path = `/feedback/${feedback_id}`;
    const response = await this.caller.call(fetch, this.apiUrl + path, {
      method: "DELETE",
      headers: this.headers,
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
    run_ids,
  }: {
    run_ids?: string[];
  } = {}): Promise<Feedback[]> {
    const queryParams = new URLSearchParams();
    if (run_ids) {
      queryParams.append("run", run_ids.join(","));
    }
    const response = await this._get<Feedback[]>("/feedback", queryParams);
    return response;
  }
}
