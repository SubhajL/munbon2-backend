import { PoolConfig } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load EC2 specific env vars
dotenv.config({ path: path.join(__dirname, '../..', '.env.ec2') });

export interface DualWriteEnvironmentConfig {
  enableDualWrite: boolean;
  localDatabase: PoolConfig;
  ec2Database: PoolConfig;
  ec2WriteTimeout: number;
  retryAttempts: number;
  retryDelay: number;
}

export function getDualWriteConfig(): DualWriteEnvironmentConfig {
  // Check feature flag from environment
  const enableDualWrite = process.env.ENABLE_DUAL_WRITE === 'true';

  // Local database configuration
  const localDatabase: PoolConfig = {
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres',
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
  };

  // EC2 database configuration
  const ec2Database: PoolConfig = {
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'postgres',
    max: 10, // Smaller pool for EC2
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000, // Longer timeout for network latency
  };

  return {
    enableDualWrite,
    localDatabase,
    ec2Database,
    ec2WriteTimeout: parseInt(process.env.EC2_WRITE_TIMEOUT || '5000'),
    retryAttempts: parseInt(process.env.EC2_RETRY_ATTEMPTS || '3'),
    retryDelay: parseInt(process.env.EC2_RETRY_DELAY || '1000'),
  };
}

// Validation function to check if EC2 config is properly set
export function validateEc2Config(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  if (!process.env.EC2_DB_HOST) {
    errors.push('EC2_DB_HOST is not set');
  }
  
  if (!process.env.EC2_DB_PASSWORD) {
    errors.push('EC2_DB_PASSWORD is not set');
  }

  // Only validate if dual write is enabled
  if (process.env.ENABLE_DUAL_WRITE === 'true' && errors.length > 0) {
    return { valid: false, errors };
  }

  return { valid: true, errors: [] };
}