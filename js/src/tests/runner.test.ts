import { _includeAttachments } from "../evaluation/_runner.js";

describe("_includeAttachments", () => {
  test("should return false for single parameter functions", () => {
    const fn = async (inputs: any) => null;
    expect(_includeAttachments(fn)).toBe(false);
  });

  test("should return true for two parameter functions", () => {
    const fn = async (inputs: any, attachments: any) => null;
    expect(_includeAttachments(fn)).toBe(true);
  });

  test("should return false for functions with optional parameters", () => {
    const fn = async (inputs: any, optional?: any) => null;
    expect(_includeAttachments(fn)).toBe(false);
  });

  test("should return false for objects with invoke method", () => {
    const runnable = {
      invoke: (x: any) => x,
    };
    expect(_includeAttachments(runnable)).toBe(false);
  });

  test("should return false for functions with more than two parameters", () => {
    const fn = async (inputs: any, attachments: any, extra: any) => null;
    expect(_includeAttachments(fn)).toBe(false);
  });
});