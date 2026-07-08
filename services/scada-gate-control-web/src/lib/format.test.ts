import { describe, expect, test } from "vitest";
import { formatClockTime } from "./format";

describe("formatClockTime", () => {
  test("formats an ISO instant as HH:MM:SS in Asia/Bangkok (UTC+7)", () => {
    expect(formatClockTime("2024-01-01T00:00:00.000Z")).toBe("07:00:00");
  });

  test.each([null, undefined, "", "not-a-date"])(
    "returns an em dash for %p",
    (value) => {
      expect(formatClockTime(value)).toBe("—");
    },
  );
});
