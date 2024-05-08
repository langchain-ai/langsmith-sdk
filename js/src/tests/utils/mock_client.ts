// eslint-disable-next-line import/no-extraneous-dependencies
import { jest } from "@jest/globals";
import { Client } from "../../index.js";

export const mockClient = () => {
  const client = new Client({ autoBatchTracing: false });
  const callSpy = jest
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  return { client, callSpy };
};
