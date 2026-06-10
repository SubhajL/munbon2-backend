"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { createApiClient, type CommandResult, type GateLevel } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { canCommand as canCommandRole } from "@/lib/role";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import { GateDetailHeader } from "@/components/GateDetailHeader";
import { LevelSensors } from "@/components/LevelSensors";
import { SidePanel } from "@/components/SidePanel";
import { ConfirmCommandModal } from "@/components/ConfirmCommandModal";
import { API_BASE } from "@/lib/config";

const POLL_MS = 3000;

function resultMessage(result: CommandResult): string {
  if (result.status === "accepted") {
    return result.pending
      ? "สั่งงานแล้ว กำลังดำเนินการ… (pending)"
      : "สั่งงานสำเร็จ (accepted)";
  }
  if (result.status === "rejected")
    return `ถูกปฏิเสธ (rejected): ${result.reason}`;
  return `ผิดพลาด (error): ${result.error}`;
}

export default function GateDetailPage() {
  return (
    <RequireAuth>
      <GateDetailContent />
    </RequireAuth>
  );
}

function GateDetailContent() {
  const params = useParams<{ id: string }>();
  const gateId = params.id;
  const { session, getToken, refresh } = useAuth();
  const client = useMemo(
    () =>
      createApiClient({ baseUrl: API_BASE, getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );
  const mayCommand = canCommandRole(session?.user.role ?? "viewer");

  const statusPoll = usePolling(() => client.getGateStatus(gateId), POLL_MS);
  const status = statusPoll.data;
  const gateName = status?.name ?? "Waste Way";
  const currentLevel = (status?.gateLevel.value?.level ??
    null) as GateLevel | null;

  const [selectedLevel, setSelectedLevel] = useState<GateLevel | null>(null);
  const [commandPending, setCommandPending] = useState(false);
  const [hornPending, setHornPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function confirmLevel() {
    if (selectedLevel === null) return;
    setCommandPending(true);
    try {
      setMessage(
        resultMessage(await client.commandLevel(gateId, selectedLevel, true)),
      );
    } catch (error) {
      setMessage(`ผิดพลาด (error): ${(error as Error).message}`);
    } finally {
      setCommandPending(false);
      setSelectedLevel(null);
    }
  }

  async function commandHorn(enabled: boolean) {
    setHornPending(true);
    try {
      setMessage(
        resultMessage(await client.commandHorn(gateId, enabled, true)),
      );
    } catch (error) {
      setMessage(`ผิดพลาด (error): ${(error as Error).message}`);
    } finally {
      setHornPending(false);
    }
  }

  return (
    <main className="flex h-dvh flex-col">
      <GateDetailHeader name={gateName} status={status} />

      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        <section className="relative flex-1 overflow-hidden rounded-2xl border border-border bg-surface-low">
          <div
            className="absolute inset-0 opacity-15"
            style={{
              backgroundImage:
                "linear-gradient(var(--color-border) 1px, transparent 1px), linear-gradient(90deg, var(--color-border) 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />
          <span className="absolute bottom-3 left-3 text-xs text-fg-muted">
            ภาพประตูน้ำ (gate image — placeholder)
          </span>
          <p className="absolute left-3 top-3 text-[11px] text-fg-muted">
            คลิกขวาหรือคลิกระดับเพื่อสั่งงาน (right-click or click a level to
            command)
          </p>
          <div className="absolute right-4 top-1/2 w-[280px] -translate-y-1/2">
            <LevelSensors
              currentLevel={currentLevel}
              canCommand={mayCommand}
              onCommand={(level) => setSelectedLevel(level)}
            />
          </div>
        </section>

        <SidePanel
          status={status}
          canCommand={mayCommand}
          hornPending={hornPending}
          onHorn={commandHorn}
        />
      </div>

      {message ? (
        <div
          role="status"
          className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-lg border border-border bg-surface px-4 py-2 text-xs text-fg shadow-lg"
        >
          {message}
        </div>
      ) : null}

      <ConfirmCommandModal
        open={selectedLevel !== null}
        gateName={gateName}
        level={selectedLevel}
        pending={commandPending}
        onConfirm={confirmLevel}
        onCancel={() => setSelectedLevel(null)}
      />
    </main>
  );
}
