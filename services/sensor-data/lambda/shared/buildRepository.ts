import type { PoolConfig } from 'pg';
import { createTimescalePool } from './createTimescalePool';
import { TimescaleRepository } from '../../src/repository/timescale.repository';

export function buildRepositoryFromEnv(env: NodeJS.ProcessEnv): TimescaleRepository {
  const config: PoolConfig = {
    host: env.TIMESCALE_HOST || 'localhost',
    port: parseInt(env.TIMESCALE_PORT || '5432', 10),
    database: env.TIMESCALE_DB || 'sensor_data',
    user: env.TIMESCALE_USER || 'postgres',
    password: env.TIMESCALE_PASSWORD || '',
  };
  const pool = createTimescalePool(config);
  // TimescaleRepository accepts PoolConfig, but internally builds a Pool itself.
  // To reuse our singleton pool, we pass the same config; the repository will create
  // its own Pool. This is acceptable for Lambda since the module is cached per warm instance.
  // If we want to share the exact Pool instance, we could extend the repository, but keep minimal changes now.
  return new TimescaleRepository(config);
}

