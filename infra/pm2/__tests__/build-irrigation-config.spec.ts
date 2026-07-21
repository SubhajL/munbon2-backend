import * as fs from 'fs';
import * as path from 'path';
import { buildProcessConfig, getIrrigationProcesses } from '../build-irrigation-config';

const REPO_ROOT = path.resolve(__dirname, '../../..');

// Credentials are no longer hardcoded in the config (SEC remediation): the builder
// requires these from the host environment and fails closed otherwise.
const REQUIRED_ENV: Record<string, string> = {
  POSTGRES_URL: 'postgresql://user:pw@test-host:5432/munbon_dev',
  TIMESCALE_URL: 'postgresql://user:pw@test-host:5432/sensor_data',
  GIS_DATABASE_URL: 'postgresql://user:pw@test-host:5432/munbon_gis',
  TIMESCALE_PASSWORD: 'test-timescale-pw',
  POSTGRES_PASSWORD: 'test-postgres-pw',
  // Control-plane trust hardening (PR 4.4a-1): the scheduler JWT config is
  // host-required and never hardcoded.
  JWT_SECRET_KEY: 'strong-test-jwt-secret-0123456789abcdef',
  JWT_ISSUER: 'munbon-auth',
  JWT_AUDIENCE: 'munbon-scheduler',
  JWT_CLAIM_POLICY_MODE: 'strict',
};

