const path = require('path');

// Ensure minimal env so config module loads without throwing validation errors
beforeAll(() => {
  process.env.TIMESCALE_HOST = 'localhost';
  process.env.TIMESCALE_PORT = '5432';
  process.env.TIMESCALE_DB = 'sensor_data';
  process.env.TIMESCALE_USER = 'postgres';
  process.env.TIMESCALE_PASSWORD = 'dummy';

  process.env.CONFIG_DB_HOST = 'localhost';
  process.env.CONFIG_DB_PORT = '5432';
  // CONFIG_DB_NAME has a default 'munbon_dev'
  process.env.CONFIG_DB_USER = 'postgres';
  process.env.CONFIG_DB_PASSWORD = 'dummy';

  process.env.MSSQL_HOST = 'localhost';
  process.env.MSSQL_PORT = '1433';
  process.env.MSSQL_DB = 'db_scada';
  process.env.MSSQL_USER = 'sa';
  process.env.MSSQL_PASSWORD = 'dummy';
});

describe('config boolean flags', () => {
  let cfg;

  beforeEach(() => {
    jest.resetModules();
    cfg = require('./index');
  });

  test('parseBool handles true/false/undefined correctly', () => {
    expect(typeof cfg.parseBool).toBe('function');
    expect(cfg.parseBool('true', false)).toBe(true);
    expect(cfg.parseBool('TRUE', false)).toBe(true);
    expect(cfg.parseBool('false', true)).toBe(false);
    expect(cfg.parseBool('FALSE', true)).toBe(false);
    expect(cfg.parseBool(undefined, true)).toBe(true);
    expect(cfg.parseBool(undefined, false)).toBe(false);
    expect(cfg.parseBool('junk', true)).toBe(true);
    expect(cfg.parseBool('junk', false)).toBe(false);
  });

  test('loadCronEnablementFromEnv returns expected booleans', () => {
    const env = {
      ENABLE_CONTROL_CRON: 'false',
      ENABLE_PLANNING_CRON: 'true',
      ENABLE_PROGRESS_CRON: 'true'
    };
    const res = cfg.loadCronEnablementFromEnv(env);
    expect(res).toEqual({ control: false, planning: true, progress: true });

    const env2 = {
      ENABLE_CONTROL_CRON: 'true',
      ENABLE_PLANNING_CRON: 'false',
      ENABLE_PROGRESS_CRON: 'false'
    };
    const res2 = cfg.loadCronEnablementFromEnv(env2);
    expect(res2).toEqual({ control: true, planning: false, progress: false });
  });
});