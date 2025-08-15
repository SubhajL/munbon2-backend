#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const dayjs_1 = __importDefault(require("dayjs"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
dayjs_1.default.extend(weekOfYear_1.default);
// RID week 1 starts on November 1 of previous year
const ridWeek1Start = (0, dayjs_1.default)('2024-11-01');
console.log('RID Week 1 starts:', ridWeek1Start.format('YYYY-MM-DD (dddd)'));
// Calculate RID week 36 (35 weeks after week 1)
const ridWeek36Start = ridWeek1Start.add(35, 'week');
console.log('RID Week 36 starts:', ridWeek36Start.format('YYYY-MM-DD (dddd)'));
// Calculate crop weeks 1-13 dates
console.log('\nCrop Week Schedule:');
for (let cropWeek = 1; cropWeek <= 13; cropWeek++) {
    const weekStart = ridWeek36Start.add(cropWeek - 1, 'week');
    const calendarWeek = weekStart.week();
    console.log(`Crop Week ${cropWeek}: ${weekStart.format('YYYY-MM-DD')} (Calendar week ${calendarWeek})`);
}
// Verify: November 1, 2024 + 35 weeks = ?
const daysToAdd = 35 * 7; // 245 days
console.log(`\nVerification: November 1, 2024 + ${daysToAdd} days = ${ridWeek1Start.add(daysToAdd, 'day').format('YYYY-MM-DD')}`);
//# sourceMappingURL=calculate-rid-week-36.js.map