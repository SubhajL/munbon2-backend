const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.TIMESCALE_HOST || 'localhost',
  port: parseInt(process.env.TIMESCALE_PORT || '5432'),
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || (() => { throw new Error('TIMESCALE_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })()
});

async function checkTriggerStatus() {
  try {
    // Check trigger
    const triggerResult = await pool.query(`
      SELECT
        trigger_name,
        event_object_table,
        action_timing,
        event_manipulation,
        action_orientation,
        action_statement
      FROM information_schema.triggers
      WHERE trigger_name = 'trigger_smooth_water_level'
    `);

    console.log('=== TRIGGER STATUS ===');
    if (triggerResult.rows.length > 0) {
      console.log('Trigger exists:');
      console.log(JSON.stringify(triggerResult.rows[0], null, 2));
    } else {
      console.log('❌ Trigger NOT FOUND');
    }

    // Check function
    const functionResult = await pool.query(`
      SELECT
        routine_name,
        routine_type,
        data_type
      FROM information_schema.routines
      WHERE routine_name = 'fn_smooth_water_level_row'
    `);

    console.log('\n=== FUNCTION STATUS ===');
    if (functionResult.rows.length > 0) {
      console.log('Function exists:');
      console.log(JSON.stringify(functionResult.rows[0], null, 2));
    } else {
      console.log('❌ Function NOT FOUND');
    }

    // Check recent data
    const recentDataResult = await pool.query(`
      SELECT
        'Raw readings (last hour)' AS table_name,
        COUNT(*) AS count,
        MAX(time) AS latest_time
      FROM water_level_readings
      WHERE time > NOW() - INTERVAL '1 hour'

      UNION ALL

      SELECT
        'Smoothed readings (last hour)' AS table_name,
        COUNT(*) AS count,
        MAX(time) AS latest_time
      FROM smoothed_water_level_readings
      WHERE time > NOW() - INTERVAL '1 hour'
    `);

    console.log('\n=== RECENT DATA ===');
    recentDataResult.rows.forEach(row => {
      console.log(`${row.table_name}: ${row.count} records, latest: ${row.latest_time}`);
    });

    // Check if trigger is on the correct table
    const triggerTableResult = await pool.query(`
      SELECT
        t.tgname AS trigger_name,
        c.relname AS table_name,
        p.proname AS function_name,
        pg_get_triggerdef(t.oid) AS trigger_definition
      FROM pg_trigger t
      JOIN pg_class c ON t.tgrelid = c.oid
      JOIN pg_proc p ON t.tgfoid = p.oid
      WHERE t.tgname = 'trigger_smooth_water_level'
    `);

    console.log('\n=== DETAILED TRIGGER INFO ===');
    if (triggerTableResult.rows.length > 0) {
      console.log('Trigger details:');
      console.log(JSON.stringify(triggerTableResult.rows[0], null, 2));
    } else {
      console.log('❌ No trigger found in pg_trigger');
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await pool.end();
  }
}

checkTriggerStatus();
