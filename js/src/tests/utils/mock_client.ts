// eslint-disable-next-line import/no-extraneous-dependencies
import { jest } from "@jest/globals";
import { Client } from "../../index.js";

type ClientParams = Exclude<ConstructorParameters<typeof Client>[0], undefined>;
export const mockClient = (config?: Omit<ClientParams, "autoBatchTracing">) => {
  const client = new Client({ ...config, autoBatchTracing: false });
  const callSpy = jest
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  return { client, callSpy };
};
