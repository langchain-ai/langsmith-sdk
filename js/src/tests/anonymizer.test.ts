import { StringNodeRule, replaceSensitiveData } from "../anonymizer/index.js";
import { v4 as uuid } from "uuid";

const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}/g;
const UUID_REGEX =
  /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g;

describe("replacer", () => {
  const replacer = (text: string) =>
    text.replace(EMAIL_REGEX, "[email address]").replace(UUID_REGEX, "[uuid]");

  test("object", () => {
    expect(
      replaceSensitiveData(
        {
          message: "Hello, this is my email: hello@example.com",
          metadata: uuid(),
        },
        replacer
      )
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(
      replaceSensitiveData(["human", "hello@example.com"], replacer)
    ).toEqual(["human", "[email address]"]);
  });

  test("string", () => {
    expect(replaceSensitiveData("hello@example.com", replacer)).toEqual(
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
      replaceSensitiveData(
        {
          message: "Hello, this is my email: hello@example.com",
          metadata: uuid(),
        },
        replacers
      )
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(
      replaceSensitiveData(["human", "hello@example.com"], replacers)
    ).toEqual(["human", "[email address]"]);
  });

  test("string", () => {
    expect(replaceSensitiveData("hello@example.com", replacers)).toEqual(
      "[email address]"
    );
  });
});
