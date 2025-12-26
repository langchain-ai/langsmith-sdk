/* eslint-disable import/no-extraneous-dependencies */
import { LanguageModelV2 } from "@ai-sdk/provider";

export class ExecutionOrderSame {
  $$typeof = Symbol.for("jest.asymmetricMatcher");

  private expectedNs: string;
  private expectedDepth: number;

  constructor(depth: number, ns: string) {
    this.expectedDepth = depth;
    this.expectedNs = ns;
  }

  asymmetricMatch(other: unknown) {
    // eslint-disable-next-line no-instanceof/no-instanceof
    if (!(typeof other === "string" || other instanceof String)) {
      return false;
    }

    const segments = other.split(".");
    if (segments.length !== this.expectedDepth) return false;

    const last = segments.at(-1);
    if (!last) return false;

    const nanoseconds = last.split("Z").at(0)?.slice(-3);
    return nanoseconds === this.expectedNs;
  }

  toString() {
    return "ExecutionOrderSame";
  }

  getExpectedType() {
    return "string";
  }

  toAsymmetricMatcher() {
    return `ExecutionOrderSame<${this.expectedDepth}, ${this.expectedNs}>`;
  }
}

// Test code from https://github.com/vercel/ai/blob/main/packages/ai/src/test/mock-language-model-v2.ts
// It seems the old models are no longer exported

export function notImplemented(): never {
  throw new Error("Not implemented");
}

export class MockLanguageModelV2 implements LanguageModelV2 {
  readonly specificationVersion = "v2";

  private _supportedUrls: () => LanguageModelV2["supportedUrls"];

  readonly provider: LanguageModelV2["provider"];
  readonly modelId: LanguageModelV2["modelId"];

  doGenerate: LanguageModelV2["doGenerate"];
  doStream: LanguageModelV2["doStream"];

  doGenerateCalls: Parameters<LanguageModelV2["doGenerate"]>[0][] = [];
  doStreamCalls: Parameters<LanguageModelV2["doStream"]>[0][] = [];

  constructor({
    provider = "mock-provider",
    modelId = "mock-model-id",
    supportedUrls = {},
    doGenerate = notImplemented,
    doStream = notImplemented,
  }: {
    provider?: LanguageModelV2["provider"];
    modelId?: LanguageModelV2["modelId"];
    supportedUrls?:
      | LanguageModelV2["supportedUrls"]
      | (() => LanguageModelV2["supportedUrls"]);
    doGenerate?:
      | LanguageModelV2["doGenerate"]
      | Awaited<ReturnType<LanguageModelV2["doGenerate"]>>
      | Awaited<ReturnType<LanguageModelV2["doGenerate"]>>[];
    doStream?:
      | LanguageModelV2["doStream"]
      | Awaited<ReturnType<LanguageModelV2["doStream"]>>
      | Awaited<ReturnType<LanguageModelV2["doStream"]>>[];
  } = {}) {
    this.provider = provider;
    this.modelId = modelId;
    this.doGenerate = async (options) => {
      this.doGenerateCalls.push(options);

      if (typeof doGenerate === "function") {
        return doGenerate(options);
      } else if (Array.isArray(doGenerate)) {
        return doGenerate[this.doGenerateCalls.length];
      } else {
        return doGenerate;
      }
    };
    this.doStream = async (options) => {
      this.doStreamCalls.push(options);

      if (typeof doStream === "function") {
        return doStream(options);
      } else if (Array.isArray(doStream)) {
        return doStream[this.doStreamCalls.length];
      } else {
        return doStream;
      }
    };
    this._supportedUrls =
      typeof supportedUrls === "function"
        ? supportedUrls
        : async () => supportedUrls;
  }

  get supportedUrls() {
    return this._supportedUrls();
  }
}
