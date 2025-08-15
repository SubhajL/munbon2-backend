#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function revertSeptemberRainfall() {
    try {
        // Revert September back to 233.20 mm as per Excel
        const updateQuery = `
      UPDATE ros.effective_rainfall_monthly
      SET effective_rainfall_mm = 233.20,
          updated_at = NOW()
      WHERE aos_station = 'นครราชสีมา'
        AND province = 'นครราชสีมา' 
        AND crop_type = 'rice'
        AND month = 9;
    `;
        await database_1.pool.query(updateQuery);
        console.log('Reverted September rainfall to 233.20 mm/month (as per Excel)');
        // Verify the update
        const verifyQuery = `
      SELECT month, effective_rainfall_mm,
        effective_rainfall_mm / 30 as daily_mm,
        (effective_rainfall_mm / 30) * 7 as weekly_mm
      FROM ros.effective_rainfall_monthly
      WHERE crop_type = 'rice' AND month = 9;
    `;
        const result = await database_1.pool.query(verifyQuery);
        const row = result.rows[0];
        console.log('\nVerification:');
        console.log(`Monthly: ${row.effective_rainfall_mm} mm`);
        console.log(`Daily: ${parseFloat(row.daily_mm).toFixed(3)} mm`);
        console.log(`Weekly: ${parseFloat(row.weekly_mm).toFixed(2)} mm`);
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
revertSeptemberRainfall();
//# sourceMappingURL=revert-september-rainfall.js.map