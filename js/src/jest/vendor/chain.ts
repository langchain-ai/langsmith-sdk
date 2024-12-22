/**
 * Adapted from https://github.com/mattphillips/jest-chain/blob/main/src/chain.js
 */
import { expect } from "@jest/globals";
import { gradedBy, SimpleEvaluator } from "./gradedBy.js";

class JestAssertionError extends Error {
  matcherResult: any;

  constructor(result: any, callsite: any) {
    super(
      typeof result.message === "function" ? result.message() : result.message
    );
    this.matcherResult = result;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, callsite);
    }
  }
}

const _wrapMatchers = (
  matchers: jest.Matchers<any>,
  evaluator: SimpleEvaluator,
  originalArgs: any[],
  staticPath: string[] = []
) => {
  return Object.keys(matchers)
    .filter((name) => typeof (matchers as any)[name] === "function")
    .map((name) => {
      const newMatcher = async (...args: any[]) => {
        try {
          const score = await gradedBy(originalArgs[0], evaluator);
          let result: any = expect(score);
          for (const pathEntry of staticPath) {
            result = result[pathEntry];
          }
          result = result[name](...args); // run matcher up to current state
          if (result && typeof result.then === "function") {
            return Object.assign(Promise.resolve(result), matchers);
          } else {
            return matchers;
          }
        } catch (error: any) {
          if (!error.matcherResult) {
            throw error;
          } else {
            throw new JestAssertionError(error.matcherResult, newMatcher);
          }
        }
      };
      return { [name]: newMatcher };
    });
};

const addGradedBy = (
  matchers: jest.Matchers<any>,
  originalArgs: any[],
  staticPath: string[] = []
) => {
  let spreadMatchers = { ...matchers };
  // Handle Bun, which uses a class
  if (Object.keys(matchers).length === 0) {
    const prototypeProps = Object.getOwnPropertyNames(
      Object.getPrototypeOf(matchers)
    );
    spreadMatchers = Object.fromEntries(
      prototypeProps.map((prop) => {
        try {
          return [prop, (matchers as any)[prop]];
        } catch (e) {
          // Ignore bizarre Bun bug
          return [];
        }
      })
    ) as any;
  }
  return Object.assign({}, matchers, {
    gradedBy: function (evaluator: SimpleEvaluator) {
      const mappedMatchers: any = _wrapMatchers(
        spreadMatchers,
        evaluator,
        originalArgs
      );
      // .not etc.
      const staticMatchers = Object.keys(spreadMatchers)
        .filter((name) => typeof (matchers as any)[name] !== "function")
        .map((name) => {
          return {
            [name]: Object.assign(
              {},
              ..._wrapMatchers(
                spreadMatchers,
                evaluator,
                originalArgs,
                staticPath.concat(name)
              )
            ),
          };
        });
      return Object.assign({}, ...mappedMatchers, ...staticMatchers);
    },
  });
};

export function wrapExpect(expect: any) {
  // proxy the expect function
  const expectProxy = Object.assign(
    (...args: any[]) => addGradedBy(expect(...args), args), // partially apply expect to get all matchers and chain them
    expect // clone additional properties on expect
  );

  return expectProxy;
}

(globalThis as any).expect = wrapExpect((globalThis as any).expect);
