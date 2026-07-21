import * as path from 'path';

export interface ServiceSpec {
  name: string;
  type: 'python' | 'node';
  port: number;
  script: string;
  args?: string;
  env?: Record<string, string>;
}

export interface PM2ProcessConfig {
  name: string;
  script: string;
  cwd: string;
  interpreter?: string;
  args?: string;
  autorestart: boolean;
  max_memory_restart: string;
  env?: Record<string, string>;
  error_file: string;
  out_file: string;
  log_date_format: string;
  merge_logs: boolean;
  time: boolean;
  cron_restart?: string;
  restart_delay?: number;
}

const REPO_ROOT = path.resolve(
  __dirname,
  path.basename(__dirname) === 'dist' ? '../../..' : '../..',
);
const LOGS_DIR = path.join(REPO_ROOT, 'logs');

// Credentials are NEVER defaulted here (SEC remediation: the previous hardcoded
// password leaked and must be rotated). Export the real values on the PM2 host
// before building this config; a missing value fails the build, loudly.
export function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} must be set in the environment to build the PM2 config (hardcoded default removed)`,
    );
  }
  return value;
}

function optionalHostEnv(names: readonly string[]): Record<string, string> {
  return Object.fromEntries(
    names.flatMap(name => (process.env[name] ? [[name, process.env[name]]] : [])),
  ) as Record<string, string>;
}

export function buildProcessConfig(spec: ServiceSpec): PM2ProcessConfig {
  const servicePath = path.join(REPO_ROOT, 'services', spec.name);

  const config: PM2ProcessConfig = {
    name: spec.name,
    script: spec.script,
    cwd: servicePath,
    autorestart: true,
    max_memory_restart: spec.type === 'python' ? '512M' : '256M',
    error_file: path.join(LOGS_DIR, `${spec.name}-error.log`),
    out_file: path.join(LOGS_DIR, `${spec.name}-out.log`),
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    time: true,
  };

  if (spec.type === 'python') {
    config.interpreter = 'bash';
  }

  if (spec.args) {
    config.args = spec.args;
  }

  if (spec.env) {
    config.env = spec.env;
  }

  return config;
}

export function getIrrigationProcesses(): PM2ProcessConfig[] {
  const serviceSpecs: ServiceSpec[] = [
    {
      name: 'flow-monitoring',
      type: 'python',
      port: 3011,
      script: './start.sh',
      env: {
        PORT: '3011',
        LOG_LEVEL: 'INFO',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        TIMESCALE_URL: requiredEnv('TIMESCALE_URL'),
        REDIS_URL: 'redis://localhost:6379/3',
        KAFKA_BROKERS: 'localhost:9092',
        KAFKA_TOPIC_SENSORS: 'sensor-data',
        KAFKA_TOPIC_ANALYTICS: 'flow-analytics',
        KAFKA_CONSUMER_GROUP: 'flow-monitoring-consumer',
        INFLUXDB_URL: 'http://localhost:8086',
        INFLUXDB_TOKEN: 'your-influxdb-token-here',
        INFLUXDB_ORG: 'munbon',
        INFLUXDB_BUCKET: 'flow_monitoring',
        // PR 4.4a-2: load the committed commandable=false engineering-prior
        // release (service-root-relative; the loader/validator are proven by the
        // flow suite). Never a commandable release — this plane is non-commanding.
        HYDRAULIC_MODEL_RELEASE_PATH: 'data/model-releases/engineering-prior-v3-v1.json',
        ...optionalHostEnv(['HYDRAULIC_COMMANDABILITY_APPROVAL_PATH']),
      },
    },
    {
      name: 'scheduler',
      type: 'python',
      port: 3021,
      script: './start.sh',
      env: {
        // Canonical scheduler port (PR 4.4a-2): start.sh honors $PORT (default
        // 3021); the retired legacy port is gone here and in every consumer URL.
        PORT: '3021',
        LOG_LEVEL: 'INFO',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        REDIS_URL: 'redis://localhost:6379/4',
        WEATHER_API_URL: 'http://localhost:3006',
        SMS_GATEWAY_URL: 'http://localhost:3050',
        FLOW_MONITORING_URL: 'http://localhost:3011',
        ROS_GIS_URL: 'http://localhost:3047',
        // (dead DATABASE_URL injection removed: the scheduler's settings consume
        // POSTGRES_URL; its EC2 entrypoint builds its own URL from POSTGRES_* parts)
        ROS_SERVICE_URL: 'http://localhost:3047',
        GIS_SERVICE_URL: 'http://localhost:3007',
        WEATHER_SERVICE_URL: 'http://localhost:3006',
        AUTH_SERVICE_URL: 'http://localhost:3005',
        // Control-plane trust hardening (PR 4.4a-1): the JWT signing secret,
        // issuer, audience and claim-policy mode are host-required and NEVER
        // defaulted. The scheduler's Settings rejects a weak secret and refuses
        // to boot without an explicit claim policy, so a missing value fails the
        // build loudly rather than shipping 'change-me'.
        JWT_SECRET_KEY: requiredEnv('JWT_SECRET_KEY'),
        JWT_ISSUER: requiredEnv('JWT_ISSUER'),
        JWT_AUDIENCE: requiredEnv('JWT_AUDIENCE'),
        JWT_ACCESS_TOKEN_TYPE: 'access',
        JWT_CLAIM_POLICY_MODE: requiredEnv('JWT_CLAIM_POLICY_MODE'),
        CORS_ORIGINS: 'http://localhost:3000,http://localhost:3001',
        // PR 7.2: independent Scheduler execution gate. Tracked deploy stays dark.
        CONTROL_EXECUTION_MODE: 'disabled',
        CONTROL_READBACK_RECONCILIATION_MODE: 'off',
        CONTROL_WORKER_HEALTH_GATES_READINESS: 'false',
        ...optionalHostEnv([
          'SCHEDULER_SCADA_BASE_URL',
          'SCHEDULER_SERVICE_JWT_SECRET',
          'SCHEDULER_SERVICE_JWT_ISSUER',
          'SCHEDULER_SERVICE_JWT_AUDIENCE',
          'SCHEDULER_SERVICE_JWT_SUBJECT',
          'SCHEDULER_SERVICE_JWT_MAX_AGE_SECONDS',
        ]),
      },
    },
    {
      name: 'bff-water-planning',
      type: 'python',
      port: 3002,
      script: './start.sh',
      env: {
        PORT: '3002',
        HOST: '0.0.0.0',
        ENVIRONMENT: 'production',
        LOG_LEVEL: 'INFO',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        GIS_DATABASE_URL: requiredEnv('GIS_DATABASE_URL'),
        TIMESCALE_URL: requiredEnv('TIMESCALE_URL'),
        REDIS_URL: 'redis://localhost:6379/2',
        ROS_SERVICE_URL: 'http://localhost:3047',
        GIS_SERVICE_URL: 'http://localhost:3007',
        AWD_CONTROL_URL: 'http://localhost:3010',
        FLOW_MONITORING_URL: 'http://localhost:3011',
        SCHEDULER_URL: 'http://localhost:3021',
        WEATHER_API_URL: 'http://localhost:3006',
        WEATHER_SERVICE_URL: 'http://localhost:3006',
        SENSOR_DATA_URL: 'http://localhost:3003',
        USE_MOCK_SERVER: 'false',
        CORS_ORIGINS: 'http://localhost:3000,http://localhost:3001',
      },
    },
    {
      name: 'ros-gis-integration',
      type: 'python',
      port: 3047,
      script: './start.sh',
      env: {
        PORT: '3047',
        LOG_LEVEL: 'INFO',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        GIS_DATABASE_URL: requiredEnv('GIS_DATABASE_URL'),
        REDIS_URL: 'redis://localhost:6379/5',
        FLOW_MONITORING_URL: 'http://localhost:3011',
        SCHEDULER_URL: 'http://localhost:3021',
        GIS_SERVICE_URL: 'http://localhost:3007',
        ROS_SERVICE_URL: 'http://localhost:3047',
        CORS_ORIGINS: 'http://localhost:3000,http://localhost:3001',
        DAILY_REQUIREMENT_ENABLED: 'false',
        DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED: 'false',
        DAILY_REQUIREMENT_SCHEDULE_ENABLED: 'false',
      },
    },
    {
      name: 'awd-control',
      type: 'node',
      port: 3010,
      script: 'npm',
      args: 'start',
      env: {
        PORT: '3010',
        LOG_LEVEL: 'info',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        TIMESCALE_URL: requiredEnv('TIMESCALE_URL'),
        TIMESCALE_HOST: '43.208.201.191',
        TIMESCALE_PORT: '5432',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: requiredEnv('TIMESCALE_PASSWORD'),
        TIMESCALE_DB: 'sensor_data',
        REDIS_URL: 'redis://localhost:6379/6',
        KAFKA_BROKERS: 'localhost:9092',
        POSTGRES_HOST: '43.208.201.191',
        POSTGRES_PORT: '5432',
        POSTGRES_DB: 'munbon_dev',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: requiredEnv('POSTGRES_PASSWORD'),
      },
    },
    {
      name: 'gis',
      type: 'node',
      port: 3007,
      script: 'npm',
      args: 'start',
      env: {
        PORT: '3007',
        LOG_LEVEL: 'info',
        ENVIRONMENT: 'production',
        DATABASE_URL: requiredEnv('GIS_DATABASE_URL'),
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        REDIS_URL: 'redis://localhost:6379/7',
        SRID: '32647',
        GEOMETRY_COLUMN: 'geom',
        MAX_FEATURES_PER_REQUEST: '10000',
        TILE_CACHE_TTL_SECONDS: '3600',
        MAX_ZOOM_LEVEL: '18',
        MIN_ZOOM_LEVEL: '8',
        WEATHER_API_URL: 'http://localhost:3006',
        SENSOR_DATA_URL: 'http://localhost:3003',
        SPATIAL_INDEX_CACHE_SIZE: '50000',
        QUERY_TIMEOUT_SECONDS: '30',
        CONNECTION_POOL_SIZE: '20',
      },
    },
    {
      name: 'water-accounting',
      type: 'python',
      port: 3020,
      script: './start.sh',
      env: {
        PORT: '3020',
        LOG_LEVEL: 'INFO',
        ENVIRONMENT: 'production',
        POSTGRES_URL: requiredEnv('POSTGRES_URL'),
        REDIS_URL: 'redis://localhost:6379/8',
        TIMESCALE_URL: requiredEnv('TIMESCALE_URL'),
        FLOW_MONITORING_URL: 'http://localhost:3014',
        GIS_SERVICE_URL: 'http://localhost:3007',
        WATER_LEVEL_URL: 'http://localhost:3008',
        WEATHER_API_URL: 'http://localhost:3006',
        ACCOUNTING_PERIOD_DAYS: '30',
        BALANCE_CALCULATION_INTERVAL_HOURS: '1',
        REPORT_GENERATION_TIME: '06:00',
        TIMEZONE: 'Asia/Bangkok',
        MAX_CALCULATION_BATCH_SIZE: '10000',
        CACHE_TTL_SECONDS: '1800',
        HISTORICAL_DATA_RETENTION_DAYS: '365',
      },
    },
  ];

  const processes = serviceSpecs.map(buildProcessConfig);
  const scheduler = processes.find(process => process.name === 'scheduler');
  if (!scheduler) throw new Error('scheduler process missing');
  processes.push({
    ...scheduler,
    name: 'scheduler-control-dispatch',
    script: './venv/bin/python',
    args: '-m jobs.shadow_dispatch_once',
    interpreter: 'none',
    // The command is a bounded one-shot. PM2 waits after its clean exit and then
    // launches a fresh process; cron_restart cannot schedule a process once stopped.
    autorestart: true,
    restart_delay: 60_000,
    env: {
      ...(scheduler.env ?? {}),
      PYTHONPATH: path.join(scheduler.cwd, 'src'),
    },
    error_file: path.join(LOGS_DIR, 'scheduler-control-dispatch-error.log'),
    out_file: path.join(LOGS_DIR, 'scheduler-control-dispatch-out.log'),
  });
  return processes;
}
