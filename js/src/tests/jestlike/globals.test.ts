import {
  _logTestFeedback,
  evaluatorLogFeedbackPromises,
} from "../../utils/jestlike/globals.js";

describe("Jest-like feedback logging", () => {
  afterEach(() => {
    evaluatorLogFeedbackPromises.clear();
  });

  test("supplies the test experiment ID and root run start time", async () => {
    const calls: any[][] = [];
    const startTime = 1784651696789;
    const client = {
      logEvaluationFeedback: async (...args: any[]) => {
        calls.push(args);
        return [];
      },
    };

    _logTestFeedback({
      exampleId: "00000000-0000-0000-0000-000000000001",
      feedback: { key: "pass", score: true },
      context: {
        enableTestTracking: true,
        createdAt: new Date().toISOString(),
        client: client as any,
        project: {
          id: "00000000-0000-0000-0000-000000000004",
        } as any,
        suiteUuid: "00000000-0000-0000-0000-000000000002",
        suiteName: "test-suite",
      },
      runTree: {
        id: "00000000-0000-0000-0000-000000000003",
        start_time: startTime,
      } as any,
      client: client as any,
    });
    await Promise.all(evaluatorLogFeedbackPromises);

    expect(calls).toHaveLength(1);
    expect(calls[0][1]).toEqual(
      expect.objectContaining({ start_time: startTime }),
    );
    expect(calls[0][3]).toBe("00000000-0000-0000-0000-000000000004");
  });
});
