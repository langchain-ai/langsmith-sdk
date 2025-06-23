import { getEnvironmentVariable, setEnvironmentVariable } from "../../utils/env.js";

export interface TracerProvider {
  addSpanProcessor(processor: any): void;
}

export interface OTLPExporter {
  export(spans: any[], resultCallback: (result: any) => void): void;
}

const HAS_OTEL = getEnvironmentVariable("OTEL_ENABLED") === "true";

export function getOtlpTracerProvider(): TracerProvider {
  if (!HAS_OTEL) {
    throw new Error(
      "OpenTelemetry packages are required to use this function. " +
      "Please install the required OpenTelemetry packages."
    );
  }

  // Set LangSmith-specific defaults if not already set in environment
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT")) {
    const lsEndpoint = getEnvironmentVariable("LANGSMITH_ENDPOINT") || 
                      getEnvironmentVariable("LANGCHAIN_ENDPOINT") || 
                      "https://api.smith.langchain.com";
    setEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT", `${lsEndpoint}/otel`);
  }

  // Configure headers with API key and project if available
  if (!getEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS")) {
    const apiKey = getEnvironmentVariable("LANGSMITH_API_KEY") || 
                   getEnvironmentVariable("LANGCHAIN_API_KEY");
    
    if (!apiKey) {
      throw new Error("LANGSMITH_API_KEY or LANGCHAIN_API_KEY environment variable is required");
    }
    
    let headers = `x-api-key=${apiKey}`;

    const project = getEnvironmentVariable("LANGSMITH_PROJECT") || 
                    getEnvironmentVariable("LANGCHAIN_PROJECT");
    if (project) {
      headers += `,Langsmith-Project=${project}`;
    }

    setEnvironmentVariable("OTEL_EXPORTER_OTLP_HEADERS", headers);
  }

  // Note: We can't directly use OpenTelemetry imports here due to the conditional import requirement
  // The actual implementation would need to be handled by the consumer
  // This is a placeholder that maintains the API contract
  
  return {
    addSpanProcessor: (_processor: any) => {
      // Implementation would depend on actual OpenTelemetry imports
      throw new Error("OpenTelemetry TracerProvider not properly initialized");
    }
  };
}