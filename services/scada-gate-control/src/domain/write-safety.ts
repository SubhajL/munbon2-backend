/**
 * Write-safety predicate from the spec's "Write Safety / Before write" list.
 * Pure decision function — the API layer calls this before ANY Modbus write.
 *
 * Check order (and therefore deny-reason precedence) follows the spec exactly:
 *   1. authenticated  2. role allows command  3. data not stale/offline
 *   4. confirmed from UI  5. target value in {1,2,3,4}
 */
import { isGateLevel, type GateLevel } from './gate-level';
import { isWritableQuality, type Quality } from './quality';

export type Role = 'viewer' | 'operator' | 'admin';

export type WriteDenyReason =
  | 'not_authenticated'
  | 'role_forbidden'
  | 'data_stale'
  | 'data_offline'
  | 'data_unavailable'
  | 'not_confirmed'
  | 'invalid_target';

export type WriteSafetyResult =
  | { readonly allowed: true }
  | { readonly allowed: false; readonly reason: WriteDenyReason };

/**
 * Gate-level result carries the validated GateLevel on success so callers can
 * build the actuation plan without re-validating or casting the raw number.
 */
export type GateLevelWriteSafetyResult =
  | { readonly allowed: true; readonly target: GateLevel }
  | { readonly allowed: false; readonly reason: WriteDenyReason };

export type CommandWriteContext = {
  readonly authenticated: boolean;
  readonly role: Role;
  readonly quality: Quality;
  readonly confirmed: boolean;
};

/** Deny shape is shared by both result types, so `deny` works for either return. */
type DenyResult = { readonly allowed: false; readonly reason: WriteDenyReason };

const ALLOW: WriteSafetyResult = { allowed: true };
const deny = (reason: WriteDenyReason): DenyResult => ({ allowed: false, reason });

/** Viewer is read-only; Operator and Admin may issue commands (spec roles table). */
export function canCommand(role: Role): boolean {
  return role === 'operator' || role === 'admin';
}

function qualityDenyReason(quality: Quality): WriteDenyReason | null {
  if (isWritableQuality(quality)) return null;
  switch (quality) {
    case 'stale':
      return 'data_stale';
    case 'offline':
      return 'data_offline';
    default:
      return 'data_unavailable';
  }
}

/** Checks shared by every command type (gate level and horn). */
function evaluateCommonWriteSafety(ctx: CommandWriteContext): WriteSafetyResult {
  if (!ctx.authenticated) return deny('not_authenticated');
  if (!canCommand(ctx.role)) return deny('role_forbidden');
  const qualityReason = qualityDenyReason(ctx.quality);
  if (qualityReason) return deny(qualityReason);
  if (!ctx.confirmed) return deny('not_confirmed');
  return ALLOW;
}

export function evaluateGateLevelWriteSafety(
  ctx: CommandWriteContext & { readonly targetValue: number },
): GateLevelWriteSafetyResult {
  const common = evaluateCommonWriteSafety(ctx);
  if (!common.allowed) return common;
  if (!isGateLevel(ctx.targetValue)) return deny('invalid_target');
  return { allowed: true, target: ctx.targetValue };
}

/** Horn has no target value; otherwise identical safety rules (no confirmation bit at Modbus level, but UI must still confirm). */
export function evaluateHornWriteSafety(ctx: CommandWriteContext): WriteSafetyResult {
  return evaluateCommonWriteSafety(ctx);
}
