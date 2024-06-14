import { StringNodeRule, createAnonymizer } from "../anonymizer/index.js";
import { v4 as uuid } from "uuid";

const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}/g;
const UUID_REGEX =
  /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g;

describe("replacer", () => {
  const replacer = (text: string) =>
    text.replace(EMAIL_REGEX, "[email address]").replace(UUID_REGEX, "[uuid]");

  test("object", () => {
    expect(
      createAnonymizer(replacer)({
        message: "Hello, this is my email: hello@example.com",
        metadata: uuid(),
      })
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(
      createAnonymizer(replacer)(["human", "hello@example.com"])
    ).toEqual(["human", "[email address]"]);
  });

  test("string", () => {
    expect(createAnonymizer(replacer)("hello@example.com")).toEqual(
      "[email address]"
    );
  });
});

describe("declared", () => {
  const replacers: StringNodeRule[] = [
    { pattern: EMAIL_REGEX, replace: "[email address]" },
    { pattern: UUID_REGEX, replace: "[uuid]" },
  ];

  test("object", () => {
    expect(
      createAnonymizer(replacers)({
        message: "Hello, this is my email: hello@example.com",
        metadata: uuid(),
      })
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(
      createAnonymizer(replacers)(["human", "hello@example.com"])
    ).toEqual(["human", "[email address]"]);
  });

  test("string", () => {
    expect(createAnonymizer(replacers)("hello@example.com")).toEqual(
      "[email address]"
    );
  });
});
