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
// Excel values from the image (weeks 36-48 are RID weeks)
const excelData = [
    { ridWeek: 36, cropWeek: 1, areaRai: 45125.7, waterDemandMm: 63.26, waterDemandM3: 4568069, effectiveRainfallMm: 29.02, netDemandMm: 34.24, netDemandM3: 2474365 },
    { ridWeek: 37, cropWeek: 2, areaRai: 45125.7, waterDemandMm: 51.54, waterDemandM3: 3724011, effectiveRainfallMm: 29.02, netDemandMm: 22.52, netDemandM3: 1626900 },
    { ridWeek: 38, cropWeek: 3, areaRai: 45125.7, waterDemandMm: 53.78, waterDemandM3: 3886133, effectiveRainfallMm: 29.02, netDemandMm: 24.76, netDemandM3: 1789022 },
    { ridWeek: 39, cropWeek: 4, areaRai: 45125.7, waterDemandMm: 55.36, waterDemandM3: 4000366, effectiveRainfallMm: 29.02, netDemandMm: 26.34, netDemandM3: 1903255 },
    { ridWeek: 40, cropWeek: 5, areaRai: 45125.7, waterDemandMm: 56.83, waterDemandM3: 4107661, effectiveRainfallMm: 28.90, netDemandMm: 27.93, netDemandM3: 2018301 },
    { ridWeek: 41, cropWeek: 6, areaRai: 45125.7, waterDemandMm: 58.30, waterDemandM3: 4214957, effectiveRainfallMm: 28.90, netDemandMm: 29.40, netDemandM3: 2125597 },
    { ridWeek: 42, cropWeek: 7, areaRai: 45125.7, waterDemandMm: 57.93, waterDemandM3: 4188009, effectiveRainfallMm: 28.90, netDemandMm: 29.03, netDemandM3: 2098649 },
    { ridWeek: 43, cropWeek: 8, areaRai: 45125.7, waterDemandMm: 50.09, waterDemandM3: 3621337, effectiveRainfallMm: 28.90, netDemandMm: 21.19, netDemandM3: 1531977 },
    { ridWeek: 44, cropWeek: 9, areaRai: 45125.7, waterDemandMm: 46.70, waterDemandM3: 3376315, effectiveRainfallMm: 29.16, netDemandMm: 17.54, netDemandM3: 1268010 },
    { ridWeek: 45, cropWeek: 10, areaRai: 45125.7, waterDemandMm: 45.13, waterDemandM3: 3263082, effectiveRainfallMm: 29.16, netDemandMm: 15.97, netDemandM3: 1154777 },
    { ridWeek: 46, cropWeek: 11, areaRai: 45125.7, waterDemandMm: 41.37, waterDemandM3: 2991563, effectiveRainfallMm: 29.16, netDemandMm: 12.21, netDemandM3: 883258 },
    { ridWeek: 47, cropWeek: 12, areaRai: 45125.7, waterDemandMm: 40.42, waterDemandM3: 2923146, effectiveRainfallMm: 29.16, netDemandMm: 11.26, netDemandM3: 814842 },
    { ridWeek: 48, cropWeek: 13, areaRai: 45125.7, waterDemandMm: 40.42, waterDemandM3: 2923146, effectiveRainfallMm: 29.16, netDemandMm: 11.26, netDemandM3: 814842 }
];
async function detailedComparison() {
    try {
        console.log('DETAILED ROS WATER DEMAND vs EXCEL COMPARISON');
        console.log('==============================================');
        console.log('Planting Date: July 4, 2025 (RID Week 36)');
        console.log('');
        console.log('Area Comparison:');
        console.log('- System: 44,459.87 rai');
        console.log('- Excel:  45,125.70 rai');
        console.log(`- Difference: ${((44459.87 - 45125.7) / 45125.7 * 100).toFixed(2)}%`);
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
        console.log('GROSS WATER DEMAND COMPARISON:');
        console.log('==============================');
        console.log('');
        console.log('Week | RID | Cal | ETo  | Kc   | Demand (mm)      | Demand (m³)          | Rainfall (mm)');
        console.log('     |     |     | (mm) |      | Excel | System   | Excel     | System   | Excel | System');
        console.log('-----|-----|-----|------|------|-------|----------|-----------|----------|-------|-------');
        let totalExcelDemandM3 = 0;
        let totalSystemDemandM3 = 0;
        let totalExcelNetM3 = 0;
        let totalSystemNetM3 = 0;
        result.rows.forEach((row, idx) => {
            const excel = excelData[idx];
            if (!excel)
                return;
            const systemDemandMm = parseFloat(row.avg_demand_mm);
            const systemDemandM3 = parseFloat(row.total_demand_m3);
            const systemRainfallMm = parseFloat(row.avg_rainfall_mm);
            const systemEto = parseFloat(row.avg_eto);
            const systemKc = parseFloat(row.avg_kc);
            console.log(`  ${excel.cropWeek.toString().padStart(2)} | ` +
                ` ${excel.ridWeek} | ` +
                ` ${row.calendar_week} | ` +
                `${systemEto.toFixed(1).padStart(4)} | ` +
                `${systemKc.toFixed(2).padStart(4)} | ` +
                `${excel.waterDemandMm.toFixed(1).padStart(5)} | ` +
                `${systemDemandMm.toFixed(1).padStart(7)} | ` +
                `${excel.waterDemandM3.toLocaleString().padStart(9)} | ` +
                `${Math.round(systemDemandM3).toLocaleString().padStart(8)} | ` +
                `${excel.effectiveRainfallMm.toFixed(1).padStart(5)} | ` +
                `${systemRainfallMm.toFixed(1).padStart(6)}`);
            totalExcelDemandM3 += excel.waterDemandM3;
            totalSystemDemandM3 += systemDemandM3;
        });
        console.log('\n');
        console.log('NET WATER DEMAND COMPARISON:');
        console.log('============================');
        console.log('');
        console.log('Week | RID | Net Demand (mm)  | Net Demand (m³)      | Difference');
        console.log('     |     | Excel | System   | Excel     | System   | mm    | %');
        console.log('-----|-----|-------|----------|-----------|----------|-------|-------');
        result.rows.forEach((row, idx) => {
            const excel = excelData[idx];
            if (!excel)
                return;
            const systemNetMm = parseFloat(row.avg_net_demand_mm);
            const systemNetM3 = parseFloat(row.total_net_demand_m3);
            const diffMm = systemNetMm - excel.netDemandMm;
            const diffPercent = excel.netDemandMm > 0 ? (diffMm / excel.netDemandMm * 100) : 0;
            console.log(`  ${excel.cropWeek.toString().padStart(2)} | ` +
                ` ${excel.ridWeek} | ` +
                `${excel.netDemandMm.toFixed(1).padStart(5)} | ` +
                `${systemNetMm.toFixed(1).padStart(7)} | ` +
                `${excel.netDemandM3.toLocaleString().padStart(9)} | ` +
                `${Math.round(systemNetM3).toLocaleString().padStart(8)} | ` +
                `${diffMm > 0 ? '+' : ''}${diffMm.toFixed(1).padStart(5)} | ` +
                `${diffPercent > 0 ? '+' : ''}${diffPercent.toFixed(1).padStart(5)}%`);
            totalExcelNetM3 += excel.netDemandM3;
            totalSystemNetM3 += systemNetM3;
        });
        console.log('\n');
        console.log('SUMMARY:');
        console.log('========');
        console.log('');
        console.log('Gross Water Demand:');
        console.log(`- Excel:  ${(totalExcelDemandM3 / 1000000).toFixed(2)} million m³`);
        console.log(`- System: ${(totalSystemDemandM3 / 1000000).toFixed(2)} million m³`);
        console.log(`- Difference: ${((totalSystemDemandM3 - totalExcelDemandM3) / totalExcelDemandM3 * 100).toFixed(2)}%`);
        console.log('');
        console.log('Net Water Demand (after rainfall):');
        console.log(`- Excel:  ${(totalExcelNetM3 / 1000000).toFixed(2)} million m³`);
        console.log(`- System: ${(totalSystemNetM3 / 1000000).toFixed(2)} million m³`);
        console.log(`- Difference: ${((totalSystemNetM3 - totalExcelNetM3) / totalExcelNetM3 * 100).toFixed(2)}%`);
        // Get land preparation data
        const landPrepQuery = `
      SELECT 
        SUM(crop_water_demand_m3) as land_prep_m3
      FROM ros.plot_water_demand_weekly
      WHERE crop_type = 'rice' 
        AND calendar_year = 2025
        AND crop_week = 0;
    `;
        const landPrepResult = await database_1.pool.query(landPrepQuery);
        const landPrepM3 = parseFloat(landPrepResult.rows[0]?.land_prep_m3 || 0);
        console.log('\n');
        console.log('INCLUDING LAND PREPARATION:');
        console.log('===========================');
        console.log(`Land Preparation Water: ${(landPrepM3 / 1000000).toFixed(2)} million m³`);
        console.log(`Total Gross (with land prep): ${((totalSystemDemandM3 + landPrepM3) / 1000000).toFixed(2)} million m³`);
        console.log(`Total Net (with land prep): ${((totalSystemNetM3 + landPrepM3) / 1000000).toFixed(2)} million m³`);
        process.exit(0);
    }
    catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}
detailedComparison();
//# sourceMappingURL=detailed-comparison-with-excel.js.map