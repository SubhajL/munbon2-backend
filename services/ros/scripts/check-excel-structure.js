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
Object.defineProperty(exports, "__esModule", { value: true });
const XLSX = __importStar(require("xlsx"));
const path = __importStar(require("path"));
const excelPath = path.resolve(__dirname, '../../../คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm');
const workbook = XLSX.readFile(excelPath);
console.log('=== ETo Worksheet Structure ===');
const etoSheet = workbook.Sheets['ETo'];
// Check what's in column B (station names)
console.log('\nColumn B (Stations):');
for (let row = 1; row <= 80; row++) {
    const cell = etoSheet[`B${row}`];
    if (cell && cell.v && String(cell.v).includes('นครราชสีมา')) {
        console.log(`Row ${row}: ${cell.v}`);
    }
    if (row === 71 && cell) {
        console.log(`Row 71 contains: ${cell.v}`);
    }
}
console.log('\n=== Kc Worksheet Structure ===');
const kcSheet = workbook.Sheets['Kc'];
// Check first row (headers)
console.log('\nFirst row (crop types):');
for (let col = 65; col <= 90; col++) { // A to Z
    const colLetter = String.fromCharCode(col);
    const cell = kcSheet[`${colLetter}1`];
    if (cell && cell.v) {
        console.log(`Column ${colLetter}: ${cell.v}`);
    }
}
// Check first column (weeks)
console.log('\nColumn A (weeks):');
for (let row = 1; row <= 10; row++) {
    const cell = kcSheet[`A${row}`];
    if (cell && cell.v) {
        console.log(`Row ${row}: ${cell.v}`);
    }
}
//# sourceMappingURL=check-excel-structure.js.map