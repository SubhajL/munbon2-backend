import type { LucideIcon } from "lucide-react";

export type StatusTone = "online" | "stale" | "offline";

const TONE_VAR: Record<StatusTone, string> = {
  online: "var(--color-online)",
  stale: "var(--color-stale)",
  offline: "var(--color-offline)",
};

export type StatusPillProps = {
  tone: StatusTone;
  icon: LucideIcon;
  labelTh: string;
  labelEn: string;
  count: number;
};

/**
 * Glanceable status counter. Conveys state with colour PLUS a shape (dot) and
 * an icon — never colour alone (WCAG 2.2 / colour-blind safe).
 */
export function StatusPill({
  tone,
  icon: Icon,
  labelTh,
  labelEn,
  count,
}: StatusPillProps) {
  const color = TONE_VAR[tone];
  return (
    <span
      data-testid={`status-pill-${tone}`}
      className="inline-flex items-center gap-1.5 rounded-full border bg-surface-high/60 px-2.5 py-1 text-xs"
      style={{ borderColor: color }}
    >
      <span
        aria-hidden
        className="size-2 rounded-full"
        style={{ background: color }}
      />
      <Icon aria-hidden className="size-3.5" style={{ color }} />
      <span className="text-fg-muted">
        {labelTh} ({labelEn})
      </span>
      <span className="font-semibold tabular-nums text-fg">{count}</span>
    </span>
  );
}
