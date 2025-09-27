import { DataSource } from 'typeorm';
import { config } from './index';
import { User } from '../models/user.entity';
import { RefreshToken } from '../models/refresh-token.entity';
import { LoginAttempt } from '../models/login-attempt.entity';
import { PasswordReset } from '../models/password-reset.entity';
import { TwoFactorSecret } from '../models/two-factor-secret.entity';
import { AuditLog } from '../models/audit-log.entity';
import { Session } from '../models/session.entity';
import { Role } from '../models/role.entity';
import { Permission } from '../models/permission.entity';

export const AppDataSource = new DataSource({
  type: 'postgres',
  url: config.database.url,
  ssl: config.database.ssl ? { rejectUnauthorized: false } : false,
  synchronize: config.env === 'development',
  logging: config.env === 'development' && config.logging.level === 'debug',
  entities: [
    User,
    RefreshToken,
    LoginAttempt,
    PasswordReset,
    TwoFactorSecret,
    AuditLog,
    Session,
    Role,
    Permission,
  ],
  migrations: ['src/migrations/*.ts'],
  subscribers: ['src/subscribers/*.ts'],
  schema: 'auth',
  poolSize: 10,
  extra: {
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
  },
});

export async function connectDatabase(): Promise<void> {
  try {
    await AppDataSource.initialize();
    
    // Create schema if it doesn't exist
    await AppDataSource.query(`CREATE SCHEMA IF NOT EXISTS auth`);
    
    // Run any pending migrations in production
    if (config.env === 'production') {
      await AppDataSource.runMigrations();
    }
  } catch (error) {
    throw new Error(`Database connection failed: ${error}`);
  }
}