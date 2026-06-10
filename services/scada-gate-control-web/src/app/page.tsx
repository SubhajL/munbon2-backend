"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { ApiError, createApiClient } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { summarizeConnections } from "@/lib/status";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import { SystemPanel } from "@/components/SystemPanel";
import { GatePopupCard } from "@/components/GatePopupCard";
import { API_BASE } from "@/lib/config";

// MapLibre touches `window`/WebGL, so load the map only on the client.
const MapView = dynamic(
  () => import("@/components/MapView").then((m) => m.MapView),
  {
    ssr: false,
  },
);

const POLL_MS = 3000;

function errorText(error: Error | null): string | null {
  if (!error) return null;
  return error instanceof ApiError ? `HTTP ${error.status}` : error.message;
}

export default function HomePage() {
  return (
    <RequireAuth>
      <HomeContent />
    </RequireAuth>
  );
}

function HomeContent() {
  const router = useRouter();
  const { getToken, refresh } = useAuth();
  const client = useMemo(
    () =>
      createApiClient({ baseUrl: API_BASE, getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const sitesPoll = usePolling(() => client.listSites(), POLL_MS);
  const statusPoll = usePolling(
    () => client.getGateStatus(selectedId ?? ""),
    POLL_MS,
    selectedId !== null,
  );

  const sites = sitesPoll.data ?? [];
  const summary = summarizeConnections(sites);

  return (
    <main className="relative h-dvh w-screen overflow-hidden">
      <MapView
        sites={sites}
        selectedId={selectedId}
        onSelect={setSelectedId}
        renderPopup={(site) => (
          <GatePopupCard
            status={statusPoll.data}
            loading={statusPoll.loading}
            onDetail={() => router.push(`/gates/${site.id}`)}
          />
        )}
      />

      <div className="pointer-events-none absolute inset-0 p-4">
        <div className="pointer-events-auto inline-block">
          <SystemPanel summary={summary} error={errorText(sitesPoll.error)} />
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 left-4">
        <ul className="pointer-events-auto flex gap-3 rounded-lg border border-border bg-surface/80 px-3 py-2 text-[11px] text-fg-muted backdrop-blur">
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: "var(--color-online)" }}
            />
            ออนไลน์ (Online)
          </li>
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: "var(--color-stale)" }}
            />
            ข้อมูลเก่า (Stale)
          </li>
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: "var(--color-offline)" }}
            />
            ออฟไลน์ (Offline)
          </li>
        </ul>
      </div>
    </main>
  );
}
