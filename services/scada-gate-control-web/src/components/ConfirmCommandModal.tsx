"use client";

import * as Dialog from "@radix-ui/react-dialog";
import type { GateLevel } from "@/lib/api";
import { confirmBody, confirmTechnical } from "@/lib/control";

export type ConfirmCommandModalProps = {
  open: boolean;
  gateName: string;
  level: GateLevel | null;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Confirmation gate for a level command, with the raw Modbus details shown. */
export function ConfirmCommandModal({
  open,
  gateName,
  level,
  pending,
  onConfirm,
  onCancel,
}: ConfirmCommandModalProps) {
  const technical = level !== null ? confirmTechnical(level) : null;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border bg-surface p-5 shadow-2xl focus:outline-none">
          {level !== null && technical ? (
            <>
              <Dialog.Title className="text-base font-bold text-fg">
                ยืนยันการสั่งงานประตูน้ำ
              </Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-fg">
                {confirmBody(gateName, level)}
              </Dialog.Description>
              <div className="mt-3 rounded-lg border border-border bg-surface-low p-3 font-mono text-xs text-fg-muted">
                <div>{technical.opGate}</div>
                <div>{technical.gateCf}</div>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onCancel}
                  className="rounded-lg border border-border px-3 py-2 text-xs font-semibold text-fg transition-colors hover:bg-surface-high focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  ยกเลิก
                </button>
                <button
                  type="button"
                  onClick={onConfirm}
                  disabled={pending}
                  className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-fg transition-colors hover:bg-primary-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50"
                >
                  {pending ? "กำลังสั่งงาน…" : "ยืนยันการสั่งงาน"}
                </button>
              </div>
            </>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
