import { describe, expect, test } from "vitest";
import { isSafeNext } from "./redirect";

describe("isSafeNext", () => {
  test.each<[string, boolean]>([
    ["/", true],
    ["/gates/waste-way", true],
    ["/gates/waste-way?tab=1#log", true],
    ["//evil.com", false],
    ["/\\evil.com", false],
    ["/%2F%2Fevil.com", false],
    ["/%2f%2fevil.com", false],
    ["/%5Cevil.com", false],
    ["https:/evil.com", false],
    ["http://evil.com", false],
    ["javascript:alert(1)", false],
    [" /evil.com", false],
    ["", false],
  ])("%j -> %s", (next, expected) => {
    expect(isSafeNext(next)).toBe(expected);
  });
});
