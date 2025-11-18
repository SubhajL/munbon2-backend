// Verify real-time smoothing trigger using the app's database config
require('dotenv').config();
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.TIMESCALE_HOST,
  port: parseInt(process.env.TIMESCALE_PORT),
  database: process.env.TIMESCALE_DB,
  user: process.env.TIMESCALE_USER,
  password: process.env.TIMESCALE_PASSWORD,
  ssl: false
});

async function verifyTrigger() {
  try {
    console.log('===  TRIGGER VERIFICATION ===\n');

    // 1. Check if trigger exists
    const triggerCheck = await pool.query(`
      SELECT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trigger_smooth_water_level'
      ) as exists
    `);

    console.log('✓ Trigger exists:', triggerCheck.rows[0].exists);

    // 2. Check if function exists
    const functionCheck = await pool.query(`
      SELECT EXISTS (
        SELECT 1 FROM information_schema.routines
        WHERE routine_name = 'fn_smooth_water_level_row'
      ) as exists
    `);

    console.log('✓ Function exists:', functionCheck.rows[0].exists);

    // 3. Check smoothed table exists and has data
    const tableCheck = await pool.query(`
      SELECT COUNT(*) as count FROM smoothed_water_level_readings
    `);

    console.log('✓ Smoothed table total rows:', tableCheck.rows[0].count);

    // 4. Check recent data in both tables
    const recentData = await pool.query(`
      SELECT
        'Raw (last hour)' AS source,
        COUNT(*) AS count,
        MAX(time) AS latest_time
      FROM water_level_readings
      WHERE time > NOW() - INTERVAL '1 hour'

      UNION ALL

      SELECT
        'Smoothed (last hour)' AS source,
        COUNT(*) AS count,
        MAX(time) AS latest_time
      FROM smoothed_water_level_readings
      WHERE time > NOW() - INTERVAL '1 hour'
    `);

    console.log('\nRecent data:');
    recentData.rows.forEach(row => {
      console.log(`  ${row.source}: ${row.count} records, latest: ${row.latest_time || 'N/A'}`);
    });

    //5. Get trigger definition
    const triggerDef = await pool.query(`
      SELECT pg_get_triggerdef(oid) as definition
      FROM pg_trigger
      WHERE tgname = 'trigger_smooth_water_level'
    `);

    if (triggerDef.rows.length > 0) {
      console.log('\n✓ Trigger definition:', triggerDef.rows[0].definition);
    }

    console.log('\n=== VERIFICATION COMPLETE ===');

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await pool.end();
  }
}

verifyTrigger();
