/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable import/no-extraneous-dependencies */
import { jest } from "@jest/globals";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { Client } from "../../index.js";

type ClientParams = Exclude<ConstructorParameters<typeof Client>[0], undefined>;
export const mockClient = (config?: Omit<ClientParams, "autoBatchTracing">) => {
  const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    text: () => Promise.resolve(""),
    json: () => Promise.resolve({}),
  } as Response);

  const client = new Client({
    ...config,
    apiKey: "MOCK",
    autoBatchTracing: false,
    fetchImplementation: mockFetch,
  });

  const callSpy = mockFetch;

  const langChainTracer = new LangChainTracer({
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore Overriden client
    client,
  });

  return { client, callSpy, langChainTracer };
};
