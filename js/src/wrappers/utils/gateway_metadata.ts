import type { RunTree } from "../../run_trees.js";
import { getCurrentRunTree } from "../../singletons/traceable.js";

const GATEWAY_METADATA_HEADER = "x-langsmith-gateway-metadata";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getHeaders(value: unknown): unknown {
  if (!isRecord(value)) return undefined;
  if (value.headers != null) return value.headers;
  if (value.responseHeaders != null) return value.responseHeaders;
  if (value.response != null) {
    const nested = getHeaders(value.response);
    if (nested != null) return nested;
  }
  if (value.sdkHttpResponse != null) return getHeaders(value.sdkHttpResponse);
  return undefined;
}

function readGatewayHeader(value: unknown): string | undefined {
  if (!isRecord(value)) return undefined;
  if (typeof value.get === "function") {
    const result: unknown = value.get(GATEWAY_METADATA_HEADER);
    return typeof result === "string" ? result : undefined;
  }
  for (const [key, headerValue] of Object.entries(value)) {
    if (
      key.toLowerCase() === GATEWAY_METADATA_HEADER &&
      typeof headerValue === "string"
    ) {
      return headerValue;
    }
  }
  return undefined;
}

export function getGatewayResponseMetadata(
  headersOrResponse: unknown,
): Record<string, unknown> | undefined {
  const headers = getHeaders(headersOrResponse) ?? headersOrResponse;
  const rawMetadata = readGatewayHeader(headers);
  if (!rawMetadata) return undefined;

  try {
    const gatewayInfo: unknown = JSON.parse(rawMetadata);
    return isRecord(gatewayInfo) ? gatewayInfo : undefined;
  } catch {
    // Invalid diagnostic metadata must never affect the provider call.
    return undefined;
  }
}

export function addGatewayResponseMetadata(
  runTree: RunTree | undefined,
  headersOrResponse: unknown,
): void {
  if (!runTree) return;
  const gatewayInfo = getGatewayResponseMetadata(headersOrResponse);
  if (!gatewayInfo) return;
  runTree.extra = {
    ...runTree.extra,
    metadata: {
      ...runTree.extra?.metadata,
      ls_gateway_info: gatewayInfo,
    },
  };
}

export function captureGatewayResponseMetadata(
  result: unknown,
  runTree = getCurrentRunTree(true),
): void {
  if (!runTree) return;

  if (isRecord(result) && typeof result.asResponse === "function") {
    void Promise.resolve(result.asResponse())
      .then((response) => addGatewayResponseMetadata(runTree, response))
      .catch((error) => addGatewayResponseMetadata(runTree, error));
    return;
  }

  if (isRecord(result) && typeof result.withResponse === "function") {
    void Promise.resolve(result.withResponse())
      .then((wrapped) => addGatewayResponseMetadata(runTree, wrapped))
      .catch((error) => addGatewayResponseMetadata(runTree, error));
    return;
  }

  if (isRecord(result) && typeof result.then === "function") {
    void Promise.resolve(result)
      .then((value) => addGatewayResponseMetadata(runTree, value))
      .catch((error) => addGatewayResponseMetadata(runTree, error));
    return;
  }

  addGatewayResponseMetadata(runTree, result);
}

export function wrapWithGatewayResponseMetadata<
  TArgs extends unknown[],
  TResult,
>(fn: (...args: TArgs) => TResult): (...args: TArgs) => TResult {
  return (...args) => {
    const result = fn(...args);
    captureGatewayResponseMetadata(result);
    return result;
  };
}
