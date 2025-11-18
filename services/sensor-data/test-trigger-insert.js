// Test trigger by inserting a new water level reading
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

async function testTrigger() {
  try {
    console.log('=== TESTING REAL-TIME SMOOTHING TRIGGER ===\n');

    // 1. Insert a test reading
    const testTime = new Date();
    const insertResult = await pool.query(`
      INSERT INTO water_level_readings (
        time, sensor_id, level_cm, voltage, rssi, temperature, quality_score, location_lat, location_lng
      ) VALUES (
        $1, 'AWD-TEST', 16.5, 3.70, -45, 25.2, 1.00, 13.7563, 100.5014
      )
      RETURNING time, sensor_id, level_cm
    `, [testTime]);

    console.log('✓ Inserted test reading:');
    console.log(`  Time: ${insertResult.rows[0].time}`);
    console.log(`  Sensor: ${insertResult.rows[0].sensor_id}`);
    console.log(`  Level: ${insertResult.rows[0].level_cm} cm\n`);

    // 2. Wait a moment for trigger to execute
    await new Promise(resolve => setTimeout(resolve, 500));

    // 3. Check if smoothed record was created
    const smoothedCheck = await pool.query(`
      SELECT time, sensor_id, level_cm, quality_score
      FROM smoothed_water_level_readings
      WHERE sensor_id = 'AWD-TEST'
      AND time >= $1
      ORDER BY time DESC
      LIMIT 1
    `, [testTime]);

    if (smoothedCheck.rows.length > 0) {
      console.log('✅ SUCCESS! Trigger created smoothed record:');
      console.log(`  Time: ${smoothedCheck.rows[0].time}`);
      console.log(`  Level: ${smoothedCheck.rows[0].level_cm} cm`);
      console.log(`  Quality: ${smoothedCheck.rows[0].quality_score}\n`);
    } else {
      console.log('❌ FAILED! No smoothed record was created by trigger\n');

      // Check for errors in PostgreSQL logs or function issues
      console.log('Checking if function can be called manually...');

      // Try calling the function directly
      try {
        await pool.query(`
          SELECT fn_smooth_water_level_row()
        `);
        console.log('Function callable (but trigger may not be firing)');
      } catch (err) {
        console.log('Error calling function:', err.message);
      }
    }

    // 4. Clean up test data
    await pool.query(`
      DELETE FROM water_level_readings WHERE sensor_id = 'AWD-TEST'
    `);
    await pool.query(`
      DELETE FROM smoothed_water_level_readings WHERE sensor_id = 'AWD-TEST'
    `);

    console.log('✓ Test data cleaned up');

    console.log('\n=== TEST COMPLETE ===');

  } catch (error) {
    console.error('Error:', error.message);
    console.error(error.stack);
  } finally {
    await pool.end();
  }
}

testTrigger();
