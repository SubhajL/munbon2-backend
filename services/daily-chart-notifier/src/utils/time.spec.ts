import { describe, expect, test } from "vitest";
import {
  bangkokNow,
  twentyFourHoursAgo,
  formatBangkokTime,
  formatForEmailSubject,
} from "./time";

describe("bangkokNow", () => {
  test("returns a Date object", () => {
    const result = bangkokNow();
    expect(result).toBeInstanceOf(Date);
  });
});

describe("twentyFourHoursAgo", () => {
  test("returns date 24 hours before input", () => {
    const now = new Date("2024-01-15T13:00:00Z");
    const result = twentyFourHoursAgo(now);

    const diffMs = now.getTime() - result.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    expect(diffHours).toBe(24);
  });
});

describe("formatBangkokTime", () => {
  test("formats date with default format", () => {
    const date = new Date("2024-01-15T06:30:00Z");
    const result = formatBangkokTime(date);

    expect(result).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
  });

  test("formats date with custom format", () => {
    const date = new Date("2024-01-15T06:30:00Z");
    const result = formatBangkokTime(date, "dd/MM/yyyy");

    expect(result).toMatch(/^\d{2}\/\d{2}\/\d{4}$/);
  });
});

describe("formatForEmailSubject", () => {
  test("returns date in yyyy-MM-dd format", () => {
    const date = new Date("2024-01-15T06:30:00Z");
    const result = formatForEmailSubject(date);

    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
