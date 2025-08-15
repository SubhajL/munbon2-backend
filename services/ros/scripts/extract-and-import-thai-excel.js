#!/usr/bin/env ts-node
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const xlsx_1 = __importDefault(require("xlsx"));
const database_1 = require("../src/config/database");
const chalk_1 = __importDefault(require("chalk"));
const fs_1 = require("fs");
const path_1 = require("path");
async function extractAndImportThaiExcel() {
    const excelPath = '/Users/subhajlimanond/dev/munbon2-backend/คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm';
    console.log(chalk_1.default.blue('📖 Reading Thai ROS Excel file...'));
    const workbook = xlsx_1.default.readFile(excelPath);
    const extractedData = {
        eto: [],
        kc: [],
        parameters: {}
    };
    // Extract ETo data
    console.log(chalk_1.default.yellow('\n📊 Extracting ETo Data...'));
    const etoSheet = workbook.Sheets['ETo'];
    // Find Nakhon Ratchasima row (row 38 - verified in Excel)
    const stationRow = 38;
    const stationName = 'นครราชสีมา';
    // Extract monthly values (columns D-O for months 1-12)
    const monthColumns = ['D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'];
    monthColumns.forEach((col, index) => {
        const cell = etoSheet[`${col}${stationRow}`];
        if (cell && cell.v) {
            const month = index + 1;
            const value = Number(cell.v);
            extractedData.eto.push({ station: stationName, month, value });
            console.log(`  Month ${month}: ${value} mm`);
        }
    });
    // Calculate annual average
    const annualTotal = extractedData.eto.reduce((sum, e) => sum + e.value, 0);
    const annualAverage = annualTotal / 12;
    console.log(chalk_1.default.green(`  Annual Average: ${annualAverage.toFixed(2)} mm/month`));
    // Extract Kc data
    console.log(chalk_1.default.yellow('\n📊 Extracting Kc Data...'));
    const kcSheet = workbook.Sheets['Kc'];
    // Crops are in COLUMNS, not rows!
    // Based on Excel structure: B=Rice, F=Corn, etc.
    const crops = [
        { column: 'B', name: 'rice', thaiName: 'ข้าว กข.(นาดำ)' },
        { column: 'F', name: 'corn', thaiName: 'ข้าวโพดเลี้ยงสัตว์' },
        { column: 'X', name: 'sugarcane', thaiName: 'อ้อย' }
    ];
    crops.forEach(crop => {
        console.log(`  Extracting ${crop.thaiName} (${crop.name})...`);
        let weekCount = 0;
        // Extract weekly Kc values (weeks start at row 6)
        for (let week = 1; week <= 52; week++) {
            const row = 5 + week; // Row 6 = Week 1, Row 7 = Week 2, etc.
            const cell = kcSheet[`${crop.column}${row}`];
            if (cell && cell.v !== undefined && cell.v !== '') {
                const value = Number(cell.v);
                if (!isNaN(value) && value > 0) {
                    extractedData.kc.push({ crop: crop.name, week, value });
                    weekCount++;
                }
            }
        }
        console.log(`    Found ${weekCount} weeks of data`);
    });
    // Extract parameters from fill_data
    console.log(chalk_1.default.yellow('\n📊 Extracting Parameters...'));
    const fillSheet = workbook.Sheets['fill_data'];
    // Seepage/percolation (row 117)
    const seepageCell = fillSheet['B117'];
    if (seepageCell) {
        extractedData.parameters.seepage = Number(seepageCell.v);
        console.log(`  Seepage/Percolation: ${seepageCell.v} mm/week`);
    }
    // Rice area (row 76)
    const riceAreaCell = fillSheet['B76'];
    if (riceAreaCell) {
        extractedData.parameters.riceArea = Number(riceAreaCell.v);
        console.log(`  Rice area: ${riceAreaCell.v} rai`);
    }
    // Save extracted data
    const outputPath = (0, path_1.resolve)(__dirname, '../extracted_thai_data.json');
    (0, fs_1.writeFileSync)(outputPath, JSON.stringify(extractedData, null, 2));
    console.log(chalk_1.default.green(`\n✅ Data saved to: ${outputPath}`));
    // Import to database
    console.log(chalk_1.default.yellow('\n📤 Importing to database...'));
    await importToDatabase(extractedData);
    // Run validation test
    console.log(chalk_1.default.yellow('\n🧪 Running validation test...'));
    await runValidationTest();
}
async function importToDatabase(data) {
    try {
        // Import ETo data
        console.log('  Importing ETo data...');
        for (const eto of data.eto) {
            await database_1.pool.query(`
        INSERT INTO ros.eto_monthly (aos_station, province, month, eto_value) 
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (aos_station, province, month) 
        DO UPDATE SET eto_value = $4
      `, [eto.station, 'นครราชสีมา', eto.month, eto.value]);
        }
        console.log(chalk_1.default.green(`  ✅ Imported ${data.eto.length} ETo records`));
        // Import Kc data
        console.log('  Importing Kc data...');
        for (const kc of data.kc) {
            await database_1.pool.query(`
        INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value) 
        VALUES ($1, $2, $3)
        ON CONFLICT (crop_type, crop_week) 
        DO UPDATE SET kc_value = $3
      `, [kc.crop, kc.week, kc.value]);
        }
        console.log(chalk_1.default.green(`  ✅ Imported ${data.kc.length} Kc records`));
    }
    catch (error) {
        console.error(chalk_1.default.red('Error importing to database:'), error);
    }
}
async function runValidationTest() {
    try {
        const { waterDemandService } = await Promise.resolve().then(() => __importStar(require('../src/services/water-demand.service')));
        // Test case: Rice Week 5 in May
        console.log(chalk_1.default.blue('\n📋 Test Case: Rice Week 5 in May'));
        const result = await waterDemandService.calculateWaterDemand({
            areaId: 'THAI-TEST',
            areaType: 'project',
            areaRai: 45731, // From Excel
            cropType: 'rice',
            cropWeek: 5,
            calendarWeek: 19, // Mid-May
            calendarYear: 2025,
            effectiveRainfall: 0,
            waterLevel: 0
        });
        // Expected values from Excel analysis (corrected)
        const expectedMonthlyETo = 116.0; // May value from Excel (row 38)
        const expectedWeeklyETo = expectedMonthlyETo / 4;
        const expectedKc = 0.72; // Week 5 Kc for rice (column B, row 10)
        const expectedPercolation = 14;
        const expectedDemandMm = (expectedWeeklyETo * expectedKc) + expectedPercolation;
        const expectedDemandM3 = expectedDemandMm * 45731 * 1.6;
        console.log('\n  Results:');
        console.log(`  Monthly ETo: ${result.monthlyETo} mm (Expected: ${expectedMonthlyETo})`);
        console.log(`  Weekly ETo: ${result.weeklyETo.toFixed(2)} mm (Expected: ${expectedWeeklyETo.toFixed(2)})`);
        console.log(`  Kc Value: ${result.kcValue} (Expected: ${expectedKc})`);
        console.log(`  Percolation: ${result.percolation} mm (Expected: ${expectedPercolation})`);
        console.log(`  Water Demand: ${result.cropWaterDemandMm.toFixed(2)} mm (Expected: ${expectedDemandMm.toFixed(2)})`);
        console.log(`  Volume: ${(result.cropWaterDemandM3 / 1000000).toFixed(2)} MCM (Expected: ${(expectedDemandM3 / 1000000).toFixed(2)} MCM)`);
        // Check if calculations match
        const mmTolerance = 0.1;
        const mmDiff = Math.abs(result.cropWaterDemandMm - expectedDemandMm);
        if (mmDiff < mmTolerance) {
            console.log(chalk_1.default.green('\n  ✅ PASS - Calculations match Thai Excel!'));
        }
        else {
            console.log(chalk_1.default.red('\n  ❌ FAIL - Calculations do not match'));
            console.log(`  Difference: ${mmDiff.toFixed(2)} mm`);
        }
        // Generate detailed comparison report
        generateComparisonReport(result, {
            monthlyETo: expectedMonthlyETo,
            weeklyETo: expectedWeeklyETo,
            kcValue: expectedKc,
            percolation: expectedPercolation,
            cropWaterDemandMm: expectedDemandMm,
            cropWaterDemandM3: expectedDemandM3
        });
    }
    catch (error) {
        console.error(chalk_1.default.red('Error running validation:'), error);
    }
}
function generateComparisonReport(actual, expected) {
    const report = {
        timestamp: new Date().toISOString(),
        excelFile: 'คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm',
        testCase: 'Rice Week 5 in May',
        comparison: {
            monthlyETo: {
                actual: actual.monthlyETo,
                expected: expected.monthlyETo,
                difference: actual.monthlyETo - expected.monthlyETo,
                match: actual.monthlyETo === expected.monthlyETo
            },
            weeklyETo: {
                actual: actual.weeklyETo,
                expected: expected.weeklyETo,
                difference: actual.weeklyETo - expected.weeklyETo,
                match: Math.abs(actual.weeklyETo - expected.weeklyETo) < 0.01
            },
            kcValue: {
                actual: actual.kcValue,
                expected: expected.kcValue,
                difference: actual.kcValue - expected.kcValue,
                match: actual.kcValue === expected.kcValue
            },
            waterDemandMm: {
                actual: actual.cropWaterDemandMm,
                expected: expected.cropWaterDemandMm,
                difference: actual.cropWaterDemandMm - expected.cropWaterDemandMm,
                match: Math.abs(actual.cropWaterDemandMm - expected.cropWaterDemandMm) < 0.1
            },
            waterDemandM3: {
                actual: actual.cropWaterDemandM3,
                expected: expected.cropWaterDemandM3,
                difference: actual.cropWaterDemandM3 - expected.cropWaterDemandM3,
                match: Math.abs(actual.cropWaterDemandM3 - expected.cropWaterDemandM3) < 1000
            }
        },
        formula: {
            description: 'Water Demand (mm) = (Weekly ETo × Kc) + Percolation',
            calculation: `(${actual.weeklyETo.toFixed(2)} × ${actual.kcValue}) + ${actual.percolation} = ${actual.cropWaterDemandMm.toFixed(2)} mm`
        }
    };
    const reportPath = (0, path_1.resolve)(__dirname, '../reports/thai-excel-comparison.json');
    (0, fs_1.writeFileSync)(reportPath, JSON.stringify(report, null, 2));
    console.log(chalk_1.default.blue(`\n📄 Detailed report saved to: ${reportPath}`));
}
// Main execution
if (require.main === module) {
    extractAndImportThaiExcel()
        .then(() => {
        console.log(chalk_1.default.green('\n✅ Thai Excel validation completed!'));
        process.exit(0);
    })
        .catch(error => {
        console.error(chalk_1.default.red('Fatal error:'), error);
        process.exit(1);
    });
}
//# sourceMappingURL=extract-and-import-thai-excel.js.map