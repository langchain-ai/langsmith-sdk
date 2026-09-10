import { jest } from "@jest/globals";
import { OpenAI } from "openai";
import { wrapOpenAI } from "../wrappers/openai.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

test.each([200, 404])(
  "responses.create is traced but retrieval with status %i is not",
  async (status) => {
    const response = {
      id: "resp_test",
      object: "response",
      status: "completed",
      model: "gpt-5-nano",
      output: [
        {
          id: "msg_test",
          type: "message",
          role: "assistant",
          status: "completed",
          content: [{ type: "output_text", text: "4", annotations: [] }],
        },
      ],
      usage: { input_tokens: 10, output_tokens: 2, total_tokens: 12 },
    };
    const error = {
      type: "invalid_request_error",
      message: "Response with id 'resp_test' not found.",
    };
    const openaiFetch = jest
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(response))
      .mockResolvedValueOnce(
        Response.json(status === 200 ? response : { error }, { status }),
      );
    const { client, callSpy } = mockClient();
    const openai = wrapOpenAI(
      new OpenAI({
        apiKey: "MOCK",
        baseURL: "https://openai.example.test/v1",
        fetch: openaiFetch,
        maxRetries: 0,
      }),
      { client, tracingEnabled: true },
    );
    const params = {
      model: "gpt-5-nano",
      input: "What is 2+2?",
      store: true,
      metadata: { request_key: "request_value" },
    };

    const created = await openai.responses.create(params);
    expect(created).toMatchObject(response);
    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(tree.nodes).toEqual(["ChatOpenAI:0"]);
    expect(tree.data["ChatOpenAI:0"]).toMatchObject({
      run_type: "llm",
      inputs: params,
      extra: {
        metadata: { request_key: "request_value", ls_model_name: params.model },
      },
      outputs: {
        id: response.id,
        usage_metadata: response.usage,
      },
    });
    const createCallCount = callSpy.mock.calls.length;

    const retrieved = openai.responses.retrieve(created.id);
    if (status === 200) {
      await expect(retrieved).resolves.toMatchObject(response);
    } else {
      await expect(retrieved).rejects.toMatchObject({ status, error });
    }
    await client.awaitPendingTraceBatches();
    expect(callSpy.mock.calls.length).toBe(createCallCount);
    expect(openaiFetch).toHaveBeenCalledTimes(2);
    expect(openaiFetch).toHaveBeenNthCalledWith(
      1,
      "https://openai.example.test/v1/responses",
      expect.objectContaining({ method: "POST", body: JSON.stringify(params) }),
    );
    expect(openaiFetch).toHaveBeenNthCalledWith(
      2,
      `https://openai.example.test/v1/responses/${created.id}`,
      expect.objectContaining({ method: "GET" }),
    );
  },
);
