/*
  PM2 ecosystem for Munbon services (runs from repo root, not service folders)
  - Loads environment from root .env (not per-service .env).
  - Uses absolute script paths and repo-root cwd so code that reads ".env" will pick the root file.
  - You can override any value by exporting it in your shell before pm2 start, or by editing the env blocks below.
*/

const fs = require('fs');
const path = require('path');

// Lightweight .env loader (no external deps)
(function loadRootDotEnv() {
  try {
    const envPath = path.resolve(__dirname, '.env');
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf8');
      content.split(/\r?\n/).forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) return;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx === -1) return;
        const key = trimmed.slice(0, eqIdx).trim();
        let val = trimmed.slice(eqIdx + 1).trim();
        // Remove surrounding quotes if any
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (key && process.env[key] === undefined) {
          process.env[key] = val;
        }
      });
    }
  } catch (_) {
    // ignore
  }
})();

const repoRoot = __dirname;

// Helper to pick the first defined env var in the list
function pick(...keys) {
  for (const k of keys) {
    if (process.env[k] && process.env[k] !== '') return process.env[k];
  }
  return undefined;
}

// Compose URLs from root .env pieces when full URLs aren't provided
function buildPostgresUrl(dbName) {
  const host = process.env.DB_HOST || 'localhost';
  const port = process.env.DB_PORT || '5432';
  const user = process.env.DB_USER || 'postgres';
  const pass = process.env.DB_PASSWORD || 'postgres';
  const db = dbName || process.env.DB_NAME || 'postgres';
  return `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}/${db}`;
}

function buildAsyncPostgresUrl(dbName) {
  const host = process.env.DB_HOST || 'localhost';
  const port = process.env.DB_PORT || '5432';
  const user = process.env.DB_USER || 'postgres';
  const pass = process.env.DB_PASSWORD || 'postgres';
  const db = dbName || process.env.DB_NAME || 'postgres';
  return `postgresql+asyncpg://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}/${db}`;
}

// Normalize SQLAlchemy URL to asyncpg and convert schema= to options=-csearch_path=... for asyncpg
function normalizeToAsyncpg(url, schemaEnvKey) {
  if (!url || typeof url !== 'string') return url;
  let u = url.startsWith('postgresql://') && !url.startsWith('postgresql+asyncpg://')
    ? url.replace('postgresql://', 'postgresql+asyncpg://')
    : url;
  try {
    const parsed = new URL(u);
    // migrate ?schema=... to ?options=-csearch_path=...
    const schemaFromUrl = parsed.searchParams.get('schema');
    const schemaFromEnv = schemaEnvKey && process.env[schemaEnvKey] ? process.env[schemaEnvKey] : null;
    const schema = schemaFromEnv || schemaFromUrl;
    if (schema) {
      parsed.searchParams.delete('schema');
      const existingOptions = parsed.searchParams.get('options') || '';
      const searchPathOpt = `-csearch_path=${schema}`;
      const combined = [existingOptions, searchPathOpt].filter(Boolean).join(' ').trim();
      // URLSearchParams will percent-encode spaces automatically
      parsed.searchParams.set('options', combined);
    }
    u = parsed.toString();
  } catch (_) {
    // If URL parsing fails, fall back to the original string
  }
  return u;
}

function buildTimescaleUrl() {
  const host = process.env.TIMESCALE_HOST || process.env.DB_HOST || 'localhost';
  const port = process.env.TIMESCALE_PORT || '5432';
  const user = process.env.TIMESCALE_USER || process.env.DB_USER || 'postgres';
  const pass = process.env.TIMESCALE_PASSWORD || process.env.DB_PASSWORD || 'postgres';
  const db = process.env.TIMESCALE_DB || process.env.DB_NAME_SENSOR_DATA || 'sensor_data';
  return `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}/${db}`;
}

function buildRedisUrl(dbIndex) {
  const host = process.env.REDIS_HOST || 'localhost';
  const port = process.env.REDIS_PORT || '6379';
  const idx = String(dbIndex ?? 0);
  return `redis://${host}:${port}/${idx}`;
}

function serviceUrl(port) {
  return `http://localhost:${port}`;
}

