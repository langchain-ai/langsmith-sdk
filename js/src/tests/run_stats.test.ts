import { describe, expect, it } from "@jest/globals";
import { Client } from "../client.js";

describe("getRunStats", () => {
  it("throws when neither projectNames nor projectIds is provided", async () => {
    const client = new Client({ apiKey: "test", apiUrl: "http://localhost" });
    await expect(client.getRunStats({})).rejects.toThrow(
      "projectNames or projectIds",
    );
  });

  it("throws when projectIds is an empty array", async () => {
    const client = new Client({ apiKey: "test", apiUrl: "http://localhost" });
    await expect(client.getRunStats({ projectIds: [] })).rejects.toThrow(
      "projectNames or projectIds",
    );
  });
});
