/* eslint-disable @typescript-eslint/no-explicit-any */
import * as lib from "./index.js";

describe("Bindings", () => {
  it("should should minimally work", async () => {
    expect(lib.fibonacci(1)).toBe(1);
    expect(lib.fibonacci(2)).toBe(1);
    expect(lib.fibonacci(3)).toBe(2);
    expect(lib.fibonacci(4)).toBe(3);
    expect(lib.fibonacci(5)).toBe(5);
    expect(lib.fibonacci(6)).toBe(8);
  });
});
