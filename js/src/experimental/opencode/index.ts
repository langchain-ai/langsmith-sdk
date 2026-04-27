// import type { Plugin } from "@opencode-ai/plugin";
import { OpenCodeSessionTracer } from "./tracer.js";

type Plugin = (ctx: any) => any;

export const LangSmithPlugin: Plugin = async (ctx) => {
  const tracer = new OpenCodeSessionTracer();

  async function getSessionHistory(sessionID: string) {
    const past = await ctx.client.session.messages({
      path: { id: sessionID },
    });
    if (past.error) throw past.error;
    return past.data;
  }

  return {
    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input.sessionID;
      if (!sessionID) return;

      await tracer.handleSessionLoad(sessionID, getSessionHistory);
      await tracer.handleSystem(input, output);
    },
    event: async (input) => {
      const sessionID =
        "sessionID" in input.event.properties &&
        typeof input.event.properties.sessionID === "string"
          ? input.event.properties.sessionID
          : undefined;

      if (!sessionID) return;

      await tracer.handleSessionLoad(sessionID, getSessionHistory);
      await tracer.handleEvent(input);
    },
  };
};
