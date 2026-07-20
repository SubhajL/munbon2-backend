import 'dotenv/config';
import { Pool } from 'pg';
import { loadConfig, type AppConfig } from './config';
import { ModbusSerialTransport } from './transport/modbus-serial-transport';
import { GateController } from './state/gate-controller';
import { JwtTokenVerifier } from './api/auth';
import { buildServer } from './api/server';
import { loadDeviceCapabilitySnapshot } from './domain/device-registry';
import { loadApprovedLineageAnchor } from './domain/approved-field-artifact';
import { CommandService } from './services/command-service';
import { InMemoryAuditRepository } from './audit/memory-repository';
import { PostgresAuditRepository } from './audit/pg-repository';
import type { AuditRepository } from './audit/types';
import { InMemoryCommandIntentReceiptRepository } from './command-intents/memory-repository';
import { PostgresCommandIntentReceiptRepository } from './command-intents/pg-repository';
import type { CommandIntentReceiptRepository } from './command-intents/types';
import { SchedulerServiceTokenVerifier, type ServiceTokenVerifier } from './api/service-auth';
import { createScadaMetrics } from './metrics/registry';
import { logger } from './utils/logger';

type Storage = {
  readonly audit: AuditRepository;
  readonly receipts: CommandIntentReceiptRepository;
};

/**
 * Durable audit + validation-receipt stores share one Postgres pool. Both are mandatory
 * unless explicitly opted out for development (ALLOW_IN_MEMORY_AUDIT).
 */
async function resolveStorage(config: AppConfig): Promise<Storage> {
  if (config.databaseUrl) {
    const pool = new Pool({ connectionString: config.databaseUrl });
    // An idle pooled client dropping (DB restart / network blip) emits 'error' on the
    // Pool; with no listener Node rethrows it as an uncaught exception and kills the
    // process — which also runs the Modbus poll loop + operator gate control. Log and
    // survive: only the receipt/audit path degrades (fails closed), not gate control.
    pool.on('error', (err) => logger.error({ err: err.message }, 'audit/receipt pg pool error'));
    const audit = new PostgresAuditRepository(pool);
    const receipts = new PostgresCommandIntentReceiptRepository(pool);
    // Independent DDLs — provision both in parallel (max round-trip, not sum).
    await Promise.all([audit.ensureSchema(), receipts.ensureSchema()]);
    return { audit, receipts };
  }
  if (!config.allowInMemoryAudit) {
    throw new Error(
      'DATABASE_URL is required for durable audit + validation-receipt logs; set ALLOW_IN_MEMORY_AUDIT=true only for development',
    );
  }
  logger.warn('using NON-PERSISTENT in-memory audit + receipt stores (ALLOW_IN_MEMORY_AUDIT=true)');
  return {
    audit: new InMemoryAuditRepository(),
    receipts: new InMemoryCommandIntentReceiptRepository(),
  };
}

async function main(): Promise<void> {
  const config = loadConfig();
  const endpoint = {
    host: config.modbus.host,
    port: config.modbus.port,
    unitId: config.modbus.unitId,
  };

  // One per-process metrics registry, shared by the write chokepoint and the /metrics route.
  const metrics = createScadaMetrics();

  const transport = new ModbusSerialTransport(config.modbus);
  const controller = new GateController({
    transport,
    thresholds: config.freshness,
    intervalMs: config.modbus.pollIntervalMs,
    writeMeter: metrics,
    onError: (error) =>
      logger.warn({ err: error instanceof Error ? error.message : String(error) }, 'poll error'),
  });

  const { audit, receipts } = await resolveStorage(config);

  const commandService = new CommandService({
    actuator: controller,
    audit,
    now: () => Date.now(),
    endpoint,
    site: config.site,
  });

  // Fail-fast at startup on a broken registry (empty when unset = zero gates).
  const deviceCapabilities = loadDeviceCapabilitySnapshot();

  // PR 6.1b — the approved lineage anchor for the reserved `lineage_mismatch` check. Null
  // (dark) unless SCADA_APPROVED_LINEAGE_ANCHOR_PATH is set; a set-but-broken anchor fails
  // fast (opting in is deliberate — never silently disable the check).
  const approvedLineageAnchor = loadApprovedLineageAnchor();
  if (!approvedLineageAnchor) {
    logger.warn(
      'SCADA_APPROVED_LINEAGE_ANCHOR_PATH is unset — the lineage_mismatch check is DARK (6.2-identical validation)',
    );
  } else {
    // Surface the anchor↔registry binding so a release-A registry paired with a release-B
    // anchor (fail-closed, but otherwise silent 100% lineage_mismatch) is visible at startup.
    logger.info(
      {
        capability_release_id: deviceCapabilities.capability_release_id,
        anchor_model_release_id: approvedLineageAnchor.model_release_id,
      },
      'lineage_mismatch check is ARMED — validating intents against the approved lineage anchor',
    );
  }

  // PR 6.2 — service verifier for the machine-boundary validate endpoint. Null (dark,
  // 503) unless a DEDICATED service secret is configured, kept separate from operator auth.
  const serviceVerifier: ServiceTokenVerifier | null = config.serviceAuth
    ? new SchedulerServiceTokenVerifier(config.serviceAuth)
    : null;
  if (!serviceVerifier) {
    logger.warn(
      'SCHEDULER_SERVICE_JWT_SECRET is unset — POST /internal/v1/command-intents/validate is DARK (503)',
    );
  }

  const app = buildServer({
    verifier: new JwtTokenVerifier({
      secret: config.auth.jwtSecret,
      issuer: config.auth.jwtIssuer,
      audience: config.auth.jwtAudience,
    }),
    commandService,
    snapshot: () => controller.snapshot(),
    site: config.site,
    endpoint,
    rateLimit: config.rateLimit,
    deviceCapabilities,
    serviceVerifier,
    receipts,
    clock: () => Date.now(),
    approvedLineageAnchor,
    siteCanonicalGateId: config.siteCanonicalGateId,
    metrics,
  });

  controller.start();
  const server = app.listen(config.httpPort, () => {
    logger.info(
      {
        site: config.site,
        endpoint,
        port: config.httpPort,
        intervalMs: config.modbus.pollIntervalMs,
      },
      'scada-gate-control started',
    );
  });

  const shutdown = (signal: string): void => {
    logger.info({ signal }, 'shutting down');
    controller.stop();
    server.close();
    void transport.close().finally(() => process.exit(0));
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

void main().catch((error) => {
  logger.error({ err: error instanceof Error ? error.message : String(error) }, 'failed to start');
  process.exit(1);
});
