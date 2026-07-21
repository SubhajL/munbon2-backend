"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useState, type FormEvent } from "react";
import type {
  ControlAuthorityMutation,
} from "@/lib/control-authority-api";
import type { MutationAction } from "@/lib/control-authority-proxy";

export type AuthorityActionSubmission = {
  mutation: ControlAuthorityMutation;
  confirmation: string;
  stepUpCode: string | undefined;
};

type Props = {
  open: boolean;
  action: MutationAction;
  planId: string;
  planVersion: number;
  grantId?: string;
  pending: boolean;
  error?: string | null;
  onSubmit: (submission: AuthorityActionSubmission) => void;
  onCancel: () => void;
};

const requiresStepUp = (action: MutationAction): boolean =>
  action !== "hold" && action !== "revoke";

const usesApprovalRefs = (action: MutationAction): boolean =>
  action === "approve-shadow" || action === "activate" || action === "grant";

const usesGrantEvidence = (action: MutationAction): boolean =>
  action === "grant" || action === "renew";

const splitRefs = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

function expectedPhrase(
  action: MutationAction,
  planId: string,
  planVersion: number,
  grantId: string | undefined,
): string {
  if (action === "renew" || action === "revoke") {
    return `${action.toUpperCase()} ${grantId ?? "missing-grant"}`;
  }
  return `${action.toUpperCase()} ${planId} v${planVersion}`;
}

export function AuthorityActionDialog({
  open,
  action,
  planId,
  planVersion,
  grantId,
  pending,
  error,
  onSubmit,
  onCancel,
}: Props) {
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [stepUpCode, setStepUpCode] = useState("");
  const [approvalRefs, setApprovalRefs] = useState("");
  const [evidenceRefs, setEvidenceRefs] = useState("");
  const [shadowHash, setShadowHash] = useState("");
  const [holdHash, setHoldHash] = useState("");
  const [rollbackHash, setRollbackHash] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const phrase = expectedPhrase(action, planId, planVersion, grantId);
  const stepUpRequired = requiresStepUp(action);
  const approvalRequired = usesApprovalRefs(action);
  const evidenceRequired = usesGrantEvidence(action);
  const valid =
    confirmation === phrase &&
    reason.trim().length > 0 &&
    (!stepUpRequired || /^[0-9]{6}$/.test(stepUpCode)) &&
    (!approvalRequired || splitRefs(approvalRefs).length > 0) &&
    (!evidenceRequired ||
      (splitRefs(evidenceRefs).length > 0 &&
        [shadowHash, holdHash, rollbackHash].every((hash) =>
          /^[0-9a-f]{64}$/.test(hash),
        ) &&
        expiresAt.length > 0));

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (!valid) return;
    const mutation: ControlAuthorityMutation = {
      action,
      planId,
      planVersion,
      reason: reason.trim(),
      ...(grantId ? { grantId } : {}),
      ...(approvalRequired ? { approvalRefs: splitRefs(approvalRefs) } : {}),
      ...(evidenceRequired
        ? {
            evidenceRefs: splitRefs(evidenceRefs),
            shadowEvidenceSha256: shadowHash,
            holdDrillEvidenceSha256: holdHash,
            rollbackDrillEvidenceSha256: rollbackHash,
            expiresAt: new Date(expiresAt).toISOString(),
          }
        : {}),
    };
    onSubmit({
      mutation,
      confirmation,
      stepUpCode: stepUpRequired ? stepUpCode : undefined,
    });
  };

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 max-h-[90vh] w-[min(94vw,540px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
          <Dialog.Title className="text-base font-bold">
            Confirm {action}
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-fg-muted">
            This action is bound to plan {planId} v{planVersion}. Type the exact
            phrase shown below.
          </Dialog.Description>
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <label className="block text-sm">
              Reason
              <textarea
                aria-label="Reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="mt-1 block w-full rounded border border-border bg-surface-low p-2"
              />
            </label>
            {approvalRequired && (
              <label className="block text-sm">
                Evidence references
                <input
                  aria-label="Evidence references"
                  value={approvalRefs}
                  onChange={(event) => setApprovalRefs(event.target.value)}
                  placeholder="RID-approval-118, ticket-77"
                  className="mt-1 block w-full rounded border border-border bg-surface-low p-2"
                />
              </label>
            )}
            {evidenceRequired && (
              <fieldset className="space-y-2 rounded border border-border p-3">
                <legend className="text-sm font-medium">Drill evidence</legend>
                <label className="block text-sm">
                  Evidence manifest references
                  <input
                    aria-label="Evidence manifest references"
                    value={evidenceRefs}
                    onChange={(event) => setEvidenceRefs(event.target.value)}
                    className="mt-1 block w-full rounded border border-border bg-surface-low p-2"
                  />
                </label>
                {[
                  ["Shadow evidence SHA-256", shadowHash, setShadowHash],
                  ["Hold drill SHA-256", holdHash, setHoldHash],
                  ["Rollback drill SHA-256", rollbackHash, setRollbackHash],
                ].map(([label, value, setter]) => (
                  <label key={label as string} className="block text-sm">
                    {label as string}
                    <input
                      aria-label={label as string}
                      value={value as string}
                      onChange={(event) =>
                        (setter as (value: string) => void)(event.target.value)
                      }
                      className="mt-1 block w-full rounded border border-border bg-surface-low p-2 font-mono text-xs"
                    />
                  </label>
                ))}
                <label className="block text-sm">
                  Authority expiry
                  <input
                    aria-label="Authority expiry"
                    type="datetime-local"
                    value={expiresAt}
                    onChange={(event) => setExpiresAt(event.target.value)}
                    className="mt-1 block w-full rounded border border-border bg-surface-low p-2"
                  />
                </label>
              </fieldset>
            )}
            {stepUpRequired && (
              <label className="block text-sm">
                TOTP code
                <input
                  aria-label="TOTP code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={stepUpCode}
                  onChange={(event) => setStepUpCode(event.target.value)}
                  className="mt-1 block w-full rounded border border-border bg-surface-low p-2"
                />
              </label>
            )}
            <div className="rounded border border-border bg-surface-low p-2 font-mono text-xs">
              {phrase}
            </div>
            <label className="block text-sm">
              Exact confirmation
              <input
                aria-label="Exact confirmation"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                className="mt-1 block w-full rounded border border-border bg-surface-low p-2 font-mono text-xs"
              />
            </label>
            {error && (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={onCancel}
                disabled={pending}
                className="rounded border border-border px-3 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!valid || pending}
                className="rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-fg disabled:opacity-50"
              >
                {pending ? "Working…" : `Confirm ${action}`}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
