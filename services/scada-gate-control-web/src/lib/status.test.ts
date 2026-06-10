import { describe, expect, test } from "vitest";
import {
  connectionLabel,
  STATUS_COLOR_VAR,
  summarizeConnections,
} from "./status";
import type { Quality, SiteSummary } from "./api";

const site = (markerColor: SiteSummary["markerColor"]): SiteSummary => ({
  id: "g",
  name: "g",
  connection: "ok",
  markerColor,
  lastUpdated: null,
});

describe("summarizeConnections", () => {
  test("counts zero for an empty list", () => {
    expect(summarizeConnections([])).toEqual({
      online: 0,
      stale: 0,
      offline: 0,
    });
  });

  test("buckets each marker colour into the right counter", () => {
    expect(
      summarizeConnections([
        site("green"),
        site("green"),
        site("yellow"),
        site("red"),
      ]),
    ).toEqual({ online: 2, stale: 1, offline: 1 });
  });
});

describe("STATUS_COLOR_VAR", () => {
  test("maps each marker colour to its design token", () => {
    expect(STATUS_COLOR_VAR).toEqual({
      green: "var(--color-online)",
      yellow: "var(--color-stale)",
      red: "var(--color-offline)",
    });
  });
});

describe("connectionLabel", () => {
  test.each<[Quality, string, string]>([
    ["ok", "ออนไลน์", "Online"],
    ["stale", "ข้อมูลเก่า", "Stale"],
    ["offline", "ออฟไลน์", "Offline"],
    ["modbus_exception", "ข้อผิดพลาด Modbus", "Modbus error"],
    ["decode_error", "ถอดรหัสค่าไม่ได้", "Decode error"],
  ])("%s -> %s / %s", (quality, th, en) => {
    expect(connectionLabel(quality)).toEqual({ th, en });
  });
});
