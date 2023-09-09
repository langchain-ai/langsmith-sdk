import { LangChainBaseMessage } from "../schemas.js";

export function isLangChainMessage(
  message?: any
): message is LangChainBaseMessage {
  return typeof message?._getType === "function";
}

export function convertLangChainMessageToExample(
  message: LangChainBaseMessage
) {
  return { type: message._getType(), data: { content: message.content } };
}
