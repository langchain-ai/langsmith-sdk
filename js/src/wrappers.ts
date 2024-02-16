import type { OpenAI } from "openai";
import type { Client } from "./index.js";
import { traceable } from "./traceable.js";

export const wrapOpenAI = (
  openai: OpenAI,
  options?: { client?: Client }
): OpenAI => {
  // @ts-expect-error Promise<APIPromise<...>> != APIPromise<...>
  openai.chat.completions.create = traceable(
    openai.chat.completions.create.bind(openai.chat.completions),
    Object.assign({ name: "ChatOpenAI", run_type: "llm" }, options?.client)
  );

  // @ts-expect-error Promise<APIPromise<...>> != APIPromise<...>
  openai.completions.create = traceable(
    openai.completions.create.bind(openai.completions),
    Object.assign({ name: "OpenAI", run_type: "llm" }, options?.client)
  );

  return openai;
};
