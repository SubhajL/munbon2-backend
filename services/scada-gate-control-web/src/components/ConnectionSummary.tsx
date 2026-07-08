import { AlertTriangle, Radio, WifiOff } from "lucide-react";
import type { ConnectionSummary as Summary } from "@/lib/status";
import { StatusPill } from "./StatusPill";

export function ConnectionSummary({ summary }: { summary: Summary }) {
  return (
    <div
      className="flex flex-wrap gap-2"
      role="group"
      aria-label="สรุปสถานะการเชื่อมต่อ (Connection summary)"
    >
      <StatusPill
        tone="online"
        icon={Radio}
        labelTh="ออนไลน์"
        labelEn="Online"
        count={summary.online}
      />
      <StatusPill
        tone="stale"
        icon={AlertTriangle}
        labelTh="ข้อมูลเก่า"
        labelEn="Stale"
        count={summary.stale}
      />
      <StatusPill
        tone="offline"
        icon={WifiOff}
        labelTh="ออฟไลน์"
        labelEn="Offline"
        count={summary.offline}
      />
    </div>
  );
}
