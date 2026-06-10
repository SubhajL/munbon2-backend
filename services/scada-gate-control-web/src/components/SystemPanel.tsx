import { AlertTriangle } from "lucide-react";
import type { ConnectionSummary as Summary } from "@/lib/status";
import { ConnectionSummary } from "./ConnectionSummary";

export type SystemPanelProps = {
  summary: Summary;
  error?: string | null;
};

/** Floating operational overlay: system title + connection health summary. */
export function SystemPanel({ summary, error }: SystemPanelProps) {
  return (
    <section
      className="w-[340px] rounded-2xl border border-border bg-surface/80 p-4 shadow-lg backdrop-blur"
      aria-label="แผงสถานะระบบ (System status panel)"
    >
      <h1 className="text-base font-bold leading-tight text-fg">
        ระบบควบคุมประตูระบายน้ำ มูลบน เฟส 2
      </h1>
      <p className="mb-3 text-xs text-fg-muted">
        RID Munbon Phase 2 — Gate Control
      </p>
      {error ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-offline/60 bg-offline/10 p-2 text-xs text-fg"
          style={{ borderColor: "var(--color-offline)" }}
        >
          <AlertTriangle
            aria-hidden
            className="mt-0.5 size-4 shrink-0"
            style={{ color: "var(--color-offline)" }}
          />
          <span>
            เชื่อมต่อ API ไม่ได้ (Cannot reach the gate API). {error}.
            กำลังลองใหม่อัตโนมัติ (retrying automatically).
          </span>
        </div>
      ) : (
        <ConnectionSummary summary={summary} />
      )}
    </section>
  );
}
