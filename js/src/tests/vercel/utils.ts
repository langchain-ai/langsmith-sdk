import { MockLanguageModelV2 } from "ai/test";

export class MockMultiStepLanguageModelV2 extends MockLanguageModelV2 {
  generateStep = -1;
  streamStep = -1;

  constructor(...args: ConstructorParameters<typeof MockLanguageModelV2>) {
    super(...args);

    const oldDoGenerate = this.doGenerate;
    this.doGenerate = async (...args) => {
      this.generateStep += 1;
      return await oldDoGenerate(...args);
    };

    const oldDoStream = this.doStream;
    this.doStream = async (...args) => {
      this.streamStep += 1;
      return await oldDoStream(...args);
    };
  }
}

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
