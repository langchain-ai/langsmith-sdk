/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { getMutableRunCreate } from "../vercel.js";
import {
  parseStrippedIsoTime,
  toStrippedIsoTime,
  fixDottedOrderTiming,
  getStartTimeFromDottedOrder,
} from "../utils/dotted_order.js";

describe("vercel utils", () => {
  describe("parseStrippedIsoTime and toStrippedIsoTime", () => {
    test("should parse and format stripped ISO time correctly", () => {
      const originalDate = new Date("2023-12-01T12:30:45.678Z");
      const stripped = toStrippedIsoTime(originalDate);
      expect(stripped).toBe("20231201T123045678000");

      // When parsing, we work with the timestamp part only (no Z suffix)
      const parsed = parseStrippedIsoTime(stripped);
      expect(parsed.toISOString()).toBe("2023-12-01T12:30:45.678Z");
    });
  });

  describe("fixDottedOrderTiming", () => {
    test("should fix timing when child segment equals parent timestamp", () => {
      const dotOrder =
        "20231201T120000000000Zparent-id.20231201T120000000000Zchild-id";
      const result = fixDottedOrderTiming(dotOrder);

      expect(result).toBe(
        "20231201T120000000000Zparent-id.20231201T120000001000Zchild-id"
      );
    });

    test("should handle multiple segments with cascading fixes", () => {
      const dotOrder =
        "20231201T120000000000Zroot-id.20231201T120000000000Zparent-id.20231201T120000000000Zchild-id";
      const result = fixDottedOrderTiming(dotOrder);

      expect(result).toBe(
        "20231201T120000000000Zroot-id.20231201T120000001000Zparent-id.20231201T120000002000Zchild-id"
      );
    });

    test("should handle already correct timing", () => {
      const dotOrder =
        "20231201T120000000000Zparent-id.20231201T120001000000Zchild-id";
      const result = fixDottedOrderTiming(dotOrder);

      expect(result).toBe(
        "20231201T120000000000Zparent-id.20231201T120001000000Zchild-id"
      );
    });
  });

  describe("getStartTimeFromDottedOrder", () => {
    test("should extract start time from single segment", () => {
      const dotOrder = "20231201T120000000000Zroot-id";
      const result = getStartTimeFromDottedOrder(dotOrder);

      expect(result).toBe("2023-12-01T12:00:00.000Z");
    });

    test("should extract start time from final segment", () => {
      const dotOrder =
        "20231201T120000000000Zparent-id.20231201T120001000000Zchild-id";
      const result = getStartTimeFromDottedOrder(dotOrder);

      expect(result).toBe("2023-12-01T12:00:01.000Z");
    });

    test("should handle corrected dotted order", () => {
      // After timing fix, child should be parent + 1ms
      const fixedDotOrder =
        "20231201T120000000000Zparent-id.20231201T120000001000Zchild-id";
      const result = getStartTimeFromDottedOrder(fixedDotOrder);

      expect(result).toBe("2023-12-01T12:00:00.001Z");
    });

    test("should throw error for invalid dotted order", () => {
      expect(() => getStartTimeFromDottedOrder("")).toThrow();
      expect(() => getStartTimeFromDottedOrder("invalid")).toThrow();
    });

    describe("fixDottedOrderTiming with microsecond preservation", () => {
      test("should preserve existing microseconds when fixing timing", () => {
        // Create a dotted order where child equals parent time but has execution order microseconds
        const parentTime = "20231201T120000000000"; // 000 microseconds
        const childTime = "20231201T120000000123"; // 123 microseconds from execution order
        const dotOrder = `${parentTime}Zparent-id.${childTime}Zchild-id`;

        const result = fixDottedOrderTiming(dotOrder);

        // The child should be incremented by 1ms but preserve the 123 microseconds
        expect(result).toMatch(/20231201T120000001123Zchild-id$/);
      });

      test("should preserve default microseconds", () => {
        const parentTime = "20231201T120000000000";
        const childTime = "20231201T120000000000";
        const dotOrder = `${parentTime}Zparent-id.${childTime}Zchild-id`;

        const result = fixDottedOrderTiming(dotOrder);

        // Should preserve the default "000" microseconds
        expect(result).toMatch(/20231201T120000001000Zchild-id$/);
      });
    });
  });

  describe("getMutableRunCreate", () => {
    test("should handle normal case without timing issues", () => {
      const dotOrder =
        "20231201T120000000000Zparent-id.20231201T120001000000Zchild-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result).toEqual({
        id: "child-id",
        trace_id: "parent-id",
        dotted_order:
          "20231201T120000000000Zparent-id.20231201T120001000000Zchild-id",
        parent_run_id: "parent-id",
        start_time: "2023-12-01T12:00:01.000Z",
      });
    });

    test("should fix timing when child segment equals parent timestamp", () => {
      // Child has same timestamp as parent
      const dotOrder =
        "20231201T120000000000Zparent-id.20231201T120000000000Zchild-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result.id).toBe("child-id");
      expect(result.trace_id).toBe("parent-id");
      expect(result.parent_run_id).toBe("parent-id");

      // Child timestamp should be incremented by 1ms
      expect(result.start_time).toBe("2023-12-01T12:00:00.001Z");
      expect(result.dotted_order).toBe(
        "20231201T120000000000Zparent-id.20231201T120000001000Zchild-id"
      );
    });

    test("should fix timing when child segment is less than parent timestamp", () => {
      // Child has earlier timestamp than parent (shouldn't happen but we handle it)
      const dotOrder =
        "20231201T120001000000Zparent-id.20231201T120000000000Zchild-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result.id).toBe("child-id");
      expect(result.trace_id).toBe("parent-id");
      expect(result.parent_run_id).toBe("parent-id");

      // Child timestamp should be incremented to parent + 1ms
      expect(result.start_time).toBe("2023-12-01T12:00:01.001Z");
      expect(result.dotted_order).toBe(
        "20231201T120001000000Zparent-id.20231201T120001001000Zchild-id"
      );
    });

    test("should handle iterative fixing for multiple segments", () => {
      // Multiple segments with timing issues
      const dotOrder =
        "20231201T120000000000Zroot-id.20231201T120000000000Zparent-id.20231201T120000000000Zchild-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result.id).toBe("child-id");
      expect(result.trace_id).toBe("root-id");
      expect(result.parent_run_id).toBe("parent-id");

      // Each segment should be incremented iteratively
      expect(result.start_time).toBe("2023-12-01T12:00:00.002Z");
      expect(result.dotted_order).toBe(
        "20231201T120000000000Zroot-id.20231201T120000001000Zparent-id.20231201T120000002000Zchild-id"
      );
    });

    test("should handle complex cascading timing fixes", () => {
      // Root: 12:00:05.000
      // Parent: 12:00:04.000 (earlier than root)
      // Child: 12:00:03.000 (earlier than parent)
      const dotOrder =
        "20231201T120005000000Zroot-id.20231201T120004000000Zparent-id.20231201T120003000000Zchild-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result.id).toBe("child-id");
      expect(result.trace_id).toBe("root-id");
      expect(result.parent_run_id).toBe("parent-id");

      // Parent should be root + 1ms = 12:00:05.001
      // Child should be parent + 1ms = 12:00:05.002
      expect(result.start_time).toBe("2023-12-01T12:00:05.002Z");
      expect(result.dotted_order).toBe(
        "20231201T120005000000Zroot-id.20231201T120005001000Zparent-id.20231201T120005002000Zchild-id"
      );
    });

    test("should handle single segment (root only)", () => {
      const dotOrder = "20231201T120000000000Zroot-id";
      const result = getMutableRunCreate(dotOrder);

      expect(result).toEqual({
        id: "root-id",
        trace_id: "root-id",
        dotted_order: "20231201T120000000000Zroot-id",
        parent_run_id: undefined,
        start_time: "2023-12-01T12:00:00.000Z",
      });
    });
  });
});
