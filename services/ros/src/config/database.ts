import { Pool, PoolConfig } from 'pg';
import { config } from './index';
import { logger } from '@utils/logger';

const poolConfig: PoolConfig = {
  host: config.database.host,
  port: config.database.port,
  database: config.database.name,
  user: config.database.user,
  password: config.database.password,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
};

export const pool = new Pool(poolConfig);

pool.on('error', (err) => {
  logger.error('Unexpected error on idle database client', err);
});

export async function testConnection(): Promise<boolean> {
  try {
    const client = await pool.connect();
    await client.query('SELECT 1');
    client.release();
    logger.info('Database connection successful');
    return true;
  } catch (error) {
    logger.error('Database connection failed:', error);
    return false;
  }
}

export async function closeDatabase(): Promise<void> {
  await pool.end();
  logger.info('Database pool closed');
}