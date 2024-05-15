import { RunTree, RunnableConfigLike } from "../run_trees.js";

interface AsyncStorageLike {
  getStore: () => RunTree | undefined;

  run: (context: RunTree | undefined, fn: () => void) => void;
}

export const TraceableLocalStorageContext = (() => {
  let storage: AsyncStorageLike;

  return {
    register: (value: AsyncStorageLike) => {
      storage ??= value;
      return storage;
    },
    get storage() {
      return storage;
    },
  };
})();

/**
 * Return the current run tree from within a traceable-wrapped function.
 * Will throw an error if called outside of a traceable function.
 *
 * @returns The run tree for the given context.
 */
export const getCurrentRunTree = () => {
  if (!TraceableLocalStorageContext.storage) {
    throw new Error("Could not find the traceable storage context");
  }

  const runTree = TraceableLocalStorageContext.storage.getStore();
  if (runTree === undefined) {
    throw new Error(
      [
        "Could not get the current run tree.",
        "",
        "Please make sure you are calling this method within a traceable function.",
      ].join("\n")
    );
  }

  return runTree;
};

export const ROOT = Symbol.for("langsmith:traceable:root");

type SmartPromise<T> = T extends AsyncGenerator
  ? T
  : T extends Promise<unknown>
  ? T
  : Promise<T>;

type WrapArgReturnPair<Pair> = Pair extends [
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  infer Args extends any[],
  infer Return
]
  ? Args extends [RunTree, ...infer RestArgs]
    ? {
        (
          runTree: RunTree | typeof ROOT,
          ...args: RestArgs
        ): SmartPromise<Return>;
        (config: RunnableConfigLike, ...args: RestArgs): SmartPromise<Return>;
      }
    : {
        (...args: Args): SmartPromise<Return>;
        (runTree: RunTree, ...rest: Args): SmartPromise<Return>;
        (config: RunnableConfigLike, ...args: Args): SmartPromise<Return>;
      }
  : never;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UnionToIntersection<U> = (U extends any ? (x: U) => void : never) extends (
  x: infer I
) => void
  ? I
  : never;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type TraceableFunction<Func extends (...args: any[]) => any> =
  // function overloads are represented as intersections rather than unions
  // matches the behavior introduced in https://github.com/microsoft/TypeScript/pull/54448
  Func extends {
    (...args: infer A1): infer R1;
    (...args: infer A2): infer R2;
    (...args: infer A3): infer R3;
    (...args: infer A4): infer R4;
    (...args: infer A5): infer R5;
  }
    ? UnionToIntersection<
        WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3] | [A4, R4] | [A5, R5]>
      >
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
        (...args: infer A3): infer R3;
        (...args: infer A4): infer R4;
      }
    ? UnionToIntersection<
        WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3] | [A4, R4]>
      >
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
        (...args: infer A3): infer R3;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1] | [A2, R2] | [A3, R3]>>
    : Func extends {
        (...args: infer A1): infer R1;
        (...args: infer A2): infer R2;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1] | [A2, R2]>>
    : Func extends {
        (...args: infer A1): infer R1;
      }
    ? UnionToIntersection<WrapArgReturnPair<[A1, R1]>>
    : never;

export function isTraceableFunction(
  x: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): x is TraceableFunction<any> {
  return typeof x === "function" && "langsmith:traceable" in x;
}

function isKVMap(x: unknown): x is Record<string, unknown> {
  if (typeof x !== "object" || x == null) {
    return false;
  }

  const prototype = Object.getPrototypeOf(x);
  return (
    (prototype === null ||
      prototype === Object.prototype ||
      Object.getPrototypeOf(prototype) === null) &&
    !(Symbol.toStringTag in x) &&
    !(Symbol.iterator in x)
  );
}
