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
// Excel values from the image (weeks 36-48 are RID weeks, which map to calendar weeks 27-39)
const excelData = [
    { ridWeek: 36, cropWeek: 1, areaRai: 45125.7, waterDemandMm: 63.26, waterDemandM3: 4568069, effectiveRainfallMm: 29.02 },
    { ridWeek: 37, cropWeek: 2, areaRai: 45125.7, waterDemandMm: 51.54, waterDemandM3: 3724011, effectiveRainfallMm: 29.02 },
    { ridWeek: 38, cropWeek: 3, areaRai: 45125.7, waterDemandMm: 53.78, waterDemandM3: 3886133, effectiveRainfallMm: 29.02 },
    { ridWeek: 39, cropWeek: 4, areaRai: 45125.7, waterDemandMm: 55.36, waterDemandM3: 4000366, effectiveRainfallMm: 29.02 },
    { ridWeek: 40, cropWeek: 5, areaRai: 45125.7, waterDemandMm: 56.83, waterDemandM3: 4107661, effectiveRainfallMm: 28.90 },
    { ridWeek: 41, cropWeek: 6, areaRai: 45125.7, waterDemandMm: 58.30, waterDemandM3: 4214957, effectiveRainfallMm: 28.90 },
    { ridWeek: 42, cropWeek: 7, areaRai: 45125.7, waterDemandMm: 57.93, waterDemandM3: 4188009, effectiveRainfallMm: 28.90 },
    { ridWeek: 43, cropWeek: 8, areaRai: 45125.7, waterDemandMm: 50.09, waterDemandM3: 3621337, effectiveRainfallMm: 28.90 },
    { ridWeek: 44, cropWeek: 9, areaRai: 45125.7, waterDemandMm: 46.70, waterDemandM3: 3376315, effectiveRainfallMm: 29.16 },
    { ridWeek: 45, cropWeek: 10, areaRai: 45125.7, waterDemandMm: 45.13, waterDemandM3: 3263082, effectiveRainfallMm: 29.16 },
    { ridWeek: 46, cropWeek: 11, areaRai: 45125.7, waterDemandMm: 41.37, waterDemandM3: 2991563, effectiveRainfallMm: 29.16 },
    { ridWeek: 47, cropWeek: 12, areaRai: 45125.7, waterDemandMm: 40.42, waterDemandM3: 2923146, effectiveRainfallMm: 29.16 },
    { ridWeek: 48, cropWeek: 13, areaRai: 45125.7, waterDemandMm: 40.42, waterDemandM3: 2923146, effectiveRainfallMm: 29.16 }
];
async function compareWithExcel() {
    try {
        console.log('ROS Water Demand vs Excel Comparison');
        console.log('=====================================');
        console.log('Planting Date: July 4, 2025 (RID Week 36)');
        console.log('Total Area in System:', await getTotalArea(), 'rai');
        console.log('Total Area in Excel: 45,125.7 rai');
        console.log('');
        // Get our weekly calculations
        const query = `
      SELECT 
        crop_week,
        calendar_week,
        calendar_year,
        SUM(area_rai) as total_area,
        AVG(weekly_eto) as avg_eto,
        AVG(kc_value) as avg_kc,
        AVG(crop_water_demand_mm) as avg_demand_mm,
        SUM(crop_water_demand_m3) as total_demand_m3,
        AVG(effective_rainfall_mm) as avg_rainfall_mm,
        AVG(net_water_demand_mm) as avg_net_demand_mm,
        SUM(net_water_demand_m3) as total_net_demand_m3
      FROM ros.plot_water_demand_weekly
      WHERE crop_type = 'rice' 
        AND calendar_year = 2025
        AND crop_week > 0  -- Exclude land preparation
      GROUP BY crop_week, calendar_week, calendar_year
      ORDER BY crop_week;
    `;
        const result = await database_1.pool.query(query);
        console.log('Week-by-Week Comparison:');
        console.log('========================');
        console.log('');
        console.log('Crop | RID  | Cal  | Water Demand (mm) | Water Demand (m³)   | Effective Rainfall (mm)');
        console.log('Week | Week | Week | Excel  | System  | Excel      | System      | Excel  | System');
        console.log('-----|------|------|--------|---------|------------|-------------|--------|--------');
        let totalExcelDemandM3 = 0;
        let totalSystemDemandM3 = 0;
        let totalExcelRainfall = 0;
        let totalSystemRainfall = 0;
        result.rows.forEach((row, idx) => {
            const excel = excelData[idx];
            if (!excel)
                return;
            const systemDemandMm = parseFloat(row.avg_demand_mm);
            const systemDemandM3 = parseFloat(row.total_demand_m3);
            const systemRainfallMm = parseFloat(row.avg_rainfall_mm);
            // Calculate differences
            const demandMmDiff = ((systemDemandMm - excel.waterDemandMm) / excel.waterDemandMm * 100).toFixed(1);
            const demandM3Diff = ((systemDemandM3 - excel.waterDemandM3) / excel.waterDemandM3 * 100).toFixed(1);
            const rainfallDiff = ((systemRainfallMm - excel.effectiveRainfallMm) / excel.effectiveRainfallMm * 100).toFixed(1);
            console.log(`  ${excel.cropWeek.toString().padStart(2)} | ` +
                ` ${excel.ridWeek} | ` +
                ` ${row.calendar_week} | ` +
                `${excel.waterDemandMm.toFixed(2).padStart(6)} | ` +
                `${systemDemandMm.toFixed(2).padStart(7)} | ` +
                `${excel.waterDemandM3.toLocaleString().padStart(10)} | ` +
                `${systemDemandM3.toFixed(0).padStart(11)} | ` +
                `${excel.effectiveRainfallMm.toFixed(2).padStart(6)} | ` +
                `${systemRainfallMm.toFixed(2).padStart(6)}`);
            console.log(`     |      |      | ` +
                `${demandMmDiff}%`.padStart(15) + ' | ' +
                `${demandM3Diff}%`.padStart(22) + ' | ' +
                `${rainfallDiff}%`.padStart(15));
            totalExcelDemandM3 += excel.waterDemandM3;
            totalSystemDemandM3 += systemDemandM3;
            totalExcelRainfall += excel.effectiveRainfallMm;
            totalSystemRainfall += systemRainfallMm;
        });
        console.log('');
        console.log('Summary:');
        console.log('--------');
        console.log(`Total Water Demand (Excel): ${(totalExcelDemandM3 / 1000000).toFixed(2)} million m³`);
        console.log(`Total Water Demand (System): ${(totalSystemDemandM3 / 1000000).toFixed(2)} million m³`);
        console.log(`Difference: ${((totalSystemDemandM3 - totalExcelDemandM3) / totalExcelDemandM3 * 100).toFixed(2)}%`);
        console.log('');
        console.log(`Average Weekly Rainfall (Excel): ${(totalExcelRainfall / 13).toFixed(2)} mm`);
        console.log(`Average Weekly Rainfall (System): ${(totalSystemRainfall / 13).toFixed(2)} mm`);
        // Show detailed calculation for one week
        console.log('\n\nDetailed Calculation Example (Crop Week 5 / RID Week 40):');
        console.log('=========================================================');
        const week5 = result.rows.find(r => r.crop_week === 5);
        if (week5) {
            console.log(`Calendar Week: ${week5.calendar_week}`);
            console.log(`ETo: ${parseFloat(week5.avg_eto).toFixed(2)} mm`);
            console.log(`Kc: ${parseFloat(week5.avg_kc).toFixed(2)}`);
            console.log(`Percolation: 14 mm`);
            console.log(`Water Demand: (${parseFloat(week5.avg_eto).toFixed(2)} × ${parseFloat(week5.avg_kc).toFixed(2)}) + 14 = ${parseFloat(week5.avg_demand_mm).toFixed(2)} mm`);
            console.log(`Effective Rainfall: ${parseFloat(week5.avg_rainfall_mm).toFixed(2)} mm`);
            console.log(`Net Demand: ${parseFloat(week5.avg_net_demand_mm).toFixed(2)} mm`);
        }
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
async function getTotalArea() {
    const query = `SELECT SUM(area_rai) as total FROM ros.plots WHERE area_rai > 0`;
    const result = await database_1.pool.query(query);
    return parseFloat(result.rows[0].total).toFixed(2);
}
compareWithExcel();
//# sourceMappingURL=compare-with-excel-rid.js.map