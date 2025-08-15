#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../src/config/database");
const dayjs_1 = __importDefault(require("dayjs"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
dayjs_1.default.extend(weekOfYear_1.default);
async function debugSeptemberRainfall() {
    try {
        console.log('Debug September Rainfall Calculation');
        console.log('====================================');
        // Check calendar weeks 36-39 (which should be in September)
        for (let calWeek = 36; calWeek <= 39; calWeek++) {
            const weekDate = (0, dayjs_1.default)().year(2025).week(calWeek);
            const month = weekDate.month() + 1;
            const startOfWeek = weekDate.startOf('week');
            const endOfWeek = weekDate.endOf('week');
            console.log(`\nCalendar Week ${calWeek}:`);
            console.log(`- Week start: ${startOfWeek.format('YYYY-MM-DD')} (Month: ${startOfWeek.month() + 1})`);
            console.log(`- Week end: ${endOfWeek.format('YYYY-MM-DD')} (Month: ${endOfWeek.month() + 1})`);
            console.log(`- Primary month: ${month}`);
            // Check if week spans months
            if (startOfWeek.month() !== endOfWeek.month()) {
                console.log(`- Week spans months: ${startOfWeek.month() + 1} and ${endOfWeek.month() + 1}`);
            }
        }
        // Check what our service would calculate
        console.log('\n\nChecking Service Logic:');
        console.log('======================');
        // Simulate the service logic
        for (let calWeek = 35; calWeek <= 39; calWeek++) {
            const weekDate = (0, dayjs_1.default)().year(2025).week(calWeek);
            const month = weekDate.month() + 1;
            const weekStart = weekDate.startOf('week');
            const weekEnd = weekDate.endOf('week');
            const spansMonths = weekStart.month() !== weekEnd.month();
            let effectiveMonth = month;
            if (spansMonths) {
                effectiveMonth = weekEnd.month() + 1; // Use next month's rainfall
            }
            // Get rainfall for effective month
            const query = `
        SELECT effective_rainfall_mm 
        FROM ros.effective_rainfall_monthly
        WHERE month = $1 AND crop_type = 'rice'
        AND aos_station = 'นครราชสีมา';
      `;
            const result = await database_1.pool.query(query, [effectiveMonth]);
            const monthlyRainfall = parseFloat(result.rows[0]?.effective_rainfall_mm || '0');
            const daysInMonth = effectiveMonth === 2 ? 28 : [4, 6, 9, 11].includes(effectiveMonth) ? 30 : 31;
            const weeklyRainfall = (monthlyRainfall / daysInMonth) * 7;
            console.log(`\nWeek ${calWeek}:`);
            console.log(`- Spans months: ${spansMonths}`);
            console.log(`- Effective month: ${effectiveMonth}`);
            console.log(`- Monthly rainfall: ${monthlyRainfall.toFixed(2)} mm`);
            console.log(`- Weekly rainfall: ${weeklyRainfall.toFixed(2)} mm`);
        }
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
debugSeptemberRainfall();
//# sourceMappingURL=debug-september-rainfall.js.map