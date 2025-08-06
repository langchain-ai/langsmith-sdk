/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { ReadableSpan } from "@opentelemetry/sdk-trace-base";
import { LangSmithOTLPTraceExporter } from "../experimental/otel/exporter.js";
import * as constants from "../experimental/otel/constants.js";
class TestExporter extends LangSmithOTLPTraceExporter {
  // Override the super.export to capture what gets sent
  constructor() {
    super({ url: "http://test", headers: {} });
  }

  // Make the protected export method public for testing
  public async testExport(spans: ReadableSpan[]): Promise<ReadableSpan[]> {
    // Create a copy of spans to avoid mutating the original
    const testSpans = spans.map((span) => ({
      ...span,
      attributes: { ...span.attributes },
    }));

    return new Promise((resolve) => {
      // Mock super.export to avoid HTTP calls but capture processed spans
      const originalSuperExport = Object.getPrototypeOf(
        LangSmithOTLPTraceExporter.prototype
      ).export;
      Object.getPrototypeOf(LangSmithOTLPTraceExporter.prototype).export =
        function (_processedSpans: ReadableSpan[], callback: any) {
          // Just call the callback with success and return the processed spans
          callback({ code: 0 });
        };

      // Call our export method which will process the spans and call super.export
      this.export(testSpans, () => {
        // Restore the original method
        Object.getPrototypeOf(LangSmithOTLPTraceExporter.prototype).export =
          originalSuperExport;
        resolve(testSpans);
      });
    });
  }
}

// Mock span factory
function createMockSpan(
  dottedOrder: string,
  startTime?: [number, number]
): ReadableSpan {
  const defaultStartTime: [number, number] = [1701432000, 0]; // 2023-12-01T12:00:00Z

  return {
    spanContext: () => ({
      traceId: "test-trace",
      spanId: "test-span",
      traceFlags: 0,
    }),
    startTime: startTime || defaultStartTime,
    endTime: [defaultStartTime[0] + 1, 0],
    attributes: {
      [constants.LANGSMITH_DOTTED_ORDER]: dottedOrder,
      [constants.LANGSMITH_TRACEABLE]: "true",
    },
    status: { code: 1 },
    name: "test-span",
    kind: 1,
    parentSpanId: undefined,
    resource: {} as any,
    instrumentationLibrary: {} as any,
    instrumentationScope: {} as any,
    events: [],
    links: [],
    ended: true,
    duration: [1, 0],
    droppedAttributesCount: 0,
    droppedEventsCount: 0,
    droppedLinksCount: 0,
  } as ReadableSpan;
}

describe("OTEL Exporter Start Time Correction", () => {
  let exporter: TestExporter;

  beforeEach(() => {
    exporter = new TestExporter();
  });

  test("should correct start time based on dotted order", async () => {
    // Create a span with incorrect start time but corrected dotted order
    const correctedDotOrder = "20231201T120000001000Ztest-run-id"; // 12:00:00.001Z with 000 microseconds
    const originalStartTime: [number, number] = [1701432000, 0]; // 12:00:00.000Z

    const span = createMockSpan(correctedDotOrder, originalStartTime);

    const processedSpans = await exporter.testExport([span]);

    expect(processedSpans).toHaveLength(1);
    const processedSpan = processedSpans[0];

    // Check that the start time was directly modified
    const expectedCorrectedMs = new Date("2023-12-01T12:00:00.001Z").getTime();
    // Include the 000 microseconds from the dotted order
    const expectedCorrectedHrTime: [number, number] = [
      Math.floor(expectedCorrectedMs / 1000),
      (expectedCorrectedMs % 1000) * 1000000 + 0 * 1000, // 000 microseconds = 0 * 1000 nanoseconds
    ];
    expect(processedSpan.startTime).toEqual(expectedCorrectedHrTime);
  });

  test("should handle invalid dotted order gracefully", async () => {
    const invalidDotOrder = "invalid-dotted-order";
    const originalStartTime: [number, number] = [1701432000, 0];

    const span = createMockSpan(invalidDotOrder, originalStartTime);

    const processedSpans = await exporter.testExport([span]);

    expect(processedSpans).toHaveLength(1);
    const processedSpan = processedSpans[0];

    // Should keep original start time when dotted order is invalid
    expect(processedSpan.startTime).toEqual(originalStartTime);
  });

  test("should handle spans without dotted order", async () => {
    const originalStartTime: [number, number] = [1701432000, 0];

    const span: ReadableSpan = {
      ...createMockSpan("", originalStartTime),
      attributes: {
        // No LANGSMITH_DOTTED_ORDER attribute
        [constants.LANGSMITH_TRACEABLE]: "true",
      },
    };

    const processedSpans = await exporter.testExport([span]);

    expect(processedSpans).toHaveLength(1);
    const processedSpan = processedSpans[0];

    // Should keep original start time when no dotted order
    expect(processedSpan.startTime).toEqual(originalStartTime);
  });

  test("should correct multiple spans with different dotted orders", async () => {
    const span1 = createMockSpan("20231201T120000001000Zrun1", [1701432000, 0]);
    const span2 = createMockSpan("20231201T120000002000Zrun2", [1701432000, 0]);

    const processedSpans = await exporter.testExport([span1, span2]);

    expect(processedSpans).toHaveLength(2);

    // First span should have corrected start time with 000 microseconds
    const expectedTime1Ms = new Date("2023-12-01T12:00:00.001Z").getTime();
    const expectedTime1: [number, number] = [
      Math.floor(expectedTime1Ms / 1000),
      (expectedTime1Ms % 1000) * 1000000 + 0 * 1000, // 000 microseconds
    ];
    expect(processedSpans[0].startTime).toEqual(expectedTime1);

    // Second span should have corrected start time with 000 microseconds
    const expectedTime2Ms = new Date("2023-12-01T12:00:00.002Z").getTime();
    const expectedTime2: [number, number] = [
      Math.floor(expectedTime2Ms / 1000),
      (expectedTime2Ms % 1000) * 1000000 + 0 * 1000, // 000 microseconds
    ];
    expect(processedSpans[1].startTime).toEqual(expectedTime2);
  });

  test("should preserve microseconds from dotted order with execution order", async () => {
    // Create a span with execution order microseconds (e.g., from timing fix with executionOrder=123)
    const dottedOrderWithMicroseconds =
      "20231201T120000001123Zrun-with-microseconds";
    const span = createMockSpan(dottedOrderWithMicroseconds, [1701432000, 0]);

    const processedSpans = await exporter.testExport([span]);

    expect(processedSpans).toHaveLength(1);
    const processedSpan = processedSpans[0];

    // Check that microseconds are preserved in the HrTime format
    const expectedTimeMs = new Date("2023-12-01T12:00:00.001Z").getTime();
    const expectedTime: [number, number] = [
      Math.floor(expectedTimeMs / 1000),
      (expectedTimeMs % 1000) * 1000000 + 123 * 1000, // 123 microseconds = 123000 nanoseconds
    ];
    expect(processedSpan.startTime).toEqual(expectedTime);
  });
});
