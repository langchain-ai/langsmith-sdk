import {
  ReadableSpan,
  Span,
  BatchSpanProcessor,
} from "@opentelemetry/sdk-trace-base";
import { Context } from "@opentelemetry/api";
import {
  LANGSMITH_IS_ROOT,
  LANGSMITH_PARENT_RUN_ID,
  LANGSMITH_TRACEABLE,
} from "./constants.js";
import { getUuidFromOtelSpanId } from "./utils.js";

export function isTraceableSpan(span: ReadableSpan): boolean {
  return (
    span.attributes[LANGSMITH_TRACEABLE] === "true" ||
    typeof span.attributes["ai.operationId"] === "string"
  );
}

function getParentSpanId(span: ReadableSpan): string | undefined {
  // Backcompat shim to support OTEL 1.x and 2.x
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (
    (span as any).parentSpanId ?? span.parentSpanContext?.spanId ?? undefined
  );
}

type TraceInfo = {
  spanInfo: Record<
    string,
    { isTraceable: boolean; parentSpanId: string | undefined }
  >;
  lastAccessed: number;
};

/**
 * Span processor that filters out spans that are not LangSmith-related and
 * usually should not be traced.
 */
export class LangSmithOTLPSpanProcessor extends BatchSpanProcessor {
  private traceMap: Record<string, TraceInfo> = {};

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private cleanupInterval: any;

  private TRACE_TTL_MS = 10 * 60 * 1000; // 10 minutes

  constructor(...args: ConstructorParameters<typeof BatchSpanProcessor>) {
    super(...args);
    // We must use a cleanup interval because LangSmith can start child spans
    // after arbitrary OTEL parent spans have ended since it uses batching.
    this.cleanupInterval = setInterval(() => this.cleanupStaleTraces(), 60000);
  }

  private cleanupStaleTraces(): void {
    const now = Date.now();
    for (const [traceId, traceInfo] of Object.entries(this.traceMap)) {
      if (now - traceInfo.lastAccessed > this.TRACE_TTL_MS) {
        delete this.traceMap[traceId];
      }
    }
  }

  shutdown(): Promise<void> {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }
    return super.shutdown();
  }

  onStart(span: Span, parentContext: Context): void {
    if (!this.traceMap[span.spanContext().traceId]) {
      this.traceMap[span.spanContext().traceId] = {
        spanInfo: {},
        lastAccessed: Date.now(),
      };
    }
    this.traceMap[span.spanContext().traceId].lastAccessed = Date.now();
    const isTraceable = isTraceableSpan(span);
    const parentSpanId = getParentSpanId(span);
    this.traceMap[span.spanContext().traceId].spanInfo[
      span.spanContext().spanId
    ] = {
      isTraceable,
      parentSpanId,
    };

    let currentCandidateParentSpanId = parentSpanId;
    let traceableParentId;
    while (currentCandidateParentSpanId) {
      const currentSpanInfo =
        this.traceMap[span.spanContext().traceId].spanInfo[
          currentCandidateParentSpanId
        ];
      if (currentSpanInfo?.isTraceable) {
        traceableParentId = currentCandidateParentSpanId;
        break;
      }
      currentCandidateParentSpanId = currentSpanInfo?.parentSpanId;
    }
    if (!traceableParentId) {
      span.attributes[LANGSMITH_IS_ROOT] = true;
    } else {
      span.attributes[LANGSMITH_PARENT_RUN_ID] =
        getUuidFromOtelSpanId(traceableParentId);
    }
    if (isTraceable) {
      super.onStart(span, parentContext);
    }
  }

  onEnd(span: ReadableSpan): void {
    const traceInfo = this.traceMap[span.spanContext().traceId];
    if (!traceInfo) return;

    traceInfo.lastAccessed = Date.now();
    const spanInfo = traceInfo.spanInfo[span.spanContext().spanId];
    if (!spanInfo) return;

    if (spanInfo.isTraceable) {
      super.onEnd(span);
    }
  }
}
