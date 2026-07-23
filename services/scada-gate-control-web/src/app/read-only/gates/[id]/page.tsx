"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { GateDetailHeader } from "@/components/GateDetailHeader";
import { RequireAuth } from "@/components/RequireAuth";
import { usePolling } from "@/hooks/usePolling";
import { API_BASE } from "@/lib/config";
import { createReadOnlyGateStatusClient } from "@/lib/read-only-gate-status";

const POLL_MS = 3000;

export default function ReadOnlyGatePage() {
  return (
    <RequireAuth>
      <ReadOnlyGateContent />
    </RequireAuth>
  );
}

function ReadOnlyGateContent() {
  const { id: gateId } = useParams<{ id: string }>();
  const { getToken, refresh } = useAuth();
  const client = useMemo(
    () =>
      createReadOnlyGateStatusClient({
        baseUrl: API_BASE,
        getToken,
        onUnauthorized: refresh,
      }),
    [getToken, refresh],
  );
  const statusPoll = usePolling(
    () => client.getGateStatus(gateId),
    POLL_MS,
  );
  const status = statusPoll.data;

  return (
    <main className="flex min-h-dvh flex-col bg-surface-low">
      <GateDetailHeader
        name={status?.name ?? `Gate ${gateId}`}
        status={status}
      />

      <section className="mx-auto w-full max-w-4xl space-y-5 p-6">
        <div className="rounded-2xl border border-border bg-surface p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
            โหมดดูอย่างเดียว (Read only)
          </p>
          <p className="mt-2 text-sm text-fg-muted">
            หน้านี้แสดงข้อมูลสถานะเท่านั้น และไม่มีการสั่งงานอุปกรณ์
          </p>
        </div>

        {statusPoll.loading ? (
          <p
            className="rounded-2xl border border-border bg-surface p-5 text-sm text-fg-muted"
            role="status"
          >
            กำลังอ่านสถานะประตูน้ำ… (Loading gate status)
          </p>
        ) : null}

        {statusPoll.error ? (
          <p
            className="rounded-2xl border border-offline/50 bg-offline/10 p-5 text-sm text-fg"
            role="alert"
          >
            ไม่สามารถอ่านสถานะประตูน้ำได้ (Gate status unavailable)
          </p>
        ) : null}

        {status ? (
          <dl className="grid gap-4 rounded-2xl border border-border bg-surface p-5 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-fg-muted">รหัสประตูน้ำ (Gate ID)</dt>
              <dd className="mt-1 font-mono text-sm text-fg">{status.id}</dd>
            </div>
            <div>
              <dt className="text-xs text-fg-muted">
                ระดับประตูน้ำที่สังเกตได้
              </dt>
              <dd className="mt-1 text-sm text-fg">
                {status.gateLevel.value?.thaiLabel ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-fg-muted">
                ประตูตู้ควบคุม (Door_SW)
              </dt>
              <dd className="mt-1 text-sm text-fg">
                {status.doorSw.value?.thaiLabel ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-fg-muted">ไซเรนที่สังเกตได้ (Horn)</dt>
              <dd className="mt-1 text-sm text-fg">
                {status.horn.value?.thaiLabel ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-fg-muted">
                Gate_Level (raw observation)
              </dt>
              <dd className="mt-1 font-mono text-sm text-fg">
                {status.gateLevel.raw ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-fg-muted">
                Gate_CF (observed confirmation)
              </dt>
              <dd className="mt-1 text-sm text-fg">
                {status.gateCf.value
                  ? status.gateCf.value.confirmed
                    ? "ยืนยันแล้ว (confirmed)"
                    : "ยังไม่ยืนยัน (not confirmed)"
                  : "—"}
              </dd>
            </div>
          </dl>
        ) : null}
      </section>
    </main>
  );
}
