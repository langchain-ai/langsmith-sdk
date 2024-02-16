import type { OpenAI } from "openai";
import { traceable } from "./traceable.js";

export const wrapOpenAI = (client: OpenAI): OpenAI => {
  // @ts-expect-error Promise<APIPromise<...>> != APIPromise<...>
  client.chat.completions.create = traceable(
    client.chat.completions.create.bind(client.chat.completions),
    { name: "ChatOpenAI", run_type: "llm" }
  );

  // @ts-expect-error Promise<APIPromise<...>> != APIPromise<...>
  client.completions.create = traceable(
    client.completions.create.bind(client.completions),
    { name: "OpenAI", run_type: "llm" }
  );

  return client;
};
