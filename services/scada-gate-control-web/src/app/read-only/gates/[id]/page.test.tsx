import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import type { GateStatus } from "@/lib/api";

const h = vi.hoisted(() => ({
  authenticated: true,
  gateId: "gate 7/ฝาย",
  fetcher: undefined as undefined | (() => Promise<unknown>),
  getGateStatus: vi.fn(),
  pollState: {
    data: null as GateStatus | null,
    error: null as Error | null,
    loading: false,
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: h.gateId }),
}));
vi.mock("@/components/RequireAuth", () => ({
  RequireAuth: ({ children }: { children: React.ReactNode }) =>
    h.authenticated ? <>{children}</> : <div role="status">access denied</div>,
}));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({
    getToken: () => "viewer-token",
    refresh: async () => null,
  }),
}));
vi.mock("@/hooks/usePolling", () => ({
  usePolling: (fetcher: () => Promise<unknown>) => {
    h.fetcher = fetcher;
    return h.pollState;
  },
}));
vi.mock("@/lib/read-only-gate-status", () => ({
  createReadOnlyGateStatusClient: () => ({
    getGateStatus: h.getGateStatus,
  }),
}));

import ReadOnlyGatePage from "./page";

const gateStatus: GateStatus = {
  id: "gate 7/ฝาย",
  name: "Gate Seven",
  endpoint: { host: "127.0.0.1", port: 502, unitId: 7 },
  connection: "ok",
  markerColor: "green",
  lastUpdated: "2026-07-24T00:00:00Z",
  lastError: null,
  gateLevel: {
    raw: 2,
    value: {
      level: 2,
      thaiLabel: "ระดับ 2",
      technicalLabel: "Level 2",
      flowRate: 1.5,
    },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  doorSw: {
    raw: 1,
    value: { closed: true, thaiLabel: "ปิด" },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  horn: {
    raw: 0,
    value: { on: false, thaiLabel: "ปิด" },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  gateCf: {
    raw: 1,
    value: { confirmed: true },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
};

beforeEach(() => {
  h.authenticated = true;
  h.gateId = "gate 7/ฝาย";
  h.fetcher = undefined;
  h.getGateStatus.mockReset();
  h.getGateStatus.mockResolvedValue(gateStatus);
  h.pollState = { data: gateStatus, error: null, loading: false };
});

describe("read-only gate page", () => {
  test("forwards the exact route ID to the GET-only status client", async () => {
    render(<ReadOnlyGatePage />);

    await expect(h.fetcher?.()).resolves.toEqual(gateStatus);
    expect(h.getGateStatus).toHaveBeenCalledWith("gate 7/ฝาย");
  });

  test("renders observed status without gate-command controls", () => {
    const { container } = render(<ReadOnlyGatePage />);
    const main = container.querySelector("main");

    expect(main).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Gate Seven" })).toBeVisible();
    expect(screen.getByText("ระดับ 2")).toBeVisible();
    expect(screen.getByText("โหมดดูอย่างเดียว (Read only)")).toBeVisible();
    expect(
      main?.querySelectorAll(
        "button, form, input, select, textarea, [role='button']",
      ),
    ).toHaveLength(0);
  });

  test("renders an unavailable state with no actuation fallback", () => {
    h.pollState = {
      data: null,
      error: new Error("upstream offline"),
      loading: false,
    };

    const { container } = render(<ReadOnlyGatePage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "ไม่สามารถอ่านสถานะประตูน้ำได้",
    );
    expect(
      container.querySelectorAll(
        "button, form, input, select, textarea, [role='button']",
      ),
    ).toHaveLength(0);
  });

  test("hides the last successful status as soon as polling fails", () => {
    h.pollState = {
      data: gateStatus,
      error: new Error("upstream offline"),
      loading: false,
    };

    render(<ReadOnlyGatePage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "ไม่สามารถอ่านสถานะประตูน้ำได้",
    );
    expect(screen.queryByText("ระดับ 2")).not.toBeInTheDocument();
    expect(screen.queryByText("gate 7/ฝาย")).not.toBeInTheDocument();
  });

  test("does not initialize status access while signed out", () => {
    h.authenticated = false;

    render(<ReadOnlyGatePage />);

    expect(screen.getByRole("status")).toHaveTextContent("access denied");
    expect(h.fetcher).toBeUndefined();
    expect(h.getGateStatus).not.toHaveBeenCalled();
  });

  test("contains only allowlisted imports and no command-capable UI or clients", async () => {
    const source = await readFile(
      resolve(process.cwd(), "src/app/read-only/gates/[id]/page.tsx"),
      "utf8",
    );
    const importSources = Array.from(
      source.matchAll(/from\s+["']([^"']+)["']/g),
      (match) => match[1],
    );

    expect(importSources).toEqual([
      "react",
      "next/navigation",
      "@/components/AuthProvider",
      "@/components/GateDetailHeader",
      "@/components/RequireAuth",
      "@/hooks/usePolling",
      "@/lib/read-only-gate-status",
    ]);
    expect(source).not.toMatch(
      /createApiClient|ConfirmCommandModal|LevelSensors|SidePanel|commandLevel|commandHorn|control-authority/,
    );
  });
});
