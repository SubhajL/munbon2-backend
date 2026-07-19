import 'dotenv/config';
import { Pool } from 'pg';
import { loadConfig, type AppConfig } from './config';
import { ModbusSerialTransport } from './transport/modbus-serial-transport';
import { GateController } from './state/gate-controller';
import { JwtTokenVerifier } from './api/auth';
import { buildServer } from './api/server';
import { loadDeviceCapabilitySnapshot } from './domain/device-registry';
import { CommandService } from './services/command-service';
import { InMemoryAuditRepository } from './audit/memory-repository';
import { PostgresAuditRepository } from './audit/pg-repository';
import type { AuditRepository } from './audit/types';
import { logger } from './utils/logger';

/** Durable audit is mandatory unless explicitly opted out for development. */
async function resolveAudit(config: AppConfig): Promise<AuditRepository> {
  if (config.databaseUrl) {
    const pool = new Pool({ connectionString: config.databaseUrl });
    const repository = new PostgresAuditRepository(pool);
    await repository.ensureSchema();
    return repository;
  }
  if (!config.allowInMemoryAudit) {
    throw new Error(
      'DATABASE_URL is required for a durable audit log; set ALLOW_IN_MEMORY_AUDIT=true only for development',
    );
  }
  logger.warn('using NON-PERSISTENT in-memory audit log (ALLOW_IN_MEMORY_AUDIT=true)');
  return new InMemoryAuditRepository();
}

async function main(): Promise<void> {
  const config = loadConfig();
  const endpoint = {
    host: config.modbus.host,
    port: config.modbus.port,
    unitId: config.modbus.unitId,
  };

  const transport = new ModbusSerialTransport(config.modbus);
  const controller = new GateController({
    transport,
    thresholds: config.freshness,
    intervalMs: config.modbus.pollIntervalMs,
    onError: (error) =>
      logger.warn({ err: error instanceof Error ? error.message : String(error) }, 'poll error'),
  });

  const audit = await resolveAudit(config);

  const commandService = new CommandService({
    actuator: controller,
    audit,
    now: () => Date.now(),
    endpoint,
    site: config.site,
  });

  // Fail-fast at startup on a broken registry (empty when unset = zero gates).
  const deviceCapabilities = loadDeviceCapabilitySnapshot();

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
