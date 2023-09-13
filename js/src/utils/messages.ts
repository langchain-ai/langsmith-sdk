import { LangChainBaseMessage } from "../schemas.js";

export function isLangChainMessage(
  message?: any
): message is LangChainBaseMessage {
  return typeof message?._getType === "function";
}

// Add index signature to data object
interface ConvertedData {
  content: string;
  [key: string]: any;
}

export function convertLangChainMessageToExample(
  message: LangChainBaseMessage
) {
  const converted: { type: string; data: ConvertedData } = {
    type: message._getType(),
    data: { content: message.content },
  };
  // Check for presence of keys in additional_kwargs
  if (
    message?.additional_kwargs &&
    Object.keys(message.additional_kwargs).length > 0
  ) {
    converted.data.additional_kwargs = { ...message.additional_kwargs };
  }
  return converted;
}
