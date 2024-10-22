export async function gatherIterator<T>(
  i: AsyncIterable<T> | Promise<AsyncIterable<T>>
): Promise<Array<T>> {
  const out: T[] = [];
  for await (const item of await i) out.push(item);
  return out;
}
