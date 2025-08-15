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
const kcSheet = workbook.Sheets['Kc'];
console.log('Looking for sugarcane (อ้อย) column:');
// Search broader range
for (let col = 65; col <= 90; col++) { // A to Z
    const colLetter = String.fromCharCode(col);
    for (let row = 1; row <= 10; row++) {
        const cell = kcSheet[`${colLetter}${row}`];
        if (cell && cell.v && String(cell.v).includes('อ้อย')) {
            console.log(`Found อ้อย at ${colLetter}${row}: ${cell.v}`);
            // Show some values from this column
            console.log(`\nSample values from column ${colLetter}:`);
            for (let week = 1; week <= 5; week++) {
                const valueRow = 5 + week;
                const valueCell = kcSheet[`${colLetter}${valueRow}`];
                console.log(`  Week ${week} (${colLetter}${valueRow}): ${valueCell?.v || 'EMPTY'}`);
            }
        }
    }
}
//# sourceMappingURL=find-sugarcane.js.map