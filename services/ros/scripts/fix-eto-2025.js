#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function fixETo2025Data() {
    try {
        // Delete incorrect values first
        await database_1.pool.query(`
      DELETE FROM ros.eto_weekly 
      WHERE calendar_year = 2025 AND calendar_week BETWEEN 26 AND 39;
    `);
        // Insert correct values
        const query = `
      INSERT INTO ros.eto_weekly (aos_station, province, calendar_week, calendar_year, month, eto_value) VALUES
      -- Land prep week
      ('นครราชสีมา', 'นครราชสีมา', 26, 2025, 6, 43.36),   -- Land prep week
      -- July 2025 weeks - same as 2024
      ('นครราชสีมา', 'นครราชสีมา', 27, 2025, 7, 42.77),  -- Crop week 1 (RID week 36)
      ('นครราชสีมา', 'นครราชสีมา', 28, 2025, 7, 33.13),  -- Crop week 2 (RID week 37)
      ('นครราชสีมา', 'นครราชสีมา', 29, 2025, 7, 33.13),  -- Crop week 3 (RID week 38)
      ('นครราชสีมา', 'นครราชสีมา', 30, 2025, 7, 33.13),  -- Crop week 4 (RID week 39)
      -- August 2025 weeks
      ('นครราชสีมา', 'นครราชสีมา', 31, 2025, 8, 31.04),  -- Crop week 5 (RID week 40)
      ('นครราชสีมา', 'นครราชสีมา', 32, 2025, 8, 31.04),  -- Crop week 6 (RID week 41)
      ('นครราชสีมา', 'นครราชสีมา', 33, 2025, 8, 31.04),  -- Crop week 7 (RID week 42)
      ('นครราชสีมา', 'นครราชสีมา', 34, 2025, 8, 31.04),  -- Crop week 8 (RID week 43)
      -- September 2025 weeks
      ('นครราชสีมา', 'นครราชสีมา', 35, 2025, 9, 28.50),  -- Crop week 9 (RID week 44)
      ('นครราชสีมา', 'นครราชสีมา', 36, 2025, 9, 28.50),  -- Crop week 10 (RID week 45)
      ('นครราชสีมา', 'นครราชสีมา', 37, 2025, 9, 28.50),  -- Crop week 11 (RID week 46)
      ('นครราชสีมา', 'นครราชสีมา', 38, 2025, 9, 28.50),  -- Crop week 12 (RID week 47)
      ('นครราชสีมา', 'นครราชสีมา', 39, 2025, 9, 28.50);  -- Crop week 13 (RID week 48)
    `;
        await database_1.pool.query(query);
        console.log('Successfully fixed ETo data for 2025');
        // Verify the data
        const verifyQuery = `
      SELECT calendar_week, calendar_year, month, eto_value
      FROM ros.eto_weekly
      WHERE calendar_year = 2025 AND calendar_week BETWEEN 26 AND 39
      ORDER BY calendar_week;
    `;
        const result = await database_1.pool.query(verifyQuery);
        console.log('\n2025 ETo data (fixed):');
        console.log('Week | Year | Month | ETo');
        console.log('-----|------|-------|-------');
        result.rows.forEach(row => {
            console.log(`  ${row.calendar_week}  | ${row.calendar_year} |   ${row.month}   | ${row.eto_value}`);
        });
        process.exit(0);
    }
    catch (error) {
        console.error('Error fixing ETo data:', error);
        process.exit(1);
    }
}
fixETo2025Data();
//# sourceMappingURL=fix-eto-2025.js.map