'use client';

import { DoorClosed, Siren } from 'lucide-react';
import type { GateStatus } from '@/lib/api';

export type SidePanelProps = {
  status: GateStatus | null;
  canCommand: boolean;
  hornPending?: boolean;
  onHorn: (enabled: boolean) => void;
};

/** Right-hand control panel: Door_SW (status only), Horn controls, raw + endpoint. */
export function SidePanel({ status, canCommand, hornPending, onHorn }: SidePanelProps) {
  const door = status?.doorSw.value;
  const horn = status?.horn.value;
  const endpoint = status?.endpoint;

  return (
    <aside
      className="w-[320px] space-y-4 rounded-2xl border border-border bg-surface/80 p-4 backdrop-blur"
      aria-label="แผงควบคุม (Control panel)"
    >
      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-muted">
          สถานะประตูตู้ควบคุม (Door_SW)
        </h3>
        <div className="flex items-center gap-2 text-sm text-fg">
          <DoorClosed aria-hidden className="size-4" />
          {door ? door.thaiLabel : '—'}
          <span className="text-xs text-fg-muted">(status only · 1=ปิด 0=เปิด)</span>
        </div>
      </section>

      <section className="border-t border-border/60 pt-3">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-muted">
          ไซเรน (Horn)
        </h3>
        <div className="mb-2 flex items-center gap-2 text-sm text-fg">
          <Siren aria-hidden className="size-4" />
          {horn ? horn.thaiLabel : '—'}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!canCommand || hornPending}
            onClick={() => onHorn(true)}
            className="flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-opacity disabled:opacity-50"
            style={{ background: 'var(--color-stale)', color: '#472a00' }}
          >
            เปิดไซเรน
          </button>
          <button
            type="button"
            disabled={!canCommand || hornPending}
            onClick={() => onHorn(false)}
            className="flex-1 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-fg transition-colors hover:bg-surface-high disabled:opacity-50"
          >
            ปิดไซเรน
          </button>
        </div>
        {!canCommand ? (
          <p className="mt-1.5 text-[11px] text-fg-muted">โหมดดูอย่างเดียว (Viewer — read only)</p>
        ) : null}
      </section>

      <section className="space-y-1 border-t border-border/60 pt-3 text-xs">
        <div className="flex justify-between">
          <span className="text-fg-muted">Gate_Level (raw)</span>
          <span className="font-mono tabular-nums text-fg">{status?.gateLevel.raw ?? '—'}</span>
        </div>
        <div className="font-mono text-[11px] text-fg-muted">
          {endpoint ? `Modbus ${endpoint.host}:${endpoint.port}` : 'Modbus —'}
        </div>
        <div className="font-mono text-[11px] text-fg-muted">Unit ID: {endpoint?.unitId ?? '—'}</div>
      </section>
    </aside>
  );
}
