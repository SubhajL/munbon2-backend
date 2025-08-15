#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function checkSeptemberRainfall() {
    try {
        // Check effective rainfall for September
        const query = `
      SELECT month, effective_rainfall_mm, crop_type
      FROM ros.effective_rainfall_monthly
      WHERE month = 9 AND crop_type = 'rice'
      ORDER BY month;
    `;
        const result = await database_1.pool.query(query);
        console.log('September Effective Rainfall Data:');
        result.rows.forEach(row => {
            console.log(`Month ${row.month}: ${row.effective_rainfall_mm} mm (${row.crop_type})`);
        });
        // Calculate weekly from monthly
        const septemberRainfall = result.rows[0]?.effective_rainfall_mm || 0;
        const dailyRainfall = septemberRainfall / 30; // September has 30 days
        const weeklyRainfall = dailyRainfall * 7;
        console.log('\nCalculation:');
        console.log(`Monthly: ${septemberRainfall} mm`);
        console.log(`Daily: ${dailyRainfall.toFixed(3)} mm`);
        console.log(`Weekly: ${weeklyRainfall.toFixed(2)} mm`);
        console.log(`\nExcel shows: 29.16 mm/week for September`);
        console.log(`Our system shows: ${weeklyRainfall.toFixed(2)} mm/week`);
        // Check all months
        console.log('\nAll Monthly Effective Rainfall:');
        const allQuery = `
      SELECT month, effective_rainfall_mm
      FROM ros.effective_rainfall_monthly
      WHERE crop_type = 'rice'
      ORDER BY month;
    `;
        const allResult = await database_1.pool.query(allQuery);
        allResult.rows.forEach(row => {
            const days = row.month === 2 ? 28 :
                [4, 6, 9, 11].includes(row.month) ? 30 : 31;
            const weekly = (row.effective_rainfall_mm / days * 7);
            console.log(`Month ${row.month}: ${row.effective_rainfall_mm} mm/month = ${weekly.toFixed(2)} mm/week`);
        });
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
checkSeptemberRainfall();
//# sourceMappingURL=check-september-rainfall.js.map