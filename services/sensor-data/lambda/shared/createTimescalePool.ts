import { Pool, PoolConfig } from 'pg';

let pool: Pool | null = null;

export function createTimescalePool(config: PoolConfig): Pool {
  if (pool) return pool;
  pool = new Pool({
    ...config,
    keepAlive: true,
  });
  // Avoid crashing the process on intermittent network issues
  pool.on('error', (err) => {
    // eslint-disable-next-line no-console
    console.error('pg: unexpected pool error (ignored)', {
      code: (err as any)?.code,
      errno: (err as any)?.errno,
      message: err?.message,
    });
  });
  return pool;
}

