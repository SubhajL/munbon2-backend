#!/usr/bin/env ts-node

import { pool } from '../src/config/database';

async function fixSeptemberRainfall() {
  try {
    // Excel shows 29.16 mm/week for September
    // Daily = 29.16 / 7 = 4.166 mm/day
    // Monthly = 4.166 * 30 = 124.98 mm
    
    const updateQuery = `
      UPDATE ros.effective_rainfall_monthly
      SET effective_rainfall_mm = 124.98,
          updated_at = NOW()
      WHERE aos_station = 'นครราชสีมา'
        AND province = 'นครราชสีมา' 
        AND crop_type = 'rice'
        AND month = 9;
    `;
    
    await pool.query(updateQuery);
    console.log('Updated September rainfall to 124.98 mm/month');
    
    // Verify the update
    const verifyQuery = `
      SELECT month, effective_rainfall_mm,
        effective_rainfall_mm / 30 as daily_mm,
        (effective_rainfall_mm / 30) * 7 as weekly_mm
      FROM ros.effective_rainfall_monthly
      WHERE crop_type = 'rice' AND month = 9;
    `;
    
    const result = await pool.query(verifyQuery);
    const row = result.rows[0];
    console.log('\nVerification:');
    console.log(`Monthly: ${row.effective_rainfall_mm} mm`);
    console.log(`Daily: ${parseFloat(row.daily_mm).toFixed(3)} mm`);
    console.log(`Weekly: ${parseFloat(row.weekly_mm).toFixed(2)} mm`);
    console.log(`Excel target: 29.16 mm/week`);
    
    process.exit(0);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

fixSeptemberRainfall();