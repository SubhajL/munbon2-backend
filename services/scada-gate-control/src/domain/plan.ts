/**
 * Safety-gated command planner — the ONLY sanctioned way to turn an operator
 * intent into Modbus writes. It evaluates write-safety first and only then
 * builds the actuation plan, so no caller can reach the raw `build*Command`
 * functions without passing the spec's pre-write checklist.
 *
 * The API/transport slices MUST call these, never `build*Command` directly.
 */
import { buildGateLevelCommand, buildHornCommand, type ModbusWrite } from './command';
import {
  evaluateGateLevelWriteSafety,
  evaluateHornWriteSafety,
  type CommandWriteContext,
  type WriteDenyReason,
} from './write-safety';

export type CommandPlan =
  | { readonly allowed: true; readonly writes: ModbusWrite[] }
  | { readonly allowed: false; readonly reason: WriteDenyReason };

export function planGateLevelCommand(
  ctx: CommandWriteContext & { readonly targetValue: number },
): CommandPlan {
  const safety = evaluateGateLevelWriteSafety(ctx);
  if (!safety.allowed) return safety;
  return { allowed: true, writes: buildGateLevelCommand(safety.target) };
}

export function planHornCommand(
  ctx: CommandWriteContext & { readonly enabled: boolean },
): CommandPlan {
  const safety = evaluateHornWriteSafety(ctx);
  if (!safety.allowed) return safety;
  return { allowed: true, writes: buildHornCommand(ctx.enabled) };
}
