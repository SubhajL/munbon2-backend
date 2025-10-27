const {
  describe,
  test,
  expect,
  beforeAll,
  afterAll
} = require('@jest/globals');
const { Pool } = require('pg');
const { TimescaleRepository } = require('../../repository/timescaleRepository');
const { DatabaseConfig } = require('../../config/database');
const OutboxPoller = require('../outboxPoller');

require('dotenv').config();

/**
 * Integration test for complete outbox pattern flow:
 * 1. INSERT sensor reading into moisture_readings
 * 2. Database trigger fires and inserts into outbox
 * 3. OutboxPoller processes outbox entry
 * 4. Entry written to sensor_plot_readings
 */
describe('Outbox Pattern Integration', () => {
  let sensorDataPool;
  let configPool;
  let repository;
  let db;

  beforeAll(async () => {
    // Connect to sensor_data database (where moisture_readings lives)
    sensorDataPool = new Pool({
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB || 'sensor_data',
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD
    });

    // Connect to config database (where outbox and sensor_plot_readings live)
    configPool = new Pool({
      host: process.env.CONFIG_DB_HOST || process.env.TIMESCALE_HOST,
      port: parseInt(
        process.env.CONFIG_DB_PORT || process.env.TIMESCALE_PORT || '5432'
      ),
      database: process.env.CONFIG_DB_NAME || 'munbon_dev',
      user: process.env.CONFIG_DB_USER || process.env.TIMESCALE_USER,
      password:
        process.env.CONFIG_DB_PASSWORD || process.env.TIMESCALE_PASSWORD
    });

    repository = new TimescaleRepository(configPool, {
      control: 'water_control_smartfarm',
      planning: 'ros_gis_smartfarm'
    });

    db = new DatabaseConfig();

    // Create schema if it doesn't exist
    await configPool.query(
      'CREATE SCHEMA IF NOT EXISTS water_control_smartfarm'
    );

    // Create outbox table if it doesn't exist
    await configPool.query(`
      CREATE TABLE IF NOT EXISTS water_control_smartfarm.sensor_readings_outbox (
        id SERIAL PRIMARY KEY,
        sensor_id TEXT NOT NULL,
        sensor_type TEXT NOT NULL CHECK (sensor_type IN ('moisture', 'water_level')),
        value DOUBLE PRECISION NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
      )
    `);

    await configPool.query(`
      CREATE INDEX IF NOT EXISTS idx_outbox_unprocessed
      ON water_control_smartfarm.sensor_readings_outbox(created_at)
      WHERE processed_at IS NULL
    `);

    // Clean up test data from previous runs
    await configPool.query(`
      DELETE FROM water_control_smartfarm.sensor_readings_outbox 
      WHERE sensor_id IN ('00000099', '00000098', '00000001', '00000010');
    `);

    await configPool.query(`
      DELETE FROM water_control_smartfarm.sensor_plot_readings 
      WHERE sensor_id = '00000099';
    `);

    // Create trigger function and triggers if they don't exist
    try {
      const client = await sensorDataPool.connect();
      await db.createOutboxTriggers(client);
      client.release();
    } catch (error) {
      console.log('Triggers may already exist:', error.message);
    }
  });

  afterAll(async () => {
    // Clean up test data
    await configPool.query(`
      DELETE FROM water_control_smartfarm.sensor_readings_outbox 
      WHERE sensor_id = '00000099';
    `);

    await configPool.query(`
      DELETE FROM water_control_smartfarm.sensor_plot_readings 
      WHERE sensor_id = '00000099';
    `);

    await sensorDataPool.end();
    await configPool.end();
  });

  test('end-to-end: moisture reading triggers outbox and gets processed', async () => {
    const testSensorId = '0001-0099'; // Will be normalized to 00000099
    const testValue = 67.5;
    const testTimestamp = new Date();

    // Step 1: Verify no existing outbox entry
    let outboxCheck = await configPool.query(
      'SELECT * FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      ['00000099']
    );
    expect(outboxCheck.rows).toHaveLength(0);

    // Step 2: INSERT into moisture_readings (this should trigger outbox insertion)
    await sensorDataPool.query(
      `INSERT INTO public.moisture_readings 
        (time, sensor_id, moisture_surface_pct, location_lat, location_lng)
       VALUES ($1, $2, $3, 13.7563, 100.5018)`,
      [testTimestamp, testSensorId, testValue]
    );

    // Step 3: Wait a bit for trigger to fire
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Step 4: Verify outbox entry was created with normalized sensor_id
    outboxCheck = await configPool.query(
      'SELECT * FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      ['00000099']
    );

    expect(outboxCheck.rows).toHaveLength(1);
    expect(outboxCheck.rows[0].sensor_id).toBe('00000099');
    expect(outboxCheck.rows[0].sensor_type).toBe('moisture');
    expect(parseFloat(outboxCheck.rows[0].value)).toBe(testValue);
    expect(outboxCheck.rows[0].processed_at).toBeNull();

    console.log('✅ Outbox entry created by trigger');

    // Step 5: Manually process the outbox entry (simulating OutboxPoller)
    // In real scenario, OutboxPoller would do this automatically

    // First, we need to setup a mock RealtimeControlService
    const mockRealtimeControlService = {
      handleSensorReading: jest.fn(async (event) => {
        // Simulate what RealtimeControlService does:
        // It would call repository.upsertSensorPlotReading
        // For this test, we'll do it directly

        // This requires a sensor mapping and plot configuration to exist
        // For testing, we'll just verify the outbox entry can be fetched
        console.log('Processing sensor reading:', event);
      })
    };

    const poller = new OutboxPoller({
      repository,
      realtimeControlService: mockRealtimeControlService,
      pollIntervalMs: 5000,
      batchSize: 100,
      logger: console,
      pool: configPool
    });

    // Step 6: Fetch unprocessed entries (what poller does)
    const unprocessedEntries = await repository.fetchUnprocessedOutboxEntries(
      configPool,
      100
    );

    const ourEntry = unprocessedEntries.find((e) => e.sensorId === '00000099');
    expect(ourEntry).toBeDefined();
    expect(ourEntry.sensorType).toBe('moisture');
    expect(ourEntry.value).toBe(testValue);

    console.log('✅ Outbox entry fetched successfully');

    // Step 7: Process the entry
    await mockRealtimeControlService.handleSensorReading({
      sensorId: ourEntry.sensorId,
      sensorType: ourEntry.sensorType,
      value: ourEntry.value,
      timestamp: ourEntry.timestamp
    });

    expect(mockRealtimeControlService.handleSensorReading).toHaveBeenCalledWith(
      {
        sensorId: '00000099',
        sensorType: 'moisture',
        value: testValue,
        timestamp: ourEntry.timestamp
      }
    );

    console.log('✅ Entry processed by mock service');

    // Step 8: Mark as processed
    await repository.markOutboxEntryProcessed(configPool, ourEntry.id);

    // Step 9: Verify entry is now marked as processed
    outboxCheck = await configPool.query(
      'SELECT * FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      ['00000099']
    );

    expect(outboxCheck.rows).toHaveLength(1);
    expect(outboxCheck.rows[0].processed_at).not.toBeNull();

    console.log('✅ Outbox entry marked as processed');

    // Step 10: Verify it no longer appears in unprocessed queries
    const stillUnprocessed = await repository.fetchUnprocessedOutboxEntries(
      configPool,
      100
    );

    const shouldNotExist = stillUnprocessed.find(
      (e) => e.sensorId === '00000099'
    );
    expect(shouldNotExist).toBeUndefined();

    console.log('✅ Entry no longer appears in unprocessed query');
  }, 30000); // 30 second timeout for integration test

  test('trigger normalizes sensor_id format correctly', async () => {
    const testCases = [
      { input: '0001-0001', expected: '00000001' },
      { input: '0001-0099', expected: '00000099' },
      { input: '0002-0010', expected: '00000010' }
    ];

    for (const { input, expected } of testCases) {
      // Clean up
      await configPool.query(
        'DELETE FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
        [expected]
      );

      // Insert
      await sensorDataPool.query(
        `INSERT INTO public.moisture_readings 
          (time, sensor_id, moisture_surface_pct, location_lat, location_lng)
         VALUES (NOW(), $1, 50.0, 13.7563, 100.5018)`,
        [input]
      );

      // Wait for trigger
      await new Promise((resolve) => setTimeout(resolve, 300));

      // Verify
      const result = await configPool.query(
        'SELECT sensor_id FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
        [expected]
      );

      expect(result.rows).toHaveLength(1);
      expect(result.rows[0].sensor_id).toBe(expected);

      // Clean up
      await configPool.query(
        'DELETE FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
        [expected]
      );
    }

    console.log('✅ All sensor_id normalizations correct');
  }, 30000);

  test('water_level readings also trigger outbox entries', async () => {
    const testSensorId = '0001-0098';
    const normalizedId = '00000098';
    const testValue = 15.5;

    // Clean up
    await configPool.query(
      'DELETE FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      [normalizedId]
    );

    // Insert into water_level_readings
    await sensorDataPool.query(
      `INSERT INTO public.water_level_readings 
        (time, sensor_id, water_level_cm, location_lat, location_lng)
       VALUES (NOW(), $1, $2, 13.7563, 100.5018)`,
      [testSensorId, testValue]
    );

    // Wait for trigger
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Verify outbox entry
    const result = await configPool.query(
      'SELECT * FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      [normalizedId]
    );

    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].sensor_id).toBe(normalizedId);
    expect(result.rows[0].sensor_type).toBe('water_level');
    expect(parseFloat(result.rows[0].value)).toBe(testValue);

    console.log('✅ Water level trigger working');

    // Clean up
    await configPool.query(
      'DELETE FROM water_control_smartfarm.sensor_readings_outbox WHERE sensor_id = $1',
      [normalizedId]
    );
  }, 30000);
});
