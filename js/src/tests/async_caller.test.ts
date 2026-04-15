import { describe, it, expect } from "@jest/globals";
import { AsyncCaller } from "../utils/async_caller.js";

describe("AsyncCaller", () => {
  describe("AbortError handling", () => {
    it("should not retry when fetch is aborted via AbortSignal", async () => {
      let callCount = 0;
      const caller = new AsyncCaller({ maxRetries: 3 });

      const controller = new AbortController();
      // Abort immediately
      controller.abort();

      const callable = async () => {
        callCount++;
        // Simulate what fetch does when signal is already aborted
        controller.signal.throwIfAborted();
        return "should not reach";
      };

      await expect(caller.call(callable)).rejects.toThrow();
      expect(callCount).toBe(1); // Should NOT retry
    });

    it("should not retry when fetch throws DOMException AbortError", async () => {
      let callCount = 0;
      const caller = new AsyncCaller({ maxRetries: 3 });

      const callable = async () => {
        callCount++;
        // Simulate what fetch throws when aborted mid-flight
        const err = new DOMException("The operation was aborted", "AbortError");
        throw err;
      };

      await expect(caller.call(callable)).rejects.toThrow(
        "The operation was aborted"
      );
      expect(callCount).toBe(1); // Should NOT retry
    });

    it("should still retry on transient network errors", async () => {
      let callCount = 0;
      const caller = new AsyncCaller({ maxRetries: 2 });

      const callable = async () => {
        callCount++;
        if (callCount < 3) {
          throw new Error("fetch failed");
        }
        return "success";
      };

      const result = await caller.call(callable);
      expect(result).toBe("success");
      expect(callCount).toBe(3); // 1 initial + 2 retries
    });
  });
});
