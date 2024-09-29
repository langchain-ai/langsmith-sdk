// eslint-disable-next-line import/no-extraneous-dependencies
import { jest } from "@jest/globals";
// eslint-disable-next-line import/no-extraneous-dependencies
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { Client } from "../../index.js";

type ClientParams = Exclude<ConstructorParameters<typeof Client>[0], undefined>;
export const mockClient = (config?: Omit<ClientParams, "autoBatchTracing">) => {
  const client = new Client({
    ...config,
    apiKey: "MOCK",
    autoBatchTracing: false,
  });
  const callSpy = jest
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const langChainTracer = new LangChainTracer({
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore Overriden client
    client,
  });

  return { client, callSpy, langChainTracer };
};
