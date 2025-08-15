#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function checkStoredRainfallValues() {
    try {
        console.log('Checking Stored Rainfall Values in plot_water_demand_weekly');
        console.log('===========================================================');
        // Check a sample plot
        const query = `
      SELECT 
        crop_week,
        calendar_week,
        calendar_year,
        effective_rainfall_mm,
        created_at
      FROM ros.plot_water_demand_weekly
      WHERE plot_id = (SELECT plot_id FROM ros.plot_water_demand_weekly LIMIT 1)
        AND crop_type = 'rice' 
        AND calendar_year = 2025
        AND crop_week BETWEEN 1 AND 13
      ORDER BY crop_week;
    `;
        const result = await database_1.pool.query(query);
        console.log('Crop | Calendar | Stored Rainfall | Created At');
        console.log('Week | Week     | (mm)           |');
        console.log('-----|----------|----------------|------------');
        result.rows.forEach(row => {
            console.log(`  ${row.crop_week.toString().padStart(2)} | ` +
                `    ${row.calendar_week}    | ` +
                `${parseFloat(row.effective_rainfall_mm).toFixed(2).padStart(14)} | ` +
                `${new Date(row.created_at).toISOString().split('T')[0]}`);
        });
        // Check when the data was last updated
        const updateQuery = `
      SELECT 
        MIN(created_at) as first_created,
        MAX(created_at) as last_created
      FROM ros.plot_water_demand_weekly
      WHERE crop_type = 'rice' 
        AND calendar_year = 2025;
    `;
        const updateResult = await database_1.pool.query(updateQuery);
        console.log('\nData Creation Info:');
        console.log(`First created: ${new Date(updateResult.rows[0].first_created).toISOString()}`);
        console.log(`Last created: ${new Date(updateResult.rows[0].last_created).toISOString()}`);
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
checkStoredRainfallValues();
//# sourceMappingURL=check-stored-rainfall-values.js.map