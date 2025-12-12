import { RunTree, RunnableConfigLike } from "../run_trees.js";
import { ROOT } from "./traceable.js";
import { _LC_CONTEXT_VARIABLES_KEY } from "./constants.js";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SmartPromise<T> = T extends AsyncIterable<any>
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
        /** @deprecated Will be removed in 0.4 */
        (config: RunnableConfigLike, ...args: RestArgs): SmartPromise<Return>;
      }
    : {
        (...args: Args): SmartPromise<Return>;
        (runTree: RunTree | typeof ROOT, ...rest: Args): SmartPromise<Return>;
        /** @deprecated Will be removed in 0.4 */
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
  (Func extends {
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
    : never) & {
    // Other properties of Func
    [K in keyof Func]: Func[K];
  };

export type RunTreeLike = RunTree;

export type ContextPlaceholder = {
  [_LC_CONTEXT_VARIABLES_KEY]?: Record<string, unknown>;
};
