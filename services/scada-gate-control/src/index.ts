import 'dotenv/config';
import { loadConfig } from './config';
import { GatePoller } from './transport/poller';
import { ModbusSerialTransport } from './transport/modbus-serial-transport';
import { logger } from './utils/logger';

/**
 * Service entry point. Starts the Modbus poll loop for the configured site.
 * The HTTP API is added in Slice 3; until then the latest snapshot is logged.
 */
function main(): void {
  const config = loadConfig();
  const transport = new ModbusSerialTransport(config.modbus);
  const poller = new GatePoller({
    transport,
    thresholds: config.freshness,
    intervalMs: config.modbus.pollIntervalMs,
    onSnapshot: (snapshot) =>
      logger.info(
        {
          connection: snapshot.connection,
          color: snapshot.markerColor,
          gateLevel: snapshot.gateLevel.value?.technicalLabel ?? null,
          lastUpdated: snapshot.lastUpdated,
        },
        'gate snapshot',
      ),
    onError: (error) =>
      logger.warn({ err: error instanceof Error ? error.message : String(error) }, 'poll error'),
  });

  logger.info(
    {
      site: config.site,
      host: config.modbus.host,
      port: config.modbus.port,
      unitId: config.modbus.unitId,
      intervalMs: config.modbus.pollIntervalMs,
    },
    'starting scada-gate-control poller',
  );
  poller.start();

  const shutdown = (signal: string): void => {
    logger.info({ signal }, 'shutting down');
    poller.stop();
    void transport.close().finally(() => process.exit(0));
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

main();
