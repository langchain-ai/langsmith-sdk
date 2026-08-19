import { describe, expect, it } from "vitest";
import { RunTree } from "../run_trees.js";
import { withRunTree } from "../singletons/traceable.js";
import {
  addGatewayResponseMetadata,
  captureGatewayResponseMetadata,
} from "../wrappers/utils/gateway_metadata.js";

function createRun(): RunTree {
  return new RunTree({ name: "gateway", run_type: "llm", inputs: {} });
}

describe("gateway response metadata", () => {
  it("attaches parsed gateway metadata from Fetch Headers", () => {
    const run = createRun();
    const headers = new Headers({
      "X-LangSmith-Gateway-Metadata": JSON.stringify({
        outcome: "blocked",
        reason: "rate_limit",
      }),
    });

    addGatewayResponseMetadata(run, headers);

    expect(run.extra?.metadata?.ls_gateway_info).toEqual({
      outcome: "blocked",
      reason: "rate_limit",
    });
  });

  it("supports Gemini-style plain header records", () => {
    const run = createRun();

    addGatewayResponseMetadata(run, {
      sdkHttpResponse: {
        headers: {
          "X-LangSmith-Gateway-Metadata": '{"outcome":"success"}',
        },
      },
    });

    expect(run.extra?.metadata?.ls_gateway_info).toEqual({
      outcome: "success",
    });
  });

  it("supports AI SDK error response headers", () => {
    const run = createRun();

    addGatewayResponseMetadata(run, {
      responseHeaders: {
        "x-langsmith-gateway-metadata":
          '{"outcome":"blocked","reason":"spend_limit"}',
      },
    });

    expect(run.extra?.metadata?.ls_gateway_info).toEqual({
      outcome: "blocked",
      reason: "spend_limit",
    });
  });

  it("captures metadata from a promise without replacing it", async () => {
    const run = createRun();
    const result = Promise.resolve({
      headers: new Headers({
        "X-LangSmith-Gateway-Metadata": '{"outcome":"success"}',
      }),
    });

    await withRunTree(run, async () => {
      captureGatewayResponseMetadata(result, run);
      await result;
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(run.extra?.metadata?.ls_gateway_info).toEqual({
      outcome: "success",
    });
  });

  it("never throws for unusual SDK response objects", () => {
    const run = createRun();
    const throwingResponse = Object.defineProperty({}, "headers", {
      get() {
        throw new Error("broken response getter");
      },
    });

    expect(() =>
      addGatewayResponseMetadata(run, throwingResponse),
    ).not.toThrow();
    expect(() =>
      captureGatewayResponseMetadata(throwingResponse, run),
    ).not.toThrow();
  });

  it("ignores malformed metadata", () => {
    const run = createRun();

    addGatewayResponseMetadata(
      run,
      new Headers({ "X-LangSmith-Gateway-Metadata": "not-json" }),
    );

    expect(run.extra?.metadata?.ls_gateway_info).toBeUndefined();
  });
});
