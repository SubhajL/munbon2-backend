// Recreate the real-time smoothing trigger
require('dotenv').config();
const { Pool } = require('pg');
const fs = require('fs');

const pool = new Pool({
  host: process.env.TIMESCALE_HOST,
  port: parseInt(process.env.TIMESCALE_PORT),
  database: process.env.TIMESCALE_DB,
  user: process.env.TIMESCALE_USER,
  password: process.env.TIMESCALE_PASSWORD,
  ssl: false
});

async function recreateTrigger() {
  try {
    console.log('=== RECREATING REAL-TIME SMOOTHING TRIGGER ===\n');

    // Read the SQL file
    const sql = fs.readFileSync('sql/water-level/07_realtime_smoothing_fn_and_trigger.sql', 'utf8');

    // Execute the SQL
    await pool.query(sql);

    console.log('✓ Trigger and function recreated successfully\n');

    // Verify
    const verifyTrigger = await pool.query(`
      SELECT trigger_name, event_object_table
      FROM information_schema.triggers
      WHERE trigger_name = 'trigger_smooth_water_level'
    `);

    if (verifyTrigger.rows.length > 0) {
      console.log('✓ Trigger verified:', verifyTrigger.rows[0].trigger_name);
    } else {
      console.log('❌ Trigger not found after creation!');
    }

    console.log('\n=== DONE ===');

  } catch (error) {
    console.error('Error:', error.message);
    console.error(error.stack);
  } finally {
    await pool.end();
  }
}

recreateTrigger();
