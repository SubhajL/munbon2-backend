import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

// TimescaleDB on EC2 for sensor data (consolidated to port 5432)
export const timescalePool = new Pool({
  host: process.env.TIMESCALE_HOST || '43.209.22.250',
  port: parseInt(process.env.TIMESCALE_PORT || '5432'),
  database: process.env.TIMESCALE_DB || 'postgres',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'P@ssw0rd123!',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// PostGIS on EC2 for zone/section data (consolidated to port 5432)
export const postgisPool = new Pool({
  host: process.env.POSTGIS_HOST || '43.209.22.250',
  port: parseInt(process.env.POSTGIS_PORT || '5432'),
  database: process.env.POSTGIS_DB || 'postgres',
  user: process.env.POSTGIS_USER || 'postgres',
  password: process.env.POSTGIS_PASSWORD || 'P@ssw0rd123!',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Test connections
export async function testConnections() {
  try {
    await timescalePool.query('SELECT NOW()');
    console.log('✅ TimescaleDB connection successful');
    
    await postgisPool.query('SELECT NOW()');
    console.log('✅ PostGIS connection successful');
  } catch (error) {
    console.error('❌ Database connection failed:', error);
    throw error;
  }
}