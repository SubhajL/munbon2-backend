#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.runComparison = runComparison;
const water_demand_service_1 = require("../src/services/water-demand.service");
const chalk_1 = __importDefault(require("chalk"));
const cli_table3_1 = __importDefault(require("cli-table3"));
const fs_1 = require("fs");
const path_1 = require("path");
// Test cases with exact Excel values
const EXCEL_TEST_CASES = [
    {
        scenario: 'Rice Week 5 in May (100 rai)',
        input: {
            cropType: 'rice',
            cropWeek: 5,
            month: 5,
            areaRai: 100
        },
        excelValues: {
            monthlyETo: 148.8,
            weeklyETo: 37.2,
            kcValue: 1.10,
            demandMm: 54.92,
            demandM3: 8787.2
        }
    },
    {
        scenario: 'Corn Week 10 in July (50 rai)',
        input: {
            cropType: 'corn',
            cropWeek: 10,
            month: 7,
            areaRai: 50
        },
        excelValues: {
            monthlyETo: 130.2,
            weeklyETo: 32.55,
            kcValue: 1.20,
            demandMm: 53.06,
            demandM3: 4244.8
        }
    },
    {
        scenario: 'Sugarcane Week 25 in September (200 rai)',
        input: {
            cropType: 'sugarcane',
            cropWeek: 25,
            month: 9,
            areaRai: 200
        },
        excelValues: {
            monthlyETo: 114.0,
            weeklyETo: 28.5,
            kcValue: 1.25,
            demandMm: 49.625,
            demandM3: 15880
        }
    }
];
async function runComparison() {
    const results = [];
    for (const testCase of EXCEL_TEST_CASES) {
        console.log(chalk_1.default.blue(`\n📊 Testing: ${testCase.scenario}`));
        try {
            // Calculate using service
            const serviceResult = await water_demand_service_1.waterDemandService.calculateWaterDemand({
                areaId: 'EXCEL-TEST',
                areaType: 'plot',
                areaRai: testCase.input.areaRai,
                cropType: testCase.input.cropType,
                cropWeek: testCase.input.cropWeek,
                calendarWeek: getWeekFromMonth(testCase.input.month),
                calendarYear: 2024,
                effectiveRainfall: 0, // No rainfall for pure calculation test
                waterLevel: 0
            });
            // Compare each value
            const comparisons = [
                { field: 'Monthly ETo', excel: testCase.excelValues.monthlyETo, service: serviceResult.monthlyETo },
                { field: 'Weekly ETo', excel: testCase.excelValues.weeklyETo, service: serviceResult.weeklyETo },
                { field: 'Kc Value', excel: testCase.excelValues.kcValue, service: serviceResult.kcValue },
                { field: 'Demand (mm)', excel: testCase.excelValues.demandMm, service: serviceResult.cropWaterDemandMm },
                { field: 'Demand (m³)', excel: testCase.excelValues.demandM3, service: serviceResult.cropWaterDemandM3 }
            ];
            comparisons.forEach(comp => {
                const diff = Math.abs(comp.excel - comp.service);
                const percentDiff = comp.excel !== 0 ? (diff / comp.excel) * 100 : 0;
                let status;
                if (percentDiff === 0) {
                    status = 'PASS';
                }
                else if (percentDiff < 0.01) {
                    status = 'PASS'; // Within tolerance
                }
                else if (percentDiff < 0.1) {
                    status = 'WARNING';
                }
                else {
                    status = 'FAIL';
                }
                results.push({
                    scenario: testCase.scenario,
                    field: comp.field,
                    excelValue: comp.excel,
                    serviceValue: comp.service,
                    difference: diff,
                    percentDiff,
                    status
                });
            });
        }
        catch (error) {
            console.error(chalk_1.default.red(`Error testing ${testCase.scenario}:`), error);
        }
    }
    return results;
}
function displayResults(results) {
    // Group by scenario
    const scenarios = [...new Set(results.map(r => r.scenario))];
    scenarios.forEach(scenario => {
        const scenarioResults = results.filter(r => r.scenario === scenario);
        console.log(chalk_1.default.yellow(`\n\n📋 ${scenario}`));
        const table = new cli_table3_1.default({
            head: ['Field', 'Excel Value', 'Service Value', 'Difference', '%', 'Status'],
            colWidths: [15, 15, 15, 12, 10, 10],
            style: { head: ['cyan'] }
        });
        scenarioResults.forEach(result => {
            const statusColor = result.status === 'PASS' ? chalk_1.default.green :
                result.status === 'WARNING' ? chalk_1.default.yellow :
                    chalk_1.default.red;
            table.push([
                result.field,
                result.excelValue.toFixed(3),
                result.serviceValue.toFixed(3),
                result.difference.toFixed(4),
                result.percentDiff.toFixed(3) + '%',
                statusColor(result.status)
            ]);
        });
        console.log(table.toString());
    });
    // Summary statistics
    const totalTests = results.length;
    const passed = results.filter(r => r.status === 'PASS').length;
    const warnings = results.filter(r => r.status === 'WARNING').length;
    const failed = results.filter(r => r.status === 'FAIL').length;
    console.log(chalk_1.default.bold('\n\n📈 Summary:'));
    console.log(chalk_1.default.green(`✅ Passed: ${passed}/${totalTests}`));
    if (warnings > 0)
        console.log(chalk_1.default.yellow(`⚠️  Warnings: ${warnings}`));
    if (failed > 0)
        console.log(chalk_1.default.red(`❌ Failed: ${failed}`));
    const successRate = (passed / totalTests) * 100;
    console.log(chalk_1.default.bold(`\nSuccess Rate: ${successRate.toFixed(1)}%`));
}
function generateHTMLReport(results) {
    const html = `
<!DOCTYPE html>
<html>
<head>
  <title>ROS Excel vs Service Comparison Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1 { color: #333; }
    h2 { color: #666; margin-top: 30px; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }
    th { background-color: #4CAF50; color: white; }
    tr:nth-child(even) { background-color: #f2f2f2; }
    .pass { color: green; font-weight: bold; }
    .warning { color: orange; font-weight: bold; }
    .fail { color: red; font-weight: bold; }
    .summary { margin-top: 30px; padding: 20px; background-color: #f0f0f0; }
  </style>
</head>
<body>
  <h1>ROS Excel vs Service Comparison Report</h1>
  <p>Generated: ${new Date().toLocaleString()}</p>
  
  ${[...new Set(results.map(r => r.scenario))].map(scenario => `
    <h2>${scenario}</h2>
    <table>
      <tr>
        <th>Field</th>
        <th>Excel Value</th>
        <th>Service Value</th>
        <th>Difference</th>
        <th>% Diff</th>
        <th>Status</th>
      </tr>
      ${results.filter(r => r.scenario === scenario).map(r => `
        <tr>
          <td style="text-align: left;">${r.field}</td>
          <td>${r.excelValue.toFixed(3)}</td>
          <td>${r.serviceValue.toFixed(3)}</td>
          <td>${r.difference.toFixed(4)}</td>
          <td>${r.percentDiff.toFixed(3)}%</td>
          <td class="${r.status.toLowerCase()}">${r.status}</td>
        </tr>
      `).join('')}
    </table>
  `).join('')}
  
  <div class="summary">
    <h2>Summary</h2>
    <p>Total Tests: ${results.length}</p>
    <p class="pass">Passed: ${results.filter(r => r.status === 'PASS').length}</p>
    <p class="warning">Warnings: ${results.filter(r => r.status === 'WARNING').length}</p>
    <p class="fail">Failed: ${results.filter(r => r.status === 'FAIL').length}</p>
    <p><strong>Success Rate: ${((results.filter(r => r.status === 'PASS').length / results.length) * 100).toFixed(1)}%</strong></p>
  </div>
</body>
</html>
  `;
    const outputPath = (0, path_1.resolve)(__dirname, '../reports/excel-comparison-report.html');
    (0, fs_1.writeFileSync)(outputPath, html);
    console.log(chalk_1.default.blue(`\n📄 HTML report saved to: ${outputPath}`));
}
function getWeekFromMonth(month) {
    // Approximate week number for middle of month
    const weeksPerMonth = [
        4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48
    ];
    return weeksPerMonth[month - 1];
}
// Main execution
async function main() {
    console.log(chalk_1.default.bold.blue('🚀 ROS Excel vs Service Comparison Tool\n'));
    try {
        const results = await runComparison();
        displayResults(results);
        generateHTMLReport(results);
    }
    catch (error) {
        console.error(chalk_1.default.red('Fatal error:'), error);
        process.exit(1);
    }
}
// Run if called directly
if (require.main === module) {
    main();
}
//# sourceMappingURL=compare-excel-calculations.js.map