describe('build-irrigation-config', () => {
  const saved: Record<string, string | undefined> = {};

  beforeAll(() => {
    for (const [key, value] of Object.entries(REQUIRED_ENV)) {
      saved[key] = process.env[key];
      process.env[key] = value;
    }
  });

  afterAll(() => {
    for (const key of Object.keys(REQUIRED_ENV)) {
      if (saved[key] === undefined) delete process.env[key];
      else process.env[key] = saved[key];
    }
  });

  describe('fail-closed credentials', () => {
    it('throws when a credential env var is missing (no hardcoded default)', () => {
      const prev = process.env.POSTGRES_URL;
      delete process.env.POSTGRES_URL;
      try {
        expect(() => getIrrigationProcesses()).toThrow(/POSTGRES_URL must be set/);
      } finally {
        process.env.POSTGRES_URL = prev;
      }
    });

    it('passes host env credential values through to service env blocks', () => {
      const processes = getIrrigationProcesses();
      const flow = processes.find(p => p.name === 'flow-monitoring');
      expect(flow?.env?.POSTGRES_URL).toBe(REQUIRED_ENV.POSTGRES_URL);
      const awd = processes.find(p => p.name === 'awd-control');
      expect(awd?.env?.POSTGRES_PASSWORD).toBe(REQUIRED_ENV.POSTGRES_PASSWORD);
      expect(awd?.env?.TIMESCALE_PASSWORD).toBe(REQUIRED_ENV.TIMESCALE_PASSWORD);
    });

    it('never hardcodes the scheduler JWT secret and requires it from env', () => {
      const prev = process.env.JWT_SECRET_KEY;
      delete process.env.JWT_SECRET_KEY;
      try {
        expect(() => getIrrigationProcesses()).toThrow(/JWT_SECRET_KEY must be set/);
      } finally {
        process.env.JWT_SECRET_KEY = prev;
      }

      const scheduler = getIrrigationProcesses().find(p => p.name === 'scheduler');
      // The old hardcoded 'change-me' secret is gone; the host value flows through.
      expect(scheduler?.env?.JWT_SECRET_KEY).toBe(REQUIRED_ENV.JWT_SECRET_KEY);
      expect(scheduler?.env?.JWT_SECRET_KEY).not.toBe('change-me');
      expect(scheduler?.env?.JWT_ISSUER).toBe(REQUIRED_ENV.JWT_ISSUER);
      expect(scheduler?.env?.JWT_AUDIENCE).toBe(REQUIRED_ENV.JWT_AUDIENCE);
      expect(scheduler?.env?.JWT_CLAIM_POLICY_MODE).toBe(REQUIRED_ENV.JWT_CLAIM_POLICY_MODE);
      expect(scheduler?.env?.JWT_ACCESS_TOKEN_TYPE).toBe('access');
    });

    it('requires the scheduler claim-policy mode from env (fail-closed)', () => {
      const prev = process.env.JWT_CLAIM_POLICY_MODE;
      delete process.env.JWT_CLAIM_POLICY_MODE;
      try {
        expect(() => getIrrigationProcesses()).toThrow(/JWT_CLAIM_POLICY_MODE must be set/);
      } finally {
        process.env.JWT_CLAIM_POLICY_MODE = prev;
      }
    });
  });

  describe('getIrrigationProcesses', () => {
    it('returns 7 services plus the bounded control-dispatch worker', () => {
      const processes = getIrrigationProcesses();

      expect(processes).toHaveLength(8);

      const serviceNames = processes.map(p => p.name);
      expect(serviceNames).toContain('flow-monitoring');
      expect(serviceNames).toContain('scheduler');
      expect(serviceNames).toContain('bff-water-planning');
      expect(serviceNames).toContain('ros-gis-integration');
      expect(serviceNames).toContain('awd-control');
      expect(serviceNames).toContain('gis');
      expect(serviceNames).toContain('water-accounting');
      expect(serviceNames).toContain('scheduler-control-dispatch');
    });

    it('uses bash interpreter and start script wrappers for python apps', () => {
      const processes = getIrrigationProcesses();

      const pythonServices = processes.filter(p =>
        [
          'flow-monitoring',
          'scheduler',
          'bff-water-planning',
          'ros-gis-integration',
          'water-accounting',
        ].includes(p.name),
      );

      pythonServices.forEach(service => {
        expect(service.script).toBe('./start.sh');
        expect(service.interpreter).toBe('bash');
      });
    });

    it('applies working directory and args', () => {
      const processes = getIrrigationProcesses();

      // Check Python service (bff-water-planning)
      const bffService = processes.find(p => p.name === 'bff-water-planning');
      expect(bffService).toBeDefined();
      expect(bffService!.cwd).toContain('services/bff-water-planning');
      expect(bffService!.script).toBe('./start.sh');
      expect(bffService!.interpreter).toBe('bash');

      // Check Node.js service (awd-control)
      const awdService = processes.find(p => p.name === 'awd-control');
      expect(awdService).toBeDefined();
      expect(awdService!.cwd).toContain('services/awd-control');
      expect(awdService!.script).toBe('npm');
      expect(awdService!.args).toBe('start');
      expect(awdService!.interpreter).toBeUndefined();

      // Check Node.js service (gis)
      const gisService = processes.find(p => p.name === 'gis');
      expect(gisService).toBeDefined();
      expect(gisService!.cwd).toContain('services/gis');
      expect(gisService!.script).toBe('npm');
      expect(gisService!.args).toBe('start');
      expect(gisService!.interpreter).toBeUndefined();
    });

    it('injects required environment variables per service', () => {
      const processes = getIrrigationProcesses();

      const flow = processes.find(p => p.name === 'flow-monitoring');
      expect(flow?.env).toMatchObject({
        POSTGRES_URL: expect.any(String),
        TIMESCALE_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        INFLUXDB_URL: expect.any(String),
        INFLUXDB_TOKEN: expect.any(String),
        INFLUXDB_ORG: expect.any(String),
        INFLUXDB_BUCKET: expect.any(String),
        KAFKA_BROKERS: expect.any(String),
        KAFKA_TOPIC_SENSORS: expect.any(String),
        KAFKA_TOPIC_ANALYTICS: expect.any(String),
        KAFKA_CONSUMER_GROUP: expect.any(String),
      });

      const scheduler = processes.find(p => p.name === 'scheduler');
      expect(scheduler?.env).toMatchObject({
        POSTGRES_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        WEATHER_API_URL: expect.any(String),
        SMS_GATEWAY_URL: expect.any(String),
        CORS_ORIGINS: expect.any(String),
      });

      const rosGis = processes.find(p => p.name === 'ros-gis-integration');
      expect(rosGis?.env).toMatchObject({
        POSTGRES_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        GIS_SERVICE_URL: expect.any(String),
        FLOW_MONITORING_URL: expect.any(String),
        SCHEDULER_URL: expect.any(String),
        CORS_ORIGINS: expect.any(String),
      });

      const bff = processes.find(p => p.name === 'bff-water-planning');
      expect(bff?.env).toMatchObject({
        POSTGRES_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        FLOW_MONITORING_URL: expect.any(String),
        GIS_SERVICE_URL: expect.any(String),
        AWD_CONTROL_URL: expect.any(String),
        CORS_ORIGINS: expect.any(String),
      });

      const gis = processes.find(p => p.name === 'gis');
      expect(gis?.env).toMatchObject({
        DATABASE_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        PORT: expect.any(String),
      });

      const waterAccounting = processes.find(p => p.name === 'water-accounting');
      expect(waterAccounting?.env).toMatchObject({
        POSTGRES_URL: expect.any(String),
        REDIS_URL: expect.any(String),
        TIMESCALE_URL: expect.any(String),
        FLOW_MONITORING_URL: expect.any(String),
        GIS_SERVICE_URL: expect.any(String),
        WATER_LEVEL_URL: expect.any(String),
        WEATHER_API_URL: expect.any(String),
      });
    });

    it('pins all ros-gis daily-requirement lifecycle flags false', () => {
      const processes = getIrrigationProcesses();

      const rosGis = processes.find(p => p.name === 'ros-gis-integration');
      expect(rosGis?.env).toMatchObject({
        DAILY_REQUIREMENT_ENABLED: 'false',
        DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED: 'false',
        DAILY_REQUIREMENT_SCHEDULE_ENABLED: 'false',
      });
    });

    it('registers the recurring bounded dispatch tick with both tracked execution gates dark', () => {
      const processes = getIrrigationProcesses();
      const scheduler = processes.find(p => p.name === 'scheduler');
      const worker = processes.find(p => p.name === 'scheduler-control-dispatch');
      expect(scheduler?.env?.CONTROL_EXECUTION_MODE).toBe('disabled');
      expect(worker).toMatchObject({
        cwd: scheduler?.cwd,
        script: './venv/bin/python',
        args: '-m jobs.shadow_dispatch_once',
        interpreter: 'none',
        autorestart: true,
        restart_delay: 60_000,
      });
      expect(worker?.cron_restart).toBeUndefined();
      expect(worker?.env?.CONTROL_EXECUTION_MODE).toBe('disabled');
      expect(worker?.env?.PYTHONPATH).toBe(`${scheduler?.cwd}/src`);
    });

    it('keeps trust artifacts and service auth optional while dark but passes host values through', () => {
      const names = [
        'HYDRAULIC_COMMANDABILITY_APPROVAL_PATH',
        'SCHEDULER_SCADA_BASE_URL',
        'SCHEDULER_SERVICE_JWT_SECRET',
      ];
      const previous = Object.fromEntries(names.map(name => [name, process.env[name]]));
      try {
        for (const name of names) delete process.env[name];
        const dark = getIrrigationProcesses();
        expect(dark.find(item => item.name === 'flow-monitoring')?.env).not.toHaveProperty(
          'HYDRAULIC_COMMANDABILITY_APPROVAL_PATH',
        );
        expect(dark.find(item => item.name === 'scheduler')?.env).toMatchObject({
          CONTROL_EXECUTION_MODE: 'disabled',
          CONTROL_READBACK_RECONCILIATION_MODE: 'off',
          CONTROL_WORKER_HEALTH_GATES_READINESS: 'false',
        });
        expect(dark.find(item => item.name === 'scheduler')?.env).not.toHaveProperty(
          'SCHEDULER_SERVICE_JWT_SECRET',
        );

        process.env.HYDRAULIC_COMMANDABILITY_APPROVAL_PATH = '/run/approvals/model.json';
        process.env.SCHEDULER_SCADA_BASE_URL = 'http://field-host:3030';
        process.env.SCHEDULER_SERVICE_JWT_SECRET = 'host-service-secret';
        const configured = getIrrigationProcesses();
        expect(configured.find(item => item.name === 'flow-monitoring')?.env).toMatchObject({
          HYDRAULIC_COMMANDABILITY_APPROVAL_PATH: '/run/approvals/model.json',
        });
        expect(configured.find(item => item.name === 'scheduler')?.env).toMatchObject({
          SCHEDULER_SCADA_BASE_URL: 'http://field-host:3030',
          SCHEDULER_SERVICE_JWT_SECRET: 'host-service-secret',
          CONTROL_EXECUTION_MODE: 'disabled',
        });
      } finally {
        for (const name of names) {
          if (previous[name] === undefined) delete process.env[name];
          else process.env[name] = previous[name];
        }
      }
    });

    // PR 4.4a-2: canonical scheduler runtime port is 3021 everywhere. start.sh
    // honors $PORT (default 3021); PM2 must set PORT=3021 and the spec port to
    // 3021, and every consumer URL (BFF, ros-gis) must point at 3021.
    it('uses port 3021 for the scheduler and every consumer that calls it', () => {
      const processes = getIrrigationProcesses();

      const scheduler = processes.find(p => p.name === 'scheduler');
      expect(scheduler?.env?.PORT).toBe('3021');
      // The retired 3012 must not linger anywhere in the scheduler env.
      expect(scheduler?.env?.PORT).not.toBe('3012');

      const bff = processes.find(p => p.name === 'bff-water-planning');
      expect(bff?.env?.SCHEDULER_URL).toBe('http://localhost:3021');

      const rosGis = processes.find(p => p.name === 'ros-gis-integration');
      expect(rosGis?.env?.SCHEDULER_URL).toBe('http://localhost:3021');
    });

    it('retires the hardcoded 3012 scheduler spec port from the config source', () => {
      // The ServiceSpec.port is not surfaced on PM2ProcessConfig, so lock the
      // source: the scheduler spec must declare port 3021 and 3012 is gone.
      const source = fs.readFileSync(
        path.join(REPO_ROOT, 'infra', 'pm2', 'build-irrigation-config.ts'),
        'utf-8',
      );
      expect(source).toContain('port: 3021');
      expect(source).not.toContain('3012');
    });

    // PR 4.4a-2: flow-monitoring must load the committed commandable=false
    // engineering-prior release; PM2 wires its exact repo path and the file must
    // exist (the loader is proven by the flow suite — never invent a filename).
    it('wires the committed non-commandable flow release path', () => {
      const flow = getIrrigationProcesses().find(p => p.name === 'flow-monitoring');
      const releasePath = flow?.env?.HYDRAULIC_MODEL_RELEASE_PATH;
      expect(releasePath).toBe('data/model-releases/engineering-prior-v3-v1.json');

      const absolute = path.join(REPO_ROOT, 'services', 'flow-monitoring', releasePath as string);
      const release = JSON.parse(fs.readFileSync(absolute, 'utf-8'));
      expect(release.commandable).toBe(false);
      expect(release.evidence_class).toBe('engineering_prior');
    });
  });

  describe('deploy topology', () => {
    it('has retired the EC2 docker deploy workflow (PM2 is the topology)', () => {
      const workflow = path.join(REPO_ROOT, '.github', 'workflows', 'deploy-flow-monitoring.yml');
      expect(fs.existsSync(workflow)).toBe(false);
    });
  });

  describe('buildProcessConfig', () => {
    it('normalizes Python service configuration', () => {
      const spec = {
        name: 'test-python-service',
        type: 'python' as const,
        port: 3000,
        script: './start.sh',
      };

      const config = buildProcessConfig(spec);

      expect(config.name).toBe('test-python-service');
      expect(config.interpreter).toBe('bash');
      expect(config.script).toBe('./start.sh');
      expect(config.cwd).toContain('services/test-python-service');
      expect(config.autorestart).toBe(true);
      expect(config.max_memory_restart).toBe('512M');
    });

    it('normalizes Node.js service configuration', () => {
      const spec = {
        name: 'test-node-service',
        type: 'node' as const,
        port: 3010,
        script: 'npm',
        args: 'start',
      };

      const config = buildProcessConfig(spec);

      expect(config.name).toBe('test-node-service');
      expect(config.interpreter).toBeUndefined();
      expect(config.script).toBe('npm');
      expect(config.args).toBe('start');
      expect(config.cwd).toContain('services/test-node-service');
      expect(config.autorestart).toBe(true);
      expect(config.max_memory_restart).toBe('256M');
    });

    it('applies custom log paths', () => {
      const spec = {
        name: 'test-service',
        type: 'python' as const,
        port: 3000,
        script: 'src/main.py',
        args: '',
      };

      const config = buildProcessConfig(spec);

      expect(config.error_file).toContain('logs/test-service-error.log');
      expect(config.out_file).toContain('logs/test-service-out.log');
      expect(config.log_date_format).toBe('YYYY-MM-DD HH:mm:ss Z');
      expect(config.merge_logs).toBe(true);
      expect(config.time).toBe(true);
    });
  });
});
