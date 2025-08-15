#!/usr/bin/env ts-node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
async function checkETo2024() {
    try {
        const query = `
      SELECT calendar_week, calendar_year, month, eto_value
      FROM ros.eto_weekly
      WHERE calendar_year = 2024 AND calendar_week BETWEEN 27 AND 39
      ORDER BY calendar_week;
    `;
        const result = await database_1.pool.query(query);
        console.log('2024 ETo data (weeks 27-39):');
        console.log('Week | Year | Month | ETo');
        console.log('-----|------|-------|-------');
        result.rows.forEach(row => {
            console.log(`  ${row.calendar_week}  | ${row.calendar_year} |   ${row.month}   | ${row.eto_value}`);
        });
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
checkETo2024();
//# sourceMappingURL=check-eto-2024.js.map