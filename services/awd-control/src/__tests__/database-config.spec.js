const mockState = { instances: [], queryImpl: () => Promise.resolve({ rows: [] }) };

jest.mock('pg', () => {
  const actual = jest.requireActual('pg');
  const createQuery = () => jest.fn((...args) => mockState.queryImpl(...args));
  const MockPool = jest.fn().mockImplementation(() => {
    const instance = {
      query: createQuery(),
      connect: jest.fn().mockResolvedValue({
        query: createQuery(),
        release: jest.fn(),
      }),
      end: jest.fn().mockResolvedValue(undefined),
    };
    mockState.instances.push(instance);
    return instance;
  });
  return { ...actual, Pool: MockPool };
});

const originalEnv = process.env;
let database;

describe('database config helpers', () => {
  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    mockState.instances.splice(0, mockState.instances.length);
    mockState.queryImpl = () => Promise.resolve({ rows: [] });
    database = require('../config/database');
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  test('buildPostgresConfig parses connection string', () => {
    process.env.POSTGRES_URL = 'postgresql://user:pass@localhost:5433/example';
    const cfg = database.buildPostgresConfig();

    expect(cfg.host).toBe('localhost');
    expect(cfg.port).toBe(5433);
    expect(cfg.user).toBe('user');
    expect(cfg.password).toBe('pass');
    expect(cfg.database).toBe('example');
  });

  test('buildTimescaleConfig applies ssl when enabled', () => {
    process.env.TIMESCALE_URL = 'postgresql://user:pass@host:5432/db';
    process.env.TIMESCALE_SSL = 'true';
    const cfg = database.buildTimescaleConfig();

    expect(cfg.ssl).toEqual({ rejectUnauthorized: false });
  });

  test('buildTimescaleConfig throws when url missing', () => {
    delete process.env.TIMESCALE_URL;

    expect(() => database.buildTimescaleConfig()).toThrow(/TIMESCALE_URL/);
  });

  test('verifyDatabaseConnections succeeds when queries pass', async () => {
    process.env.POSTGRES_URL = 'postgresql://user:pass@localhost:5432/example';
    process.env.TIMESCALE_URL = 'postgresql://user:pass@localhost:5432/example';

    await database.connectDatabases();
    await database.closeDatabases();

    expect(mockState.instances.length).toBeGreaterThan(0);
  });

  test('verifyDatabaseConnections surfaces query failures', async () => {
    jest.resetModules();
    process.env.POSTGRES_URL = 'postgresql://user:pass@localhost:5432/example';
    process.env.TIMESCALE_URL = 'postgresql://user:pass@localhost:5432/example';
    mockState.queryImpl = () => Promise.reject(new Error('boom'));
    const testModule = require('../test-connection');

    await expect(testModule.verifyDatabaseConnections()).rejects.toThrow('boom');
  });
});
