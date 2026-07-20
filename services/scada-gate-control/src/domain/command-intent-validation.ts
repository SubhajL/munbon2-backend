/**
 * PR 6.2 — pure, I/O-free validation of a machine-boundary CommandIntent against
 * the 6.1a device-capability snapshot, plus receipt assembly. No plan DB, no
 * approved-artifact anchor, and — critically — NO reference to any actuator,
 * transport, or Modbus write. The route (6.2b) Ajv-validates the body first
 * (`schema_invalid` → 422), then calls `validateCommandIntent` on a schema-valid
 * intent and persists the resulting receipt idempotently.
 *
 * Reason codes 6.2 enforces standalone (first failure wins, in this order):
 *   freshness_failed     — intent pins a capability release/hash SCADA no longer serves
 *   capability_mismatch  — gate absent, or device_id/adapter_gate_id disagree with the binding
 *   target_invalid       — (position, level) is not an EXACT member of the device's targets
 *   not_before_violation — malformed or inverted/empty temporal window (see below)
 *   deadline_expired     — now is past the deadline (evaluated once, frozen into the receipt)
 * `lineage_mismatch` is RESERVED for PR 6.1b (the approved-artifact lineage anchor); the frozen
 * 6.0 schema already validates lineage STRUCTURE, so 6.2 emits no lineage_mismatch.
 */
import { type ValidateFunction } from 'ajv/dist/2020';
import canonicalize from 'canonicalize';

import { COMMAND_INTENT_SCHEMA_V1 } from './command-intent.schema';
import { newMachineBoundaryAjv } from './machine-boundary-ajv';
import { VALIDATION_RECEIPT_SCHEMA_V1 } from './validation-receipt.schema';
import type {
  CommandIntent,
  DeviceCapability,
  DeviceCapabilitySnapshot,
  ValidationReceipt,
  ValidationRejectionReason,
} from './machine-boundary';

export type ValidationVerdict =
  | { readonly status: 'validation_accepted'; readonly reason_code: null }
  | { readonly status: 'validation_rejected'; readonly reason_code: ValidationRejectionReason };

const ACCEPTED: ValidationVerdict = { status: 'validation_accepted', reason_code: null };
const reject = (reason: ValidationRejectionReason): ValidationVerdict => ({
  status: 'validation_rejected',
  reason_code: reason,
});

/**
 * Own-property lookup only: the intent's canonical_gate_id is untrusted `[!-~]+`, so a
 * bare `capabilities[gateId]` with `__proto__`/`constructor` would read a phantom
 * (truthy) object off the prototype chain. Non-own keys => the gate is absent.
 */
function ownCapability(
  snapshot: DeviceCapabilitySnapshot,
  gateId: string,
): DeviceCapability | undefined {
  const caps = snapshot.capabilities as Readonly<Record<string, DeviceCapability>>;
  return Object.prototype.hasOwnProperty.call(caps, gateId) ? caps[gateId] : undefined;
}

/** Compare two positions the way the Scheduler's `capability_member` does: by canonical
 * number STRING (RFC-8785), never float `===`, so quantizer membership agrees cross-language.
 * Both inputs are schema-constrained finite numbers; the explicit finiteness guard fails
 * CLOSED (rather than letting canonicalize throw inside Array.find) if one ever isn't. */
function positionsEqual(a: number, b: number): boolean {
  if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
  return canonicalize(a) === canonicalize(b);
}

/**
 * Parse a contract UtcInstant STRICTLY. The 6.0 `utc_instant` regex is pattern-only and
 * permits calendar-impossible days (e.g. 2026-02-30, 2026-04-31, Feb-29 in a non-leap
 * year), which `Date.parse` silently ROLLS OVER to a real-but-different instant. We
 * round-trip the parsed epoch back through UTC getters and return null on any mismatch,
 * so a nonexistent date can never be reinterpreted as a valid window. (Python's
 * `datetime.fromisoformat` raises on these, so this also keeps the two sides in agreement.)
 */
export function parseUtcInstant(instant: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?Z$/.exec(instant);
  if (!m) return null;
  const ms = Date.parse(instant);
  if (Number.isNaN(ms)) return null;
  const d = new Date(ms);
  const [, y, mo, day, h, mi, s] = m;
  if (
    d.getUTCFullYear() !== Number(y) ||
    d.getUTCMonth() + 1 !== Number(mo) ||
    d.getUTCDate() !== Number(day) ||
    d.getUTCHours() !== Number(h) ||
    d.getUTCMinutes() !== Number(mi) ||
    d.getUTCSeconds() !== Number(s)
  ) {
    return null; // calendar-impossible instant that Date.parse rolled over
  }
  return ms;
}

