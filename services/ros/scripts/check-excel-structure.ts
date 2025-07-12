#!/usr/bin/env ts-node

import * as XLSX from 'xlsx';
import * as path from 'path';

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