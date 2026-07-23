const warnedMessages: Record<string, boolean> = {};

export function warnOnce(
  message: string,
  options?: { type?: string; code?: string },
): void {
  const key = options?.code ?? message;
  if (!warnedMessages[key]) {
    warnedMessages[key] = true;
    if (
      options?.type &&
      typeof process !== "undefined" &&
      typeof process.emitWarning === "function"
    ) {
      process.emitWarning(message, { type: options.type, code: options.code });
    } else if (options?.type && options?.code) {
      console.warn(`${options.type} [${options.code}]: ${message}`);
    } else {
      console.warn(message);
    }
  }
}
