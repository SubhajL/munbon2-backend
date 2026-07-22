import { buildProcessConfig, requiredEnv, type PM2ProcessConfig } from './build-irrigation-config';

const OPTIONAL_FIELD_ENV = [
  'SCADA_SITE_CANONICAL_GATE_ID',
  'SCADA_APPROVED_FIELD_BUNDLE_PATH',
  'SCHEDULER_SERVICE_JWT_SECRET',
  'SCHEDULER_SERVICE_JWT_ISSUER',
  'SCHEDULER_SERVICE_JWT_AUDIENCE',
  'SCHEDULER_SERVICE_JWT_MAX_AGE',
] as const;

export function getScadaFieldProcesses(): PM2ProcessConfig[] {
  const optionalEnv = Object.fromEntries(
    OPTIONAL_FIELD_ENV.flatMap(name => (process.env[name] ? [[name, process.env[name]]] : [])),
  ) as Record<string, string>;
  const config = buildProcessConfig({
    name: 'scada-gate-control',
    type: 'node',
    port: 3030,
    script: 'dist/index.js',
    env: {
      NODE_ENV: 'production',
      PORT: '3030',
      LOG_LEVEL: 'info',
      TZ: 'Asia/Bangkok',
      DATABASE_URL: requiredEnv('DATABASE_URL'),
      JWT_SECRET: requiredEnv('JWT_SECRET'),
      MODBUS_HOST: requiredEnv('MODBUS_HOST'),
      ALLOW_IN_MEMORY_AUDIT: 'false',
      ALLOW_MACHINE_COMMANDS: 'false',
      ...optionalEnv,
    },
  });
  return [{ ...config, restart_delay: 5_000 }];
}
