#!/usr/bin/env ts-node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const xlsx_1 = __importDefault(require("xlsx"));
const chalk_1 = __importDefault(require("chalk"));
const excelPath = '/Users/subhajlimanond/dev/munbon2-backend/คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm';
console.log(chalk_1.default.blue(`📖 Reading Excel file: ${excelPath}`));
const workbook = xlsx_1.default.readFile(excelPath);
console.log(chalk_1.default.yellow('\nAvailable worksheets:'));
Object.keys(workbook.Sheets).forEach((sheet, i) => {
    console.log(`${i + 1}. ${sheet}`);
});
// Look for effective rainfall sheet
const effectiveRainfallSheets = Object.keys(workbook.Sheets).filter(sheet => sheet.includes('ฝน') || sheet.includes('rain') || sheet.includes('Rainfall'));
if (effectiveRainfallSheets.length > 0) {
    console.log(chalk_1.default.green('\n✅ Found potential effective rainfall sheets:'));
    effectiveRainfallSheets.forEach(sheet => {
        console.log(`  - ${sheet}`);
        // Try to extract data from the sheet
        const worksheet = workbook.Sheets[sheet];
        console.log(chalk_1.default.yellow(`\n  Checking structure of ${sheet}:`));
        // Check first few cells
        const range = xlsx_1.default.utils.decode_range(worksheet['!ref'] || 'A1:Z100');
        console.log(`  Sheet range: A1:${xlsx_1.default.utils.encode_cell({ r: range.e.r, c: range.e.c })}`);
        // Look for rice data in column C and field crops in column H
        console.log('\n  Rice effective rainfall (Column C):');
        for (let row = 1; row <= Math.min(20, range.e.r); row++) {
            const cellC = worksheet[xlsx_1.default.utils.encode_cell({ r: row, c: 2 })]; // Column C
            if (cellC?.v !== undefined) {
                const cellA = worksheet[xlsx_1.default.utils.encode_cell({ r: row, c: 0 })]; // Column A for label
                console.log(`    Row ${row + 1}: ${cellA?.v || 'No label'} = ${cellC.v}`);
            }
        }
        console.log('\n  Field crops effective rainfall (Column H):');
        for (let row = 1; row <= Math.min(20, range.e.r); row++) {
            const cellH = worksheet[xlsx_1.default.utils.encode_cell({ r: row, c: 7 })]; // Column H
            if (cellH?.v !== undefined) {
                const cellG = worksheet[xlsx_1.default.utils.encode_cell({ r: row, c: 6 })]; // Column G for label
                console.log(`    Row ${row + 1}: ${cellG?.v || 'No label'} = ${cellH.v}`);
            }
        }
    });
}
else {
    console.log(chalk_1.default.red('\n❌ No effective rainfall sheet found'));
}
//# sourceMappingURL=check-effective-rainfall.js.map