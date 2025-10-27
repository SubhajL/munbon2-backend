const {
  describe,
  test,
  expect,
  beforeEach,
  afterEach
} = require('@jest/globals');
const { Pool } = require('pg');
const { TimescaleRepository } = require('../timescaleRepository');

require('dotenv').config();

const testConfig = {
  host: process.env.TIMESCALE_HOST || 'localhost',
  port: parseInt(process.env.TIMESCALE_PORT || '5432'),
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres'
};

describe('TimescaleRepository - Outbox', () => {
  let pool;
  let repository;

  beforeEach(async () => {
    pool = new Pool(testConfig);
    repository = new TimescaleRepository(pool);

    // Create outbox table for tests
    await pool.query(`
      CREATE TABLE IF NOT EXISTS water_control_smartfarm.sensor_readings_outbox (
        id SERIAL PRIMARY KEY,
        sensor_id TEXT NOT NULL,
        sensor_type TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
      )
    `);

    // Clean outbox table
    await pool.query(
      'TRUNCATE water_control_smartfarm.sensor_readings_outbox RESTART IDENTITY'
    );
  });

  afterEach(async () => {
    await pool.end();
  });

  describe('fetchUnprocessedOutboxEntries', () => {
    test('returns unprocessed rows only', async () => {
      // Insert processed and unprocessed entries
      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), NOW()),
          ('00000002', 'moisture', 50.0, NOW(), NULL),
          ('00000003', 'water_level', 30.0, NOW(), NULL)
      `);

      const entries = await repository.fetchUnprocessedOutboxEntries(pool);

      expect(entries).toHaveLength(2);
      expect(entries.every((e) => e.processedAt === null)).toBe(true);
      expect(entries.map((e) => e.sensorId).sort()).toEqual([
        '00000002',
        '00000003'
      ]);
    });

    test('respects limit parameter', async () => {
      // Insert 150 unprocessed rows
      const values = Array.from(
        { length: 150 },
        (_, i) =>
          `('sensor${i.toString().padStart(8, '0')}', 'moisture', ${40 + i}, NOW(), NULL)`
      ).join(',');

      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ${values}
      `);

      const entries = await repository.fetchUnprocessedOutboxEntries(pool, 100);

      expect(entries).toHaveLength(100);
    });

    test('returns oldest entries first', async () => {
      // Insert entries with different timestamps
      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, created_at, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), NOW() - INTERVAL '3 minutes', NULL),
          ('00000002', 'moisture', 50.0, NOW(), NOW() - INTERVAL '1 minute', NULL),
          ('00000003', 'water_level', 30.0, NOW(), NOW() - INTERVAL '2 minutes', NULL)
      `);

      const entries = await repository.fetchUnprocessedOutboxEntries(pool);

      expect(entries).toHaveLength(3);
      expect(entries[0].sensorId).toBe('00000001');
      expect(entries[1].sensorId).toBe('00000003');
      expect(entries[2].sensorId).toBe('00000002');
    });

    test('returns empty array when no unprocessed entries', async () => {
      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ('00000001', 'moisture', 45.5, NOW(), NOW())
      `);

      const entries = await repository.fetchUnprocessedOutboxEntries(pool);

      expect(entries).toEqual([]);
    });
  });

  describe('markOutboxEntryProcessed', () => {
    test('sets processed_at timestamp', async () => {
      const insertResult = await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ('00000001', 'moisture', 45.5, NOW(), NULL)
        RETURNING id
      `);
      const outboxId = insertResult.rows[0].id;
      const processedAt = new Date('2025-10-23T10:00:00Z');

      await repository.markOutboxEntryProcessed(pool, outboxId, processedAt);

      const result = await pool.query(
        'SELECT processed_at FROM water_control_smartfarm.sensor_readings_outbox WHERE id = $1',
        [outboxId]
      );

      expect(result.rows[0].processed_at).toEqual(processedAt);
    });

    test('is idempotent', async () => {
      const insertResult = await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ('00000001', 'moisture', 45.5, NOW(), NULL)
        RETURNING id
      `);
      const outboxId = insertResult.rows[0].id;

      await repository.markOutboxEntryProcessed(pool, outboxId);
      await expect(
        repository.markOutboxEntryProcessed(pool, outboxId)
      ).resolves.not.toThrow();
    });

    test('uses current time when processedAt not provided', async () => {
      const insertResult = await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ('00000001', 'moisture', 45.5, NOW(), NULL)
        RETURNING id
      `);
      const outboxId = insertResult.rows[0].id;
      const before = new Date();

      await repository.markOutboxEntryProcessed(pool, outboxId);

      const result = await pool.query(
        'SELECT processed_at FROM water_control_smartfarm.sensor_readings_outbox WHERE id = $1',
        [outboxId]
      );
      const after = new Date();

      expect(result.rows[0].processed_at.getTime()).toBeGreaterThanOrEqual(
        before.getTime()
      );
      expect(result.rows[0].processed_at.getTime()).toBeLessThanOrEqual(
        after.getTime()
      );
    });
  });

  describe('insertOutboxEntry', () => {
    test('creates new outbox row', async () => {
      const entry = {
        sensorId: '00000001',
        sensorType: 'moisture',
        value: 45.5,
        timestamp: new Date('2025-10-23T10:00:00Z')
      };

      const outboxId = await repository.insertOutboxEntry(pool, entry);

      expect(outboxId).toBeGreaterThan(0);

      const result = await pool.query(
        'SELECT * FROM water_control_smartfarm.sensor_readings_outbox WHERE id = $1',
        [outboxId]
      );

      expect(result.rows).toHaveLength(1);
      expect(result.rows[0].sensor_id).toBe(entry.sensorId);
      expect(result.rows[0].sensor_type).toBe(entry.sensorType);
      expect(parseFloat(result.rows[0].value)).toBe(entry.value);
      expect(result.rows[0].timestamp).toEqual(entry.timestamp);
      expect(result.rows[0].processed_at).toBeNull();
    });
  });

  describe('deleteProcessedOutboxEntries', () => {
    test('deletes only processed entries older than threshold', async () => {
      const oldDate = new Date('2025-10-15T10:00:00Z');
      const recentDate = new Date('2025-10-22T10:00:00Z');

      // Insert mix of old processed, recent processed, and unprocessed
      await pool.query(
        `
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), $1),
          ('00000002', 'moisture', 50.0, NOW(), $2),
          ('00000003', 'moisture', 55.0, NOW(), NULL),
          ('00000004', 'water_level', 30.0, NOW(), $1)
      `,
        [oldDate, recentDate]
      );

      const cutoffDate = new Date('2025-10-20T00:00:00Z');
      const deletedCount = await repository.deleteProcessedOutboxEntries(
        pool,
        cutoffDate
      );

      expect(deletedCount).toBe(2);

      const remaining = await pool.query(
        'SELECT * FROM water_control_smartfarm.sensor_readings_outbox ORDER BY sensor_id'
      );

      expect(remaining.rows).toHaveLength(2);
      expect(remaining.rows[0].sensor_id).toBe('00000002');
      expect(remaining.rows[1].sensor_id).toBe('00000003');
    });

    test('returns correct count of deleted entries', async () => {
      const oldDate = new Date('2025-10-01T10:00:00Z');

      // Insert 10 old processed entries
      for (let i = 0; i < 10; i++) {
        await pool.query(
          `INSERT INTO water_control_smartfarm.sensor_readings_outbox
            (sensor_id, sensor_type, value, timestamp, processed_at)
          VALUES ($1, 'moisture', 45.5, NOW(), $2)`,
          [`sensor${i.toString().padStart(8, '0')}`, oldDate]
        );
      }

      const cutoffDate = new Date('2025-10-20T00:00:00Z');
      const deletedCount = await repository.deleteProcessedOutboxEntries(
        pool,
        cutoffDate
      );

      expect(deletedCount).toBe(10);
    });

    test('leaves unprocessed entries untouched', async () => {
      const oldDate = new Date('2025-10-01T10:00:00Z');

      await pool.query(
        `
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), NULL),
          ('00000002', 'moisture', 50.0, NOW(), $1)
      `,
        [oldDate]
      );

      const cutoffDate = new Date('2025-10-20T00:00:00Z');
      await repository.deleteProcessedOutboxEntries(pool, cutoffDate);

      const remaining = await pool.query(
        'SELECT * FROM water_control_smartfarm.sensor_readings_outbox'
      );

      expect(remaining.rows).toHaveLength(1);
      expect(remaining.rows[0].sensor_id).toBe('00000001');
      expect(remaining.rows[0].processed_at).toBeNull();
    });

    test('returns zero when no entries match criteria', async () => {
      const recentDate = new Date('2025-10-22T10:00:00Z');

      await pool.query(
        `INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES ('00000001', 'moisture', 45.5, NOW(), $1)`,
        [recentDate]
      );

      const cutoffDate = new Date('2025-10-20T00:00:00Z');
      const deletedCount = await repository.deleteProcessedOutboxEntries(
        pool,
        cutoffDate
      );

      expect(deletedCount).toBe(0);
    });
  });

  describe('getOutboxBacklogCount', () => {
    test('returns correct count of unprocessed entries', async () => {
      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), NULL),
          ('00000002', 'moisture', 50.0, NOW(), NOW()),
          ('00000003', 'water_level', 30.0, NOW(), NULL),
          ('00000004', 'water_level', 35.0, NOW(), NOW())
      `);

      const count = await repository.getOutboxBacklogCount(pool);

      expect(count).toBe(2);
    });

    test('returns zero when all entries processed', async () => {
      await pool.query(`
        INSERT INTO water_control_smartfarm.sensor_readings_outbox
          (sensor_id, sensor_type, value, timestamp, processed_at)
        VALUES
          ('00000001', 'moisture', 45.5, NOW(), NOW()),
          ('00000002', 'moisture', 50.0, NOW(), NOW())
      `);

      const count = await repository.getOutboxBacklogCount(pool);

      expect(count).toBe(0);
    });

    test('returns zero when table is empty', async () => {
      const count = await repository.getOutboxBacklogCount(pool);

      expect(count).toBe(0);
    });
  });
});
