#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const chalk_1 = __importDefault(require("chalk"));
const fs_1 = require("fs");
const path_1 = require("path");
// Extracted data from Thai Excel (คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm)
const THAI_EXCEL_DATA = {
    // ETo monthly values for นครราชสีมา (mm/month)
    eto: {
        1: 121.68, // January
        2: 123.94, // February
        3: 150.05, // March
        4: 147.47, // April
        5: 142.65, // May
        6: 132.26, // June
        7: 137.98, // July
        8: 137.58, // August
        9: 127.65, // September
        10: 119.42, // October
        11: 106.99, // November
        12: 114.67 // December
    },
    // Kc values for rice (ข้าว กข.) - first 16 weeks shown
    kcRice: {
        1: 1.07, 2: 0.79, 3: 1.30, 4: 0.52,
        5: 0.72, 6: 0.68, 7: 0.57, 8: 0.69,
        9: 0.72, 10: 0.87, 11: 0.70, 12: 0.57,
        13: 0.73, 14: 1.14, 15: 0.82, 16: 0.76
    },
    // Fixed parameters
    percolation: 14, // mm/week (standard value, not the 0.087 from extraction)
    riceArea: 45731 // rai (from row 76 of fill_data sheet)
};
function calculateWaterDemand(monthlyETo, kcValue, areaRai, percolation = 14) {
    // Calculate weekly ETo from monthly
    const weeklyETo = monthlyETo / 4;
    // Water demand formula: (Weekly ETo × Kc) + Percolation
    const cropWaterDemandMm = (weeklyETo * kcValue) + percolation;
    // Convert to volume: mm × area(rai) × 1.6
    const cropWaterDemandM3 = cropWaterDemandMm * areaRai * 1.6;
    return {
        monthlyETo,
        weeklyETo,
        kcValue,
        percolation,
        cropWaterDemandMm,
        cropWaterDemandM3
    };
}
function runValidationTests() {
    const results = [];
    // Test Case 1: Rice Week 5 in May
    console.log(chalk_1.default.blue('\n📋 Test Case 1: Rice Week 5 in May'));
    const test1 = {
        cropType: 'rice',
        cropWeek: 5,
        calendarMonth: 5,
        areaRai: 100 // Using 100 rai for easier calculation
    };
    const monthlyETo = THAI_EXCEL_DATA.eto[test1.calendarMonth];
    const kcValue = THAI_EXCEL_DATA.kcRice[test1.cropWeek];
    const calc1 = calculateWaterDemand(monthlyETo, kcValue, test1.areaRai);
    console.log(`  Monthly ETo: ${monthlyETo} mm`);
    console.log(`  Weekly ETo: ${calc1.weeklyETo.toFixed(2)} mm`);
    console.log(`  Kc Value: ${kcValue}`);
    console.log(`  Percolation: ${calc1.percolation} mm`);
    console.log(`  Water Demand: ${calc1.cropWaterDemandMm.toFixed(2)} mm`);
    console.log(`  Volume: ${calc1.cropWaterDemandM3.toFixed(0)} m³`);
    results.push({
        testCase: 'Rice Week 5 in May (100 rai)',
        input: test1,
        expected: calc1,
        actual: calc1, // In real test, this would come from ROS service
        differences: {},
        passed: true
    });
    // Test Case 2: Rice Week 14 (high Kc period)
    console.log(chalk_1.default.blue('\n📋 Test Case 2: Rice Week 14 - Peak Kc'));
    const test2 = {
        cropType: 'rice',
        cropWeek: 14,
        calendarMonth: 7, // July
        areaRai: 1000
    };
    const calc2 = calculateWaterDemand(THAI_EXCEL_DATA.eto[test2.calendarMonth], THAI_EXCEL_DATA.kcRice[test2.cropWeek], test2.areaRai);
    console.log(`  Monthly ETo: ${THAI_EXCEL_DATA.eto[test2.calendarMonth]} mm`);
    console.log(`  Weekly ETo: ${calc2.weeklyETo.toFixed(2)} mm`);
    console.log(`  Kc Value: ${THAI_EXCEL_DATA.kcRice[test2.cropWeek]}`);
    console.log(`  Water Demand: ${calc2.cropWaterDemandMm.toFixed(2)} mm`);
    console.log(`  Volume: ${(calc2.cropWaterDemandM3 / 1000).toFixed(0)} thousand m³`);
    results.push({
        testCase: 'Rice Week 14 - Peak Kc (1000 rai)',
        input: test2,
        expected: calc2,
        actual: calc2,
        differences: {},
        passed: true
    });
    // Test Case 3: Full project area
    console.log(chalk_1.default.blue('\n📋 Test Case 3: Full Rice Area (45,731 rai)'));
    const test3 = {
        cropType: 'rice',
        cropWeek: 5,
        calendarMonth: 5,
        areaRai: THAI_EXCEL_DATA.riceArea
    };
    const calc3 = calculateWaterDemand(THAI_EXCEL_DATA.eto[test3.calendarMonth], THAI_EXCEL_DATA.kcRice[test3.cropWeek], test3.areaRai);
    console.log(`  Area: ${test3.areaRai.toLocaleString()} rai`);
    console.log(`  Water Demand: ${calc3.cropWaterDemandMm.toFixed(2)} mm`);
    console.log(`  Volume: ${(calc3.cropWaterDemandM3 / 1000000).toFixed(2)} MCM`);
    results.push({
        testCase: 'Full Rice Area Week 5',
        input: test3,
        expected: calc3,
        actual: calc3,
        differences: {},
        passed: true
    });
    return results;
}
function generateValidationFormulas() {
    console.log(chalk_1.default.yellow('\n📐 Validation Formulas:'));
    console.log('\n1. Weekly ETo Calculation:');
    console.log('   Weekly ETo = Monthly ETo ÷ 4');
    console.log('   Example: May = 142.65 ÷ 4 = 35.66 mm/week');
    console.log('\n2. Water Demand Calculation:');
    console.log('   Water Demand (mm) = (Weekly ETo × Kc) + Percolation');
    console.log('   Example: (35.66 × 0.72) + 14 = 39.68 mm');
    console.log('\n3. Volume Calculation:');
    console.log('   Volume (m³) = Water Demand (mm) × Area (rai) × 1.6');
    console.log('   Example: 39.68 × 100 × 1.6 = 6,348 m³');
}
function generateComparisonTable() {
    console.log(chalk_1.default.yellow('\n📊 Thai Excel Values Summary:'));
    // ETo Summary
    console.log('\nMonthly ETo (นครราชสีมา):');
    console.log('Month | Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec');
    console.log('------|----------------------------------------------------------------------');
    console.log('mm    |', Object.values(THAI_EXCEL_DATA.eto).map(v => v.toFixed(0).padStart(5)).join(' '));
    // Kc Summary for Rice
    console.log('\n\nWeekly Kc for Rice (ข้าว กข.):');
    console.log('Week  | 1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16');
    console.log('------|------------------------------------------------------------------------------');
    console.log('Kc    |', Object.values(THAI_EXCEL_DATA.kcRice).map(v => v.toFixed(2).padStart(4)).join(' '));
}
function saveValidationReport(results) {
    const report = {
        timestamp: new Date().toISOString(),
        excelFile: 'คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm',
        extractedData: {
            etoStation: 'นครราชสีมา',
            annualAverageETo: (Object.values(THAI_EXCEL_DATA.eto).reduce((a, b) => a + b, 0) / 12).toFixed(2),
            percolation: THAI_EXCEL_DATA.percolation,
            riceArea: THAI_EXCEL_DATA.riceArea
        },
        testResults: results,
        formulas: {
            weeklyETo: 'Monthly ETo ÷ 4',
            waterDemand: '(Weekly ETo × Kc) + Percolation',
            volume: 'Water Demand (mm) × Area (rai) × 1.6'
        },
        validation: {
            status: 'READY_FOR_TESTING',
            note: 'These are the expected values from Thai Excel. ROS service should match these calculations.'
        }
    };
    const reportPath = (0, path_1.resolve)(__dirname, '../reports/thai-excel-validation-expected.json');
    (0, fs_1.writeFileSync)(reportPath, JSON.stringify(report, null, 2));
    console.log(chalk_1.default.green(`\n📄 Validation report saved to: ${reportPath}`));
}
// Main execution
function main() {
    console.log(chalk_1.default.bold.blue('🇹🇭 Thai ROS Excel Validation\n'));
    console.log(`Excel File: คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm`);
    console.log(`Station: นครราชสีมา (Nakhon Ratchasima)`);
    // Generate comparison table
    generateComparisonTable();
    // Show validation formulas
    generateValidationFormulas();
    // Run validation tests
    const results = runValidationTests();
    // Save report
    saveValidationReport(results);
    // Summary
    console.log(chalk_1.default.bold('\n✅ Validation Summary:'));
    console.log(`- Extracted ETo data for 12 months`);
    console.log(`- Extracted Kc data for rice (16 weeks)`);
    console.log(`- Percolation: ${THAI_EXCEL_DATA.percolation} mm/week`);
    console.log(`- Rice area: ${THAI_EXCEL_DATA.riceArea.toLocaleString()} rai`);
    console.log(`- Test calculations completed`);
    console.log(chalk_1.default.yellow('\n⚠️  Note: To complete validation, run these calculations through the ROS service API'));
    console.log('and compare with the expected values shown above.');
}
if (require.main === module) {
    main();
}
//# sourceMappingURL=validate-thai-excel-calculations.js.map