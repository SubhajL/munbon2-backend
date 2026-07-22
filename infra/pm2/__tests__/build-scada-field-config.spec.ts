import * as path from 'path';
import { getScadaFieldProcesses } from '../build-scada-field-config';

const repoRoot = path.resolve(__dirname, '../../..');

describe('getScadaFieldProcesses', () => {
  const requiredEnv = {
    DATABASE_URL: 'postgresql://operator:secret@db.test/munbon',
    JWT_SECRET: 'operator-jwt-secret',
    MODBUS_HOST: 'field-plc.test',
  };
  const saved: Record<string, string | undefined> = {};

  beforeAll(() => {
    for (const [name, value] of Object.entries(requiredEnv)) {
      saved[name] = process.env[name];
      process.env[name] = value;
    }
  });

  afterAll(() => {
    for (const name of Object.keys(requiredEnv)) {
      if (saved[name] === undefined) delete process.env[name];
      else process.env[name] = saved[name];
    }
  });

  test('registers only the dedicated SCADA gate-control process with machine commands dark', () => {
    expect(getScadaFieldProcesses()).toEqual([
      expect.objectContaining({
        name: 'scada-gate-control',
        script: 'dist/index.js',
        cwd: path.join(repoRoot, 'services', 'scada-gate-control'),
        autorestart: true,
        env: expect.objectContaining({
          ALLOW_MACHINE_COMMANDS: 'false',
          DATABASE_URL: requiredEnv.DATABASE_URL,
          JWT_SECRET: requiredEnv.JWT_SECRET,
          MODBUS_HOST: requiredEnv.MODBUS_HOST,
          PORT: '3030',
        }),
      }),
    ]);
    expect(getScadaFieldProcesses().map(process => process.name)).not.toContain('scada-service');
  });

  test.each(Object.keys(requiredEnv))('fails closed when %s is absent', name => {
    const previous = process.env[name];
    delete process.env[name];
    try {
      expect(() => getScadaFieldProcesses()).toThrow(`${name} must be set`);
    } finally {
      process.env[name] = previous;
    }
  });
});
