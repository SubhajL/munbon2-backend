/**
 * Command service — the single server-side path that actuates the gate/horn.
 * It always: (1) evaluates the Slice-1 safety-gated planner against the latest
 * snapshot, (2) on allow, hands the writes to the GateActuator which performs
 * them + a read-back ATOMICALLY (serialized against polls and other commands),
 * (3) records an audit entry for EVERY attempt (rejected / error / ok), with
 * the actually-attempted raw writes on partial failure, (4) reports whether the
 * command is still pending (device not yet at target).
 */
import type { ModbusWrite } from '../domain/command';
import { planGateLevelCommand, planHornCommand } from '../domain/plan';
import type { WriteDenyReason } from '../domain/write-safety';
import type { GateActuator } from '../state/gate-controller';
import type { GateSnapshot } from '../state/store';
import type { AuditCommandType, AuditRepository, AuditResult, AuditWrite } from '../audit/types';
import type { AuthenticatedUser } from '../api/auth';

export type CommandServiceDeps = {
  readonly actuator: GateActuator;
  readonly audit: AuditRepository;
  readonly now: () => number;
  readonly endpoint: { readonly host: string; readonly port: number; readonly unitId: number };
  readonly site: { readonly gateId: string; readonly name: string };
};

export type CommandOutcome =
  | { readonly status: 'accepted'; readonly pending: boolean; readonly snapshot: GateSnapshot }
  | {
      readonly status: 'rejected';
      readonly reason: WriteDenyReason;
      readonly snapshot: GateSnapshot;
    }
  | { readonly status: 'error'; readonly error: string; readonly snapshot: GateSnapshot };

function toAuditWrites(writes: readonly ModbusWrite[]): AuditWrite[] {
  return writes.map((write) => ({ address: write.address, value: write.value }));
}

export class CommandService {
  constructor(private readonly deps: CommandServiceDeps) {}

  async commandGateLevel(
    user: AuthenticatedUser,
    targetValue: number,
    confirmed: boolean,
  ): Promise<CommandOutcome> {
    const snapshot = this.deps.actuator.snapshot();
    const plan = planGateLevelCommand({
      authenticated: true,
      role: user.role,
      quality: snapshot.connection,
      confirmed,
      targetValue,
    });
    if (!plan.allowed) {
      await this.recordAudit(user, 'command-level', targetValue, [], 'rejected', null);
      return { status: 'rejected', reason: plan.reason, snapshot };
    }
    return this.execute(
      user,
      'command-level',
      targetValue,
      plan.writes,
      (after) => after.gateLevel.value?.level === targetValue,
    );
  }

  async commandHorn(
    user: AuthenticatedUser,
    enabled: boolean,
    confirmed: boolean,
  ): Promise<CommandOutcome> {
    const snapshot = this.deps.actuator.snapshot();
    const plan = planHornCommand({
      authenticated: true,
      role: user.role,
      quality: snapshot.connection,
      confirmed,
      enabled,
    });
    if (!plan.allowed) {
      await this.recordAudit(user, 'horn', enabled, [], 'rejected', null);
      return { status: 'rejected', reason: plan.reason, snapshot };
    }
    return this.execute(
      user,
      'horn',
      enabled,
      plan.writes,
      (after) => after.horn.value?.on === enabled,
    );
  }

  private async execute(
    user: AuthenticatedUser,
    commandType: AuditCommandType,
    target: number | boolean,
    writes: readonly ModbusWrite[],
    isSettled: (after: GateSnapshot) => boolean,
  ): Promise<CommandOutcome> {
    // Operator-authenticated actuation is the ONLY reachable write path today, so the
    // provenance is a hardcoded 'operator'. A future machine-authority write path MUST NOT be
    // routed through this method (it would inherit this literal and mis-attribute its writes
    // as operator, keeping the shadow tripwire dark) — it must carry its own provenance.
    const execution = await this.deps.actuator.executeWrites(writes, 'operator');
    if (execution.failed) {
      const attempted = [...execution.succeeded, execution.failed.write];
      await this.recordAudit(
        user,
        commandType,
        target,
        toAuditWrites(attempted),
        'error',
        execution.failed.error,
      );
      return { status: 'error', error: execution.failed.error, snapshot: execution.snapshot };
    }
    await this.recordAudit(
      user,
      commandType,
      target,
      toAuditWrites(execution.succeeded),
      'ok',
      null,
    );
    return {
      status: 'accepted',
      pending: !isSettled(execution.snapshot),
      snapshot: execution.snapshot,
    };
  }

  private async recordAudit(
    user: AuthenticatedUser,
    commandType: AuditCommandType,
    requestedTarget: number | boolean,
    writes: AuditWrite[],
    result: AuditResult,
    error: string | null,
  ): Promise<void> {
    await this.deps.audit.record({
      timestamp: new Date(this.deps.now()).toISOString(),
      userId: user.userId,
      userRole: user.role,
      gateId: this.deps.site.gateId,
      gateName: this.deps.site.name,
      commandType,
      requestedTarget,
      modbusHost: this.deps.endpoint.host,
      modbusPort: this.deps.endpoint.port,
      unitId: this.deps.endpoint.unitId,
      writes,
      result,
      error,
    });
  }
}
