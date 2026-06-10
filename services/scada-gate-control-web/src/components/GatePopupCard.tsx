import {
  ChevronRight,
  DoorClosed,
  Gauge,
  Siren,
  type LucideIcon,
} from "lucide-react";
import type { GateStatus } from "@/lib/api";
import { formatClockTime } from "@/lib/format";

function Row({
  icon: Icon,
  labelTh,
  labelEn,
  value,
}: {
  icon: LucideIcon;
  labelTh: string;
  labelEn: string;
  value: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-xs">
      <span className="flex items-center gap-1.5 text-fg-muted">
        <Icon aria-hidden className="size-3.5" />
        {labelTh} ({labelEn})
      </span>
      <span className="text-right font-medium tabular-nums text-fg">
        {value}
      </span>
    </div>
  );
}

export type GatePopupCardProps = {
  status: GateStatus | null;
  loading?: boolean;
  onDetail: () => void;
};

/** Popup body shown when a gate marker is clicked. */
export function GatePopupCard({
  status,
  loading,
  onDetail,
}: GatePopupCardProps) {
  const gateLevel = status?.gateLevel.value;
  const door = status?.doorSw.value;
  const horn = status?.horn.value;

  return (
    <div data-testid="gate-popup" className="w-[280px]">
      <h2 className="mb-1 text-sm font-bold text-fg">
        {status?.name ?? "Waste Way"}
      </h2>
      {loading && !status ? (
        <p role="status" className="py-2 text-xs text-fg-muted">
          กำลังโหลด… (Loading)
        </p>
      ) : (
        <div className="divide-y divide-border/60">
          <Row
            icon={Gauge}
            labelTh="ระดับประตูน้ำ"
            labelEn="Gate_Level"
            value={
              gateLevel
                ? `${gateLevel.thaiLabel} — ${gateLevel.flowRate} ลบ.ม./วินาที`
                : "—"
            }
          />
          <Row
            icon={DoorClosed}
            labelTh="ประตูตู้ควบคุม"
            labelEn="Door_SW"
            value={door ? door.thaiLabel : "—"}
          />
          <Row
            icon={Siren}
            labelTh="ไซเรน"
            labelEn="Horn"
            value={horn ? horn.thaiLabel : "—"}
          />
        </div>
      )}
      <p className="mt-2 text-[11px] text-fg-muted">
        Last updated:{" "}
        <span className="tabular-nums">
          {formatClockTime(status?.lastUpdated ?? null)}
        </span>
      </p>
      <button
        type="button"
        onClick={onDetail}
        className="mt-2 flex w-full items-center justify-center gap-1 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-fg transition-colors hover:bg-primary-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        ดูรายละเอียด / ควบคุม
        <ChevronRight aria-hidden className="size-3.5" />
      </button>
    </div>
  );
}