/**
 * Pure verdict function. Assumes `intent` already passed the command-intent v1 Ajv
 * schema (the route enforces that and returns `schema_invalid`/422 otherwise).
 */
export function validateCommandIntent(
  intent: CommandIntent,
  snapshot: DeviceCapabilitySnapshot,
  nowMs: number,
): ValidationVerdict {
  // 1. Freshness: the intent must be compiled against the release SCADA currently serves.
  if (
    intent.capability_release_id !== snapshot.capability_release_id ||
    intent.capability_hash !== snapshot.capability_hash
  ) {
    return reject('freshness_failed');
  }

  // 2. Capability: the gate must be machine-capable and bound to the exact device/adapter.
  const capability = ownCapability(snapshot, intent.canonical_gate_id);
  if (
    capability === undefined ||
    capability.device_id !== intent.device_id ||
    capability.adapter_gate_id !== intent.adapter_gate_id
  ) {
    return reject('capability_mismatch');
  }

  // 3. Target: (position, level) must be an EXACT member of the device's quantizer.
  const member = capability.targets.find((t) =>
    positionsEqual(t.target_position_m, intent.target_position_m),
  );
  if (member === undefined || member.target_level !== intent.target_level) {
    return reject('target_invalid');
  }

  // 4. Window (field-only, no clock). `not_before_violation` covers BOTH a malformed
  //    instant (parseUtcInstant returns null for a calendar-impossible date the regex
  //    let through — fail closed, never silently rolled over) AND an inverted/empty
  //    window (not_before >= deadline). Note it is NOT "the window has not opened":
  //    a future-dated intent is legitimately accepted (validation never actuates).
  const notBeforeMs = parseUtcInstant(intent.not_before);
  const deadlineMs = parseUtcInstant(intent.deadline);
  if (notBeforeMs === null || deadlineMs === null || !(notBeforeMs < deadlineMs)) {
    return reject('not_before_violation');
  }

  // 5. Deadline: evaluated once at first validation and frozen into the durable receipt.
  if (deadlineMs < nowMs) {
    return reject('deadline_expired');
  }

  return ACCEPTED;
}

let cachedIntentValidator: ValidateFunction | null = null;
export function compileCommandIntentValidator(): ValidateFunction {
  if (cachedIntentValidator) return cachedIntentValidator;
  cachedIntentValidator = newMachineBoundaryAjv().compile(
    COMMAND_INTENT_SCHEMA_V1 as unknown as Record<string, unknown>,
  );
  return cachedIntentValidator;
}

let cachedReceiptValidator: ValidateFunction | null = null;
function receiptValidator(): ValidateFunction {
  if (cachedReceiptValidator) return cachedReceiptValidator;
  cachedReceiptValidator = newMachineBoundaryAjv().compile(
    VALIDATION_RECEIPT_SCHEMA_V1 as unknown as Record<string, unknown>,
  );
  return cachedReceiptValidator;
}

/** Format epoch ms as a contract UtcInstant (`YYYY-MM-DDTHH:mm:ss.sssZ`, 24 chars). */
export function formatUtcInstant(epochMs: number): string {
  return new Date(epochMs).toISOString();
}

/**
 * Assemble the ValidationReceipt from the intent + verdict, then SELF-CHECK it against
 * the embedded receipt v1 schema. A failed self-check is an internal bug (never a
 * caller error) and throws so the route maps it to 503 — SCADA never emits a
 * contract-violating receipt.
 */
export function buildValidationReceipt(params: {
  readonly intent: CommandIntent;
  readonly verdict: ValidationVerdict;
  readonly receiptId: string;
  readonly validatedAt: string;
  readonly contentHash: string;
}): ValidationReceipt {
  const { intent, verdict, receiptId, validatedAt, contentHash } = params;
  const receipt = {
    schema_version: 1,
    receipt_id: receiptId,
    intent_id: intent.intent_id,
    correlation_id: intent.correlation_id,
    request_id: intent.request_id,
    idempotency_key: intent.idempotency_key,
    intent_content_hash: contentHash,
    // The receipt records the capability_hash the intent WAS VALIDATED AGAINST (the
    // intent's own pin) — on freshness_failed that is the stale hash, deliberately, so
    // the receipt says exactly which release the scheduler compiled against.
    capability_hash: intent.capability_hash,
    status: verdict.status,
    validated_at: validatedAt,
    reason_code: verdict.reason_code,
  } as unknown as ValidationReceipt;
  if (!receiptValidator()(receipt)) {
    throw new Error('assembled validation receipt violates the validation-receipt v1 contract');
  }
  return receipt;
}
