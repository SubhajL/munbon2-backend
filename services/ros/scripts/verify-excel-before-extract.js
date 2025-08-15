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
const XLSX = __importStar(require("xlsx"));
const path = __importStar(require("path"));
const chalk_1 = __importDefault(require("chalk"));
const excelPath = path.resolve(__dirname, '../../../คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm');
const workbook = XLSX.readFile(excelPath);
console.log(chalk_1.default.blue('=== Verifying Excel Structure Before Extraction ==='));
// Verify ETo sheet - Row 38 should be นครราชสีมา
console.log(chalk_1.default.yellow('\n📊 ETo Worksheet Verification:'));
const etoSheet = workbook.Sheets['ETo'];
// Check row 38
const row38StationCell = etoSheet['B38'];
const row38ProvinceCell = etoSheet['C38'];
console.log(`Row 38 Station: ${row38StationCell?.v || 'EMPTY'}`);
console.log(`Row 38 Province: ${row38ProvinceCell?.v || 'EMPTY'}`);
// Check a few ETo values from row 38
console.log('\nRow 38 Monthly Values:');
const months = ['D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'];
months.forEach((col, idx) => {
    const cell = etoSheet[`${col}38`];
    if (cell && cell.v) {
        console.log(`  Month ${idx + 1} (${col}38): ${cell.v}`);
    }
});
// Also verify row 71 is NOT นครราชสีมา
const row71Cell = etoSheet['B71'];
console.log(`\nRow 71 Station (for comparison): ${row71Cell?.v || 'EMPTY'}`);
// Verify Kc sheet - Crops in columns
console.log(chalk_1.default.yellow('\n📊 Kc Worksheet Verification:'));
const kcSheet = workbook.Sheets['Kc'];
// Check crop headers (around rows 3-5)
console.log('\nCrop Headers (Rows 3-5):');
const cropColumns = ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'];
cropColumns.forEach(col => {
    for (let row = 3; row <= 5; row++) {
        const cell = kcSheet[`${col}${row}`];
        if (cell && cell.v && String(cell.v).length > 0) {
            console.log(`  ${col}${row}: ${cell.v}`);
        }
    }
});
// Check week labels in column A
console.log('\nWeek Labels (Column A):');
for (let row = 6; row <= 15; row++) {
    const cell = kcSheet[`A${row}`];
    if (cell && cell.v) {
        console.log(`  Row ${row}: ${cell.v}`);
    }
}
// Check some Kc values
console.log('\nSample Kc Values:');
console.log('Rice (Column B), Weeks 1-5:');
for (let week = 1; week <= 5; week++) {
    const row = 5 + week;
    const cell = kcSheet[`B${row}`];
    console.log(`  Week ${week} (B${row}): ${cell?.v || 'EMPTY'}`);
}
console.log('\nCorn (Column F), Weeks 1-5:');
for (let week = 1; week <= 5; week++) {
    const row = 5 + week;
    const cell = kcSheet[`F${row}`];
    console.log(`  Week ${week} (F${row}): ${cell?.v || 'EMPTY'}`);
}
console.log(chalk_1.default.green('\n✅ Verification complete!'));
//# sourceMappingURL=verify-excel-before-extract.js.map