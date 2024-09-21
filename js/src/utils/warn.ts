const warnedMessages: Record<string, boolean> = {};

export function warnOnce(message: string): void {
  if (!warnedMessages[message]) {
    console.warn(message);
    warnedMessages[message] = true;
  }
}
