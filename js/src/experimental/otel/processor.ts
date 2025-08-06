import {
  ReadableSpan,
  Span,
  BatchSpanProcessor,
} from "@opentelemetry/sdk-trace-base";
import { Context, type HrTime } from "@opentelemetry/api";
import {
  LANGSMITH_IS_ROOT,
  LANGSMITH_PARENT_RUN_ID,
  LANGSMITH_TRACEABLE,
  LANGSMITH_DOTTED_ORDER,
  LANGSMITH_TRACE_ID,
} from "./constants.js";
import { getUuidFromOtelSpanId } from "./utils.js";
import { RunTree, stripNonAlphanumeric } from "../../run_trees.js";
import { fixDottedOrderTiming } from "../../utils/dotted_order.js";

const NANOSECOND_DIGITS = 9;
const MICROSECOND_DIGITS = 6;

export function isTraceableSpan(span: ReadableSpan): boolean {
  return (
    span.attributes[LANGSMITH_TRACEABLE] === "true" ||
    typeof span.attributes["ai.operationId"] === "string"
  );
}

/**
 * Convert hrTime to timestamp, for example "2019-05-14T17:00:00.000123Z"
 * @param time
 */
function hrTimeToTimeStamp(time: HrTime): string {
  const precision = NANOSECOND_DIGITS;
  const tmp = `${"0".repeat(precision)}${time[1]}Z`;
  const nanoString = tmp.substring(tmp.length - precision - 1);
  const date = new Date(time[0] * 1000).toISOString();
  // We only need 6 digits of precision for the dotted order
  return `${date.replace("000Z", nanoString.slice(0, MICROSECOND_DIGITS))}Z`;
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
    {
      isTraceable: boolean;
      lsTraceId: string;
      spanId: string;
      parentSpanId: string | undefined;
      dottedOrder: string;
    }
  >;
  spanCount: number;
};

/**
 * Span processor that filters out spans that are not LangSmith-related and
 * usually should not be traced.
 */
export class LangSmithOTLPSpanProcessor extends BatchSpanProcessor {
  private traceMap: Record<string, TraceInfo> = {};

  onStart(span: Span, parentContext: Context): void {
    if (!this.traceMap[span.spanContext().traceId]) {
      this.traceMap[span.spanContext().traceId] = {
        spanInfo: {},
        spanCount: 0,
      };
    }
    this.traceMap[span.spanContext().traceId].spanCount++;
    const isTraceable = isTraceableSpan(span);
    const parentSpanId = getParentSpanId(span);

    let currentCandidateParentSpanId = parentSpanId;
    let traceableParentId;
    let parentDottedOrder;
    // LangSmith uses the first span's id as the trace id, NOT the actual OTEL trace id
    // Default to the current span if no parent information is present
    let lsTraceId = getUuidFromOtelSpanId(span.spanContext().spanId);
    while (currentCandidateParentSpanId) {
      const currentSpanInfo =
        this.traceMap[span.spanContext().traceId].spanInfo[
          currentCandidateParentSpanId
        ];
      if (currentSpanInfo?.isTraceable) {
        traceableParentId = currentCandidateParentSpanId;
        parentDottedOrder = currentSpanInfo.dottedOrder;
        lsTraceId = currentSpanInfo.lsTraceId;
        break;
      }
      currentCandidateParentSpanId = currentSpanInfo?.parentSpanId;
    }
    const startTimestamp = hrTimeToTimeStamp(span.startTime);
    const spanUuid = getUuidFromOtelSpanId(span.spanContext().spanId);
    const dottedOrderComponent =
      stripNonAlphanumeric(startTimestamp) + spanUuid;
    const rawDottedOrder = parentDottedOrder
      ? `${parentDottedOrder}.${dottedOrderComponent}`
      : dottedOrderComponent;

    // Apply timing fix to ensure chronological ordering
    // Use the span count as execution order for mock microseconds
    const executionOrder = this.traceMap[span.spanContext().traceId].spanCount;
    const currentDottedOrder = fixDottedOrderTiming(
      rawDottedOrder,
      executionOrder
    );
    this.traceMap[span.spanContext().traceId].spanInfo[
      span.spanContext().spanId
    ] = {
      isTraceable,
      lsTraceId,
      spanId: span.spanContext().spanId,
      parentSpanId,
      dottedOrder: currentDottedOrder,
    };
    if (!traceableParentId) {
      span.attributes[LANGSMITH_IS_ROOT] = true;
    } else {
      span.attributes[LANGSMITH_PARENT_RUN_ID] =
        getUuidFromOtelSpanId(traceableParentId);
    }
    span.attributes[LANGSMITH_DOTTED_ORDER] = currentDottedOrder;
    span.attributes[LANGSMITH_TRACE_ID] = lsTraceId;
    if (isTraceable) {
      super.onStart(span, parentContext);
    }
  }

  onEnd(span: ReadableSpan): void {
    const traceInfo = this.traceMap[span.spanContext().traceId];
    if (!traceInfo) return;

    const spanInfo = traceInfo.spanInfo[span.spanContext().spanId];
    if (!spanInfo) return;

    // Decrement span count and cleanup trace if all spans are done
    traceInfo.spanCount--;
    if (traceInfo.spanCount <= 0) {
      delete this.traceMap[span.spanContext().traceId];
    }

    if (spanInfo.isTraceable) {
      super.onEnd(span);
    }
  }

  async shutdown() {
    await RunTree.getSharedClient().awaitPendingTraceBatches();
    await super.shutdown();
  }
}
