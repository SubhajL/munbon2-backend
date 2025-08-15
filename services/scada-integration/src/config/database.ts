import { Pool } from 'pg';

// SCADA database configuration
export const scadaPool = new Pool({
  host: process.env.SCADA_DB_HOST || 'moonup.hopto.org',
  port: parseInt(process.env.SCADA_DB_PORT || '5432'),
  database: process.env.SCADA_DB_NAME || 'db_scada',
  user: process.env.SCADA_DB_USER || 'postgres',
  password: process.env.SCADA_DB_PASSWORD || 'P@ssw0rd123!',
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Test connection
export async function testScadaConnection(): Promise<boolean> {
  try {
    const client = await scadaPool.connect();
    await client.query('SELECT 1');
    client.release();
    console.log('✅ SCADA database connection successful');
    return true;
  } catch (error) {
    console.error('❌ SCADA database connection failed:', error);
    return false;
  }
}

// Graceful shutdown
export async function closeConnections(): Promise<void> {
  await scadaPool.end();
  console.log('Database connections closed');
}