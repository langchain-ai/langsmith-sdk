import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { ReadableSpan } from "@opentelemetry/sdk-trace-base";
import * as constants from "./constants.js";
import { isEnvTracingEnabled } from "../../env.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "../../utils/env.js";
import { extractUsageMetadata } from "../../utils/vercel.js";
import { warnOnce } from "../../utils/warn.js";
import { AgentAddress, ensureAgent } from "../../address.js";
import { rejectConflicting } from "../../utils/addressing.js";

/**
 * Convert headers string in format "name=value,name2=value2" to object
 */
function parseHeadersString(headersStr: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (!headersStr) return headers;

  headersStr.split(",").forEach((pair) => {
    const [name, ...valueParts] = pair.split("=");
    if (name && valueParts.length > 0) {
      headers[name.trim()] = valueParts.join("=").trim();
    }
  });

  return headers;
}

export type LangSmithOTLPTraceExporterConfig = ConstructorParameters<
  typeof OTLPTraceExporter
>[0] & {
  /**
   * A function that takes an exported span and returns a transformed version of it.
   * May be used to add or remove attributes from the span.
   *
   * For example, to add a custom attribute to the span, you can do:
   *
   * ```ts
   * import { LangSmithOTLPTraceExporter } from "langsmith/experimental/otel/exporter";
   *
   * const exporter = new LangSmithOTLPTraceExporter({
   *   transformExportedSpan: (span) => {
   *     if (span.name === "foo") {
   *       span.attributes["langsmith.metadata.bar"] = "baz";
   *     }
   *     return span;
   *   }
   * });
   * ```
   *
   * @param span - The span to transform.
   * @returns A transformed version of the span.
   */
  transformExportedSpan?: (
    span: ReadableSpan,
  ) => ReadableSpan | Promise<ReadableSpan>;

  /**
   * The API key to use for the exporter.
   */
  apiKey?: string;

  /**
   * The name of the project to export traces to.
   */
  projectName?: string;

  /**
   * (beta) The agent environment to export traces to, instead of a project.
   * Defaults to the one `LANGSMITH_AGENT_ID` and `LANGSMITH_AGENT_ENVIRONMENT`
   * name. Naming both a project and an address throws. Agent addressing is
   * enabled per workspace.
   */
  address?: AgentAddress;

  /**
   * Default headers to add to exporter requests.
   */
  headers?: Record<string, string>;
};

/**
 * LangSmith OpenTelemetry trace exporter that extends the standard OTLP trace exporter
 * with LangSmith-specific configuration and span attribute transformations.
 *
 * This exporter automatically configures itself with LangSmith endpoints and API keys,
 * based on your LANGSMITH_API_KEY and LANGSMITH_PROJECT environment variables.
 * OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is a full traces URL and takes precedence over
 * OTEL_EXPORTER_OTLP_ENDPOINT, a base URL to which /v1/traces is appended unless
 * it already ends in /traces for compatibility.
 * Also respects OTEL_EXPORTER_OTLP_HEADERS if set.
 *
 * @param config - Optional configuration object that accepts all OTLPTraceExporter parameters.
 *                 If not provided, uses default LangSmith configuration:
 *                 - `url`: Defaults to LangSmith OTEL endpoint (`${LANGSMITH_ENDPOINT}/otel/v1/traces`)
 *                 - `headers`: Auto-configured with LangSmith API key and project headers
 *                 Any provided config will override these defaults.
 */
export class LangSmithOTLPTraceExporter extends OTLPTraceExporter {
  private transformExportedSpan?: (
    span: ReadableSpan,
  ) => ReadableSpan | Promise<ReadableSpan>;

  private projectName?: string;
  private address?: AgentAddress;

  constructor(config?: LangSmithOTLPTraceExporterConfig) {
    const defaultLsEndpoint =
      getLangSmithEnvironmentVariable("ENDPOINT") ||
      "https://api.smith.langchain.com";
    const defaultBaseUrl = defaultLsEndpoint.replace(/\/$/, "");
    const baseEndpoint =
      getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT") ||
      `${defaultBaseUrl}/otel`;
    const defaultUrl =
      getEnvironmentVariable("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") ||
      (baseEndpoint.endsWith("/traces")
        ? baseEndpoint
        : `${baseEndpoint.replace(/\/$/, "")}/v1/traces`);
    if (
      config?.url === undefined &&
      !getEnvironmentVariable("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") &&
      baseEndpoint.endsWith("/traces")
    ) {
      warnOnce(
        "LangSmith now treats OTEL_EXPORTER_OTLP_ENDPOINT as a base URL and " +
          "appends /v1/traces. Your value ends in /traces, so it is being " +
          "preserved unchanged for compatibility. This fallback will be " +
          "removed in the v1 release of the SDK. Move this full URL to " +
          "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT to use standard OpenTelemetry " +
          "configuration.",
      );
    }
    // Configure headers with API key and project if available
    let headers = config?.headers;
    if (headers === undefined) {
      let defaultHeaderString =
        getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS") ?? "";
      if (!defaultHeaderString) {
        const apiKey =
          config?.apiKey ?? getLangSmithEnvironmentVariable("API_KEY");
        if (apiKey) {
          defaultHeaderString = `x-api-key=${apiKey}`;
        }
      }
      headers = parseHeadersString(defaultHeaderString);
    }

    super({
      url: defaultUrl,
      headers,
      ...config,
    });

    this.transformExportedSpan = config?.transformExportedSpan;
    const address = ensureAgent(config?.address);
    rejectConflicting(config?.projectName, address);
    if (config?.projectName !== undefined || address !== undefined) {
      this.projectName = config?.projectName;
      this.address = address;
    } else {
      // Like a run, the env decides when nothing is named here: an address
      // when `LANGSMITH_AGENT_*` names one, else the project.
      const envProject = getLangSmithEnvironmentVariable("PROJECT");
      const envAddress = AgentAddress.fromEnv();
      rejectConflicting(envProject, envAddress);
      this.projectName = envProject;
      this.address = envAddress;
    }
  }

  export(
    spans: ReadableSpan[],
    resultCallback: Parameters<OTLPTraceExporter["export"]>[1],
  ): void {
    if (!isEnvTracingEnabled()) {
      return resultCallback({ code: 0 });
    }
    const runExport = async () => {
      for (let span of spans) {
        if (this.transformExportedSpan) {
          span = await this.transformExportedSpan(span);
        }
        if (!span.attributes[constants.GENAI_PROMPT]) {
          if (span.attributes["ai.prompt"]) {
            span.attributes[constants.GENAI_PROMPT] =
              span.attributes["ai.prompt"];
          }
          if (
            span.attributes["ai.prompt.messages"] &&
            typeof span.attributes["ai.prompt.messages"] === "string"
          ) {
            let messages;
            try {
              messages = JSON.parse(span.attributes["ai.prompt.messages"]);
            } catch (e) {
              console.error("Failed to parse ai.prompt.messages", e);
            }
            if (messages && Array.isArray(messages)) {
              span.attributes[constants.GENAI_PROMPT] = JSON.stringify({
                input: messages,
              });
            }
          }
          if (span.attributes["ai.toolCall.input"]) {
            span.attributes[constants.GENAI_PROMPT] =
              span.attributes["ai.toolCall.input"];
          } else if (span.attributes["ai.toolCall.args"]) {
            span.attributes[constants.GENAI_PROMPT] =
              span.attributes["ai.toolCall.args"];
          }
        }
        // Iterate over all attributes starting with "ai.telemetry.metadata"
        for (const [key, value] of Object.entries(span.attributes)) {
          if (key.startsWith("ai.telemetry.metadata.")) {
            if (key === "ai.telemetry.metadata.ls_project_name") {
              span.attributes[constants.LANGSMITH_SESSION_NAME] = value;
            } else if (key === "ai.telemetry.metadata.ls_project_id") {
              span.attributes[constants.LANGSMITH_SESSION_ID] = value;
            } else {
              const metadataKey = key.replace("ai.telemetry.metadata.", "");
              span.attributes[
                `${constants.LANGSMITH_METADATA}.${metadataKey}`
              ] = value;
            }
            delete span.attributes[key];
          }
        }
        if (!span.attributes[constants.GENAI_COMPLETION]) {
          if (span.attributes["ai.response.text"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.response.text"];
          }
          if (span.attributes["ai.response.choices"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.response.choices"];
          }
          if (span.attributes["ai.response.object"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.response.object"];
          }
          if (span.attributes["ai.response.toolCalls"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.response.toolCalls"];
          }
          if (span.attributes["ai.toolCall.output"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.toolCall.output"];
          } else if (span.attributes["ai.toolCall.result"]) {
            span.attributes[constants.GENAI_COMPLETION] =
              span.attributes["ai.toolCall.result"];
          }
        }
        if (
          typeof span.attributes["ai.operationId"] === "string" &&
          constants.AI_SDK_LLM_OPERATIONS.includes(
            span.attributes["ai.operationId"],
          )
        ) {
          span.attributes[constants.LANGSMITH_RUN_TYPE] = "llm";
          const usageMetadata = extractUsageMetadata(span);
          span.attributes[constants.LANGSMITH_USAGE_METADATA] =
            JSON.stringify(usageMetadata);
        } else if (
          typeof span.attributes["ai.operationId"] === "string" &&
          constants.AI_SDK_TOOL_OPERATIONS.includes(
            span.attributes["ai.operationId"],
          )
        ) {
          span.attributes[constants.LANGSMITH_RUN_TYPE] = "tool";
          if (span.attributes["ai.toolCall.name"]) {
            span.attributes[constants.LANGSMITH_NAME] =
              span.attributes["ai.toolCall.name"];
          }
        }
        if (span.attributes[`${constants.LANGSMITH_METADATA}.ls_run_name`]) {
          span.attributes[constants.LANGSMITH_NAME] =
            span.attributes[`${constants.LANGSMITH_METADATA}.ls_run_name`];
          delete span.attributes[`${constants.LANGSMITH_METADATA}.ls_run_name`];
        }
        if (this.address !== undefined) {
          // A span that names its own project or agent keeps it.
          if (
            span.attributes[constants.LANGSMITH_SESSION_NAME] === undefined &&
            span.attributes[constants.LANGSMITH_SESSION_ID] === undefined &&
            span.attributes[constants.LANGSMITH_AGENT_ID] === undefined
          ) {
            span.attributes[constants.LANGSMITH_AGENT_ID] = this.address.id;
            span.attributes[constants.LANGSMITH_AGENT_ENVIRONMENT] =
              this.address.environment;
          }
        } else if (
          span.attributes[constants.LANGSMITH_SESSION_NAME] === undefined &&
          this.projectName !== undefined
        ) {
          span.attributes[constants.LANGSMITH_SESSION_NAME] = this.projectName;
        }
      }
      super.export(spans, resultCallback);
    };
    void runExport();
  }
}
