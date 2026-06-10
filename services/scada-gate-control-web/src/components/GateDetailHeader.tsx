'use client';

import Link from 'next/link';
import { AlertTriangle, ChevronLeft, Radio, WifiOff, type LucideIcon } from 'lucide-react';
import type { GateStatus, Quality } from '@/lib/api';
import { connectionLabel } from '@/lib/status';
import { formatClockTime } from '@/lib/format';

type Tone = 'online' | 'stale' | 'offline';

const TONE_META: Record<Tone, { icon: LucideIcon; varName: string }> = {
  online: { icon: Radio, varName: 'var(--color-online)' },
  stale: { icon: AlertTriangle, varName: 'var(--color-stale)' },
  offline: { icon: WifiOff, varName: 'var(--color-offline)' },
};

function toneOf(quality: Quality): Tone {
  if (quality === 'ok') return 'online';
  if (quality === 'stale') return 'stale';
  return 'offline';
}

export function ConnectionBadge({ quality }: { quality: Quality }) {
  const tone = toneOf(quality);
  const { icon: Icon, varName } = TONE_META[tone];
  const label = connectionLabel(quality);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
      style={{ borderColor: varName }}
    >
      <span aria-hidden className="size-2 rounded-full" style={{ background: varName }} />
      <Icon aria-hidden className="size-3.5" style={{ color: varName }} />
      {label.th} ({label.en})
    </span>
  );
}

export function GateDetailHeader({ name, status }: { name: string; status: GateStatus | null }) {
  return (
    <header className="flex items-center gap-3 border-b border-border bg-surface/80 px-4 py-3 backdrop-blur">
      <Link
        href="/"
        aria-label="ย้อนกลับ (Back)"
        className="flex items-center gap-1 rounded-lg border border-border px-2 py-1.5 text-xs text-fg transition-colors hover:bg-surface-high focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <ChevronLeft aria-hidden className="size-4" />
        ย้อนกลับ
      </Link>
      <h1 className="text-base font-bold text-fg">{name}</h1>
      {status ? <ConnectionBadge quality={status.connection} /> : null}
      <span className="ml-auto text-xs text-fg-muted">
        Last updated: <span className="tabular-nums">{formatClockTime(status?.lastUpdated ?? null)}</span>
      </span>
    </header>
  );
}
