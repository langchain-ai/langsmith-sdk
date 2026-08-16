const warnedMessages: Record<string, boolean> = {};

/**
 * Clear the warn-once record so a later call warns again.
 *
 * Test-only. `warnedMessages` is module-global and never otherwise reset, so
 * without this a test asserting "warning X was (not) emitted" depends on whether
 * an earlier test in the same file already consumed X.
 *
 * @internal
 */
export function _resetWarnedMessages(): void {
  for (const key of Object.keys(warnedMessages)) {
    delete warnedMessages[key];
  }
}

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