module.exports = {
  apps: [
    // Scheduler (FastAPI)
    {
      name: 'munbon-scheduler',
      cwd: repoRoot, // ensure .env from repo root is used
      script: '/Users/subhajlimanond/dev/munbon2-backend/services/scheduler/venv/bin/python',
      args: ['/Users/subhajlimanond/dev/munbon2-backend/services/scheduler/src/main.py'],
      interpreter: 'none',
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        AWS_REGION: pick('AWS_REGION') || 'ap-southeast-1',
        SERVICE_NAME: 'scheduler',
        SERVICE_PORT: pick('SCHEDULER_PORT', 'SERVICE_PORT') || '3021',
        // Force asyncpg URL and safely handle schema -> options
        DATABASE_URL: normalizeToAsyncpg(pick('SCHEDULER_DATABASE_URL') || buildAsyncPostgresUrl(), 'SCHEDULER_DB_SCHEMA'),
        REDIS_URL: pick('SCHEDULER_REDIS_URL', 'REDIS_URL') || buildRedisUrl(4),
        ROS_SERVICE_URL: pick('ROS_SERVICE_URL') || serviceUrl(3047),
        GIS_SERVICE_URL: pick('GIS_SERVICE_URL') || serviceUrl(3007),
        FLOW_MONITORING_URL: pick('FLOW_MONITORING_URL') || serviceUrl(3011),
        WEATHER_SERVICE_URL: pick('WEATHER_SERVICE_URL') || serviceUrl(3006),
        AUTH_SERVICE_URL: pick('AUTH_SERVICE_URL') || serviceUrl(3001),
        JWT_SECRET_KEY: pick('JWT_SECRET_KEY', 'JWT_SECRET') || 'dev-jwt-secret',
      },
    },

    // Flow Monitoring (FastAPI)
    {
      name: 'munbon-flow-monitoring',
      cwd: repoRoot,
      script: '/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring/venv/bin/python',
      args: ['/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring/src/main.py'],
      interpreter: 'none',
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        SERVICE_NAME: 'flow-monitoring',
        PORT: pick('FLOW_MONITORING_PORT', 'PORT') || '3011',
        // DBs
        POSTGRES_URL: pick('FLOW_POSTGRES_URL', 'POSTGRES_URL') || buildPostgresUrl(),
        TIMESCALE_URL: pick('FLOW_TIMESCALE_URL', 'TIMESCALE_URL') || buildTimescaleUrl(),
        REDIS_URL: pick('FLOW_REDIS_URL', 'REDIS_URL') || buildRedisUrl(3),
        // InfluxDB
        INFLUXDB_URL: pick('INFLUXDB_URL') || 'http://localhost:8086',
        INFLUXDB_TOKEN: pick('INFLUXDB_TOKEN') || 'dev-token',
        INFLUXDB_ORG: pick('INFLUXDB_ORG') || 'munbon',
        INFLUXDB_BUCKET: pick('INFLUXDB_BUCKET') || 'flow_monitoring',
        // Kafka removed/optional — no envs required
        // API
        API_PREFIX: pick('API_PREFIX') || '/api/v1',
        CORS_ORIGINS: pick('CORS_ORIGINS') || 'http://localhost:3000,http://127.0.0.1:3000',
      },
    },

    // BFF Water Planning (FastAPI via uvicorn)
    {
      name: 'munbon-bff-water-planning',
      cwd: repoRoot,
      script: '/Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/venv/bin/python',
      args: ['-m', 'uvicorn', '--app-dir', '/Users/subhajlimanond/dev/munbon2-backend/services/bff-water-planning/src', 'main:app', '--host', '0.0.0.0', '--port', pick('BFF_WATER_PLANNING_PORT') || '3022'],
      interpreter: 'none',
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        SERVICE_NAME: 'bff-water-planning',
        PORT: pick('BFF_WATER_PLANNING_PORT') || '3022',
        POSTGRES_URL: pick('BFF_POSTGRES_URL', 'POSTGRES_URL') || buildPostgresUrl(),
        REDIS_URL: pick('BFF_REDIS_URL', 'REDIS_URL') || buildRedisUrl(2),
        USE_MOCK_SERVER: pick('USE_MOCK_SERVER') || 'true',
        MOCK_SERVER_URL: pick('MOCK_SERVER_URL') || 'http://localhost:3099',
        ROS_SERVICE_URL: pick('ROS_SERVICE_URL') || serviceUrl(3047),
        GIS_SERVICE_URL: pick('GIS_SERVICE_URL') || serviceUrl(3007),
        AWD_CONTROL_URL: pick('AWD_CONTROL_URL') || serviceUrl(3013),
        FLOW_MONITORING_URL: pick('FLOW_MONITORING_URL') || serviceUrl(3011),
        SCHEDULER_URL: pick('SCHEDULER_URL') || serviceUrl(3021),
        WEATHER_API_URL: pick('WEATHER_API_URL') || serviceUrl(3006),
        CORS_ORIGINS: pick('CORS_ORIGINS') || 'http://localhost:3000,http://127.0.0.1:3000',
      },
    },

    // ROS/GIS Integration (FastAPI via uvicorn)
    {
      name: 'munbon-ros-gis-integration',
      cwd: repoRoot,
      script: '/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/venv/bin/python',
      args: ['-m', 'uvicorn', '--app-dir', '/Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration/src', 'main:app', '--host', '0.0.0.0', '--port', pick('ROS_GIS_INTEGRATION_PORT') || '3047'],
      interpreter: 'none',
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        SERVICE_NAME: 'ros-gis-integration',
        PORT: pick('ROS_GIS_INTEGRATION_PORT') || '3047',
        POSTGRES_URL: pick('RG_POSTGRES_URL', 'POSTGRES_URL') || buildPostgresUrl(),
        REDIS_URL: pick('RG_REDIS_URL', 'REDIS_URL') || buildRedisUrl(5),
        FLOW_MONITORING_URL: pick('FLOW_MONITORING_URL') || serviceUrl(3011),
        SCHEDULER_URL: pick('SCHEDULER_URL') || serviceUrl(3021),
        ROS_SERVICE_URL: pick('ROS_SERVICE_URL') || serviceUrl(3047),
        GIS_SERVICE_URL: pick('GIS_SERVICE_URL') || serviceUrl(3007),
        CORS_ORIGINS: pick('CORS_ORIGINS') || '*',
        DAILY_REQUIREMENT_ENABLED: 'false',
        DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED: 'false',
        DAILY_REQUIREMENT_SCHEDULE_ENABLED: 'false',
      },
    },

    // Water Accounting (FastAPI via uvicorn)
    {
      name: 'munbon-water-accounting',
      cwd: repoRoot,
      script: '/Users/subhajlimanond/dev/munbon2-backend/services/water-accounting/venv/bin/python',
      args: ['-m', 'uvicorn', '--app-dir', '/Users/subhajlimanond/dev/munbon2-backend/services/water-accounting/src', 'main:app', '--host', '0.0.0.0', '--port', pick('WATER_ACCOUNTING_PORT') || '3020'],
      interpreter: 'none',
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        SERVICE_NAME: 'water-accounting',
        PORT: pick('WATER_ACCOUNTING_PORT') || '3020',
        POSTGRES_URL: pick('WA_POSTGRES_URL', 'POSTGRES_URL') || buildPostgresUrl(),
        REDIS_URL: pick('WA_REDIS_URL', 'REDIS_URL') || buildRedisUrl(8),
        TIMESCALE_URL: pick('WA_TIMESCALE_URL', 'TIMESCALE_URL') || buildTimescaleUrl(),
        FLOW_MONITORING_URL: pick('FLOW_MONITORING_URL') || serviceUrl(3011),
        GIS_SERVICE_URL: pick('GIS_SERVICE_URL') || serviceUrl(3007),
        WEATHER_API_URL: pick('WEATHER_API_URL') || serviceUrl(3006),
      },
    },

    // AWD Control (Node)
    {
      name: 'munbon-awd-control',
      cwd: repoRoot,
      script: 'npm',
      args: ['start', '--prefix', '/Users/subhajlimanond/dev/munbon2-backend/services/awd-control'],
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        PORT: pick('AWD_CONTROL_PORT') || '3013',
        POSTGRES_URL: pick('AWD_POSTGRES_URL', 'POSTGRES_URL') || buildPostgresUrl(),
        REDIS_URL: pick('AWD_REDIS_URL', 'REDIS_URL') || buildRedisUrl(6),
        TIMESCALE_URL: pick('AWD_TIMESCALE_URL', 'TIMESCALE_URL') || buildTimescaleUrl(),
        TIMESCALE_SSL: pick('TIMESCALE_SSL') || 'false',
        TIMESCALE_SCHEMA: pick('TIMESCALE_SCHEMA') || 'public',
        SENSOR_DATA_URL: pick('SENSOR_DATA_URL') || serviceUrl(3003),
        GIS_SERVICE_URL: pick('GIS_SERVICE_URL') || serviceUrl(3007),
        WEATHER_API_URL: pick('WEATHER_API_URL') || serviceUrl(3006),
        NOTIFICATION_URL: pick('NOTIFICATION_URL') || serviceUrl(3023),
      },
    },

    // GIS (Node)
    {
      name: 'munbon-gis',
      cwd: repoRoot,
      script: 'npm',
      args: ['start', '--prefix', '/Users/subhajlimanond/dev/munbon2-backend/services/gis'],
      env: {
        NODE_ENV: pick('NODE_ENV') || 'development',
        PORT: pick('GIS_PORT') || '3007',
        // The GIS service expects DATABASE_URL specifically
        DATABASE_URL: pick('GIS_DATABASE_URL', 'DATABASE_URL') || buildPostgresUrl(process.env.POSTGIS_DB),
        REDIS_URL: pick('GIS_REDIS_URL', 'REDIS_URL') || buildRedisUrl(7),
        WEATHER_API_URL: pick('WEATHER_API_URL') || serviceUrl(3006),
        SENSOR_DATA_URL: pick('SENSOR_DATA_URL') || serviceUrl(3003),
      },
    },
  ],
};
