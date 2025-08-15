#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.extractTestDataFromExcel = extractTestDataFromExcel;
const xlsx_1 = __importDefault(require("xlsx"));
const fs_1 = require("fs");
const path_1 = require("path");
const chalk_1 = __importDefault(require("chalk"));
function extractTestDataFromExcel(excelPath) {
    console.log(chalk_1.default.blue(`📖 Reading Excel file: ${excelPath}`));
    const workbook = xlsx_1.default.readFile(excelPath);
    const testCases = [];
    // Extract ETo data
    console.log(chalk_1.default.yellow('\n📊 Extracting ETo Monthly Data...'));
    const etoSheet = workbook.Sheets['ETo'];
    const etoData = extractEToData(etoSheet);
    // Extract Kc data
    console.log(chalk_1.default.yellow('\n📊 Extracting Kc Weekly Data...'));
    const kcSheet = workbook.Sheets['Kc'];
    const kcData = extractKcData(kcSheet);
    // Extract test scenarios from calculation sheet
    console.log(chalk_1.default.yellow('\n📊 Extracting Test Scenarios...'));
    const calcSheet = workbook.Sheets['Calculation'] || workbook.Sheets['Test'];
    if (calcSheet) {
        // Find test scenario rows
        const scenarios = extractScenarios(calcSheet, etoData, kcData);
        testCases.push(...scenarios);
    }
    // Generate additional test cases for edge cases
    console.log(chalk_1.default.yellow('\n🔧 Generating Edge Case Tests...'));
    testCases.push(...generateEdgeCaseTests(etoData, kcData));
    return testCases;
}
function extractEToData(sheet) {
    const etoMap = new Map();
    // Assuming ETo data structure:
    // Column A: Month names or numbers
    // Column B: ETo values for นครราชสีมา
    for (let row = 2; row <= 13; row++) {
        const monthCell = sheet[`A${row}`];
        const etoCell = sheet[`B${row}`];
        if (monthCell && etoCell) {
            const month = typeof monthCell.v === 'number' ? monthCell.v : row - 1;
            const etoValue = Number(etoCell.v);
            etoMap.set(month, etoValue);
            console.log(`  Month ${month}: ${etoValue} mm`);
        }
    }
    return etoMap;
}
function extractKcData(sheet) {
    const kcMap = new Map();
    // Initialize crop maps
    kcMap.set('rice', new Map());
    kcMap.set('corn', new Map());
    kcMap.set('sugarcane', new Map());
    // Extract Kc values
    // Assuming structure: Row 1 has crop names, Column A has week numbers
    const crops = ['rice', 'corn', 'sugarcane'];
    const columnMap = { rice: 'B', corn: 'C', sugarcane: 'D' };
    crops.forEach(crop => {
        const column = columnMap[crop];
        const cropKcMap = kcMap.get(crop);
        // Rice and corn: 16 weeks, Sugarcane: 52 weeks
        const maxWeeks = crop === 'sugarcane' ? 52 : 16;
        for (let week = 1; week <= maxWeeks; week++) {
            const cell = sheet[`${column}${week + 1}`]; // +1 for header row
            if (cell) {
                cropKcMap.set(week, Number(cell.v));
            }
        }
        console.log(`  ${crop}: ${cropKcMap.size} weeks of Kc data`);
    });
    return kcMap;
}
function extractScenarios(sheet, etoData, kcData) {
    const scenarios = [];
    // Look for test scenario section in the sheet
    // This is customized based on actual Excel structure
    // Example scenario extraction (adjust based on actual Excel)
    const testRows = [
        { row: 5, crop: 'rice', week: 5, month: 5, area: 100 },
        { row: 6, crop: 'corn', week: 10, month: 7, area: 50 },
        { row: 7, crop: 'sugarcane', week: 25, month: 9, area: 200 }
    ];
    testRows.forEach((test, index) => {
        const monthlyETo = etoData.get(test.month) || 0;
        const weeklyETo = monthlyETo / 4;
        const kcValue = kcData.get(test.crop)?.get(test.week) || 0;
        const percolation = 14;
        const demandMm = (weeklyETo * kcValue) + percolation;
        const demandM3 = demandMm * test.area * 1.6;
        scenarios.push({
            description: `${test.crop} week ${test.week} in month ${test.month}`,
            input: {
                cropType: test.crop,
                cropWeek: test.week,
                calendarWeek: test.month * 4, // Approximate
                calendarMonth: test.month,
                areaRai: test.area
            },
            excelCalculation: {
                monthlyETo,
                weeklyETo,
                kcValue,
                percolation,
                cropWaterDemandMm: demandMm,
                cropWaterDemandM3: demandM3,
                formula: {
                    etoCalc: `${monthlyETo} / 4 = ${weeklyETo}`,
                    kcLookup: `Kc[${test.crop}][${test.week}] = ${kcValue}`,
                    demandCalc: `(${weeklyETo} × ${kcValue}) + ${percolation} = ${demandMm}`,
                    volumeCalc: `${demandMm} × ${test.area} × 1.6 = ${demandM3}`
                }
            }
        });
    });
    return scenarios;
}
function generateEdgeCaseTests(etoData, kcData) {
    const edgeCases = [];
    // Test 1: First week of rice (low Kc)
    const riceKc = kcData.get('rice');
    const janETo = etoData.get(1);
    edgeCases.push({
        description: 'Rice first week (January) - Low Kc start',
        input: {
            cropType: 'rice',
            cropWeek: 1,
            calendarWeek: 1,
            calendarMonth: 1,
            areaRai: 75.5 // Decimal area
        },
        excelCalculation: {
            monthlyETo: janETo,
            weeklyETo: janETo / 4,
            kcValue: riceKc.get(1),
            percolation: 14,
            cropWaterDemandMm: (janETo / 4 * riceKc.get(1)) + 14,
            cropWaterDemandM3: ((janETo / 4 * riceKc.get(1)) + 14) * 75.5 * 1.6,
            formula: {
                etoCalc: `${janETo} / 4`,
                kcLookup: `Kc[rice][1]`,
                demandCalc: 'Weekly ETo × Kc + 14',
                volumeCalc: 'Demand mm × 75.5 × 1.6'
            }
        }
    });
    // Test 2: Peak Kc period
    const julyETo = etoData.get(7);
    const peakKc = Math.max(...Array.from(riceKc.values()));
    const peakWeek = Array.from(riceKc.entries()).find(([_, kc]) => kc === peakKc)?.[0] || 10;
    edgeCases.push({
        description: 'Rice peak Kc period - Maximum water demand',
        input: {
            cropType: 'rice',
            cropWeek: peakWeek,
            calendarWeek: 28,
            calendarMonth: 7,
            areaRai: 250
        },
        excelCalculation: {
            monthlyETo: julyETo,
            weeklyETo: julyETo / 4,
            kcValue: peakKc,
            percolation: 14,
            cropWaterDemandMm: (julyETo / 4 * peakKc) + 14,
            cropWaterDemandM3: ((julyETo / 4 * peakKc) + 14) * 250 * 1.6,
            formula: {
                etoCalc: `${julyETo} / 4`,
                kcLookup: `Kc[rice][${peakWeek}] (peak)`,
                demandCalc: 'Weekly ETo × Peak Kc + 14',
                volumeCalc: 'Demand mm × 250 × 1.6'
            }
        }
    });
    return edgeCases;
}
function saveTestCases(testCases, outputPath) {
    const output = {
        generatedAt: new Date().toISOString(),
        source: 'ROS Excel Worksheet',
        testCases: testCases
    };
    (0, fs_1.writeFileSync)(outputPath, JSON.stringify(output, null, 2));
    console.log(chalk_1.default.green(`\n✅ Saved ${testCases.length} test cases to: ${outputPath}`));
}
function generateTestCode(testCases) {
    const testCode = `
// Auto-generated test cases from Excel
// Generated: ${new Date().toISOString()}

export const EXCEL_VALIDATION_TESTS = ${JSON.stringify(testCases, null, 2)};

describe('Excel Formula Validation', () => {
  EXCEL_VALIDATION_TESTS.forEach(testCase => {
    test(\`\${testCase.description}\`, async () => {
      const result = await waterDemandService.calculateWaterDemand({
        areaId: 'EXCEL-TEST',
        areaType: 'plot',
        areaRai: testCase.input.areaRai,
        cropType: testCase.input.cropType,
        cropWeek: testCase.input.cropWeek,
        calendarWeek: testCase.input.calendarWeek,
        calendarYear: 2024
      });
      
      expect(result.monthlyETo).toBe(testCase.excelCalculation.monthlyETo);
      expect(result.weeklyETo).toBeCloseTo(testCase.excelCalculation.weeklyETo, 3);
      expect(result.kcValue).toBe(testCase.excelCalculation.kcValue);
      expect(result.cropWaterDemandMm).toBeCloseTo(testCase.excelCalculation.cropWaterDemandMm, 2);
      expect(result.cropWaterDemandM3).toBeCloseTo(testCase.excelCalculation.cropWaterDemandM3, 1);
    });
  });
});
`;
    return testCode;
}
// Main execution
async function main() {
    const args = process.argv.slice(2);
    const excelPath = args[0] || (0, path_1.resolve)(__dirname, '../tests/fixtures/ROS_Calculation.xlsx');
    const outputPath = args[1] || (0, path_1.resolve)(__dirname, '../tests/fixtures/excel-test-cases.json');
    console.log(chalk_1.default.bold.blue('🔍 ROS Excel Test Data Extractor\n'));
    try {
        const testCases = extractTestDataFromExcel(excelPath);
        saveTestCases(testCases, outputPath);
        // Also generate test code
        const testCodePath = outputPath.replace('.json', '.test.ts');
        const testCode = generateTestCode(testCases);
        (0, fs_1.writeFileSync)(testCodePath, testCode);
        console.log(chalk_1.default.green(`✅ Generated test code: ${testCodePath}`));
        // Display summary
        console.log(chalk_1.default.bold('\n📊 Extraction Summary:'));
        console.log(`Total test cases: ${testCases.length}`);
        console.log(`Crops covered: ${[...new Set(testCases.map(t => t.input.cropType))].join(', ')}`);
        console.log(`Months covered: ${[...new Set(testCases.map(t => t.input.calendarMonth))].join(', ')}`);
    }
    catch (error) {
        console.error(chalk_1.default.red('❌ Error extracting test data:'), error);
        process.exit(1);
    }
}
if (require.main === module) {
    main();
}
//# sourceMappingURL=extract-excel-test-data.js.map