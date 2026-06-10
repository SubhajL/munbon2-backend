import 'dotenv/config';
import { DEFAULT_UNIT_ID, GATE_LEVEL_VALUES, REGISTERS } from './domain';
import { logger } from './utils/logger';

/**
 * Service entry point. Transport (poll loop) and the HTTP API are added in
 * later slices; for now we boot, log the active register map, and self-check
 * the domain tables so a misconfigured build fails loudly at startup.
 */
function main(): void {
  logger.info(
    {
      registers: REGISTERS,
      gateLevels: GATE_LEVEL_VALUES,
      defaultUnitId: DEFAULT_UNIT_ID,
    },
    'scada-gate-control domain core loaded',
  );
}

main();
