import { stripNonAlphanumeric } from "../run_trees.js";

// Helper function to convert stripped ISO string back to parseable format
export const parseStrippedIsoTime = (stripped: string): Date => {
  // Insert back the removed characters: YYYYMMDDTHHMMSSSSSSSS -> YYYY-MM-DDTHH:MM:SS.SSSZ
  // The stripped format is timestamp part only (no Z - that becomes the separator)
  // Format includes microseconds: 20231201T120000000000 (milliseconds + microseconds)
  const year = stripped.slice(0, 4);
  const month = stripped.slice(4, 6);
  const day = stripped.slice(6, 8);
  const hour = stripped.slice(9, 11); // Skip 'T'
  const minute = stripped.slice(11, 13);
  const second = stripped.slice(13, 15);
  const ms = stripped.slice(15, 18); // Only use first 3 digits for milliseconds
  // Ignore microseconds (18-21) as Date only has millisecond precision

  return new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}.${ms}Z`);
};

// Helper function to convert Date back to stripped format
export const toStrippedIsoTime = (
  date: Date,
  executionOrder?: number
): string => {
  if (executionOrder !== undefined) {
    // Mock microseconds using execution order like in convertToDottedOrderFormat
    const paddedOrder = executionOrder.toFixed(0).slice(0, 3).padStart(3, "0");
    const microsecondIso = `${date.toISOString().slice(0, -1)}${paddedOrder}Z`;
    // stripNonAlphanumeric removes -:. but keeps Z, so remove the Z manually after stripping
    return stripNonAlphanumeric(microsecondIso).slice(0, -1);
  }

  return stripNonAlphanumeric(date.toISOString().slice(0, -1)) + "000";
};

/**
 * Fixes timing issues in dotted order strings where child segments have timestamps
 * less than or equal to their parent segments. Ensures chronological ordering by
 * incrementing child timestamps to be parent + 1ms when needed.
 *
 * @param dotOrder - Dotted order string like "timestamp1Zid1.timestamp2Zid2"
 * @param executionOrder - Optional execution order to mock microseconds for tie-breaking
 * @returns Fixed dotted order string with corrected timestamps
 */
export function fixDottedOrderTiming(
  dotOrder: string,
  executionOrder?: number
): string {
  const segments = dotOrder.split(".").map((i) => {
    const [startTime, runId] = i.split("Z");
    return { startTime, runId };
  });

  // Iteratively check and fix timing to ensure each segment is greater than its parent
  for (let i = 1; i < segments.length; i++) {
    try {
      const parentTime = parseStrippedIsoTime(segments[i - 1].startTime);
      const currentTime = parseStrippedIsoTime(segments[i].startTime);

      // Validate parsed dates
      if (isNaN(parentTime.getTime()) || isNaN(currentTime.getTime())) {
        console.error("Invalid timestamp in dotted order:", dotOrder);
        continue;
      }

      if (currentTime.getTime() <= parentTime.getTime()) {
        // Increment by 1 millisecond to make it greater than parent
        const newTime = new Date(parentTime.getTime() + 1);
        // Use execution order for mock microseconds if provided, incremented for each segment
        const segmentExecutionOrder =
          executionOrder !== undefined ? executionOrder + i : undefined;
        segments[i].startTime = toStrippedIsoTime(
          newTime,
          segmentExecutionOrder
        );
      }
    } catch (error) {
      console.error("Error processing dotted order segment:", error, dotOrder);
      continue;
    }
  }

  // Reconstruct the dotted order with potentially updated timestamps
  return segments
    .map((segment) => `${segment.startTime}Z${segment.runId}`)
    .join(".");
}

/**
 * Extracts the start time from the final segment of a dotted order string.
 * Useful for setting the start_time field of runs based on their position in the trace hierarchy.
 *
 * @param dotOrder - Dotted order string like "timestamp1Zid1.timestamp2Zid2"
 * @returns ISO timestamp string of the final segment, or throws error if invalid
 */
export function getStartTimeFromDottedOrder(dotOrder: string): string {
  const segments = dotOrder.split(".");
  if (segments.length === 0) {
    throw new Error(`Empty dotted order: ${dotOrder}`);
  }

  const lastSegment = segments[segments.length - 1];
  const [startTime] = lastSegment.split("Z");

  if (!startTime) {
    throw new Error(`Invalid dotted order segment: ${lastSegment}`);
  }

  try {
    const parsedTime = parseStrippedIsoTime(startTime);

    // Validate the parsed timestamp
    if (isNaN(parsedTime.getTime())) {
      throw new Error(`Invalid timestamp in dotted order: ${dotOrder}`);
    }

    return parsedTime.toISOString();
  } catch (error) {
    console.error(
      "Error parsing start time from dotted order:",
      error,
      dotOrder
    );
    throw new Error(
      `Failed to parse start time from dotted order: ${dotOrder}`
    );
  }
}
