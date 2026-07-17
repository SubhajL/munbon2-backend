import { buildProcessConfig, getIrrigationProcesses } from '../build-irrigation-config';

// Credentials are no longer hardcoded in the config (SEC remediation): the builder
// requires these from the host environment and fails closed otherwise.
const REQUIRED_ENV: Record<string, string> = {
  POSTGRES_URL: 'postgresql://user:pw@test-host:5432/munbon_dev',
  TIMESCALE_URL: 'postgresql://user:pw@test-host:5432/sensor_data',
  GIS_DATABASE_URL: 'postgresql://user:pw@test-host:5432/munbon_gis',
  TIMESCALE_PASSWORD: 'test-timescale-pw',
  POSTGRES_PASSWORD: 'test-postgres-pw',
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
  });

  describe('getIrrigationProcesses', () => {
    it('returns 7 irrigation services', () => {
      const processes = getIrrigationProcesses();

      expect(processes).toHaveLength(7);

      const serviceNames = processes.map(p => p.name);
      expect(serviceNames).toContain('flow-monitoring');
      expect(serviceNames).toContain('scheduler');
      expect(serviceNames).toContain('bff-water-planning');
      expect(serviceNames).toContain('ros-gis-integration');
      expect(serviceNames).toContain('awd-control');
      expect(serviceNames).toContain('gis');
      expect(serviceNames).toContain('water-accounting');
    });

    it('uses bash interpreter and start script wrappers for python apps', () => {
      const processes = getIrrigationProcesses();

      const pythonServices = processes.filter(p =>
        ['flow-monitoring', 'scheduler', 'bff-water-planning', 'ros-gis-integration', 'water-accounting'].includes(p.name)
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
