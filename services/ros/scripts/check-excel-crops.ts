#!/usr/bin/env ts-node

import * as XLSX from 'xlsx';
import * as path from 'path';

const excelPath = path.resolve(__dirname, '../../../คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm');
const workbook = XLSX.readFile(excelPath);

const kcSheet = workbook.Sheets['Kc'];

// Check row 3-5 for crop headers
console.log('=== Crop Headers (Rows 3-5) ===');
for (let row = 3; row <= 5; row++) {
  console.log(`\nRow ${row}:`);
  for (let col = 65; col <= 80; col++) { // A to P
    const colLetter = String.fromCharCode(col);
    const cell = kcSheet[`${colLetter}${row}`];
    if (cell && cell.v) {
      console.log(`  ${colLetter}: ${cell.v}`);
    }
  }
}

// Check some Kc values
console.log('\n=== Sample Kc Values ===');
console.log('Row 6 (Week 1):');
for (let col = 66; col <= 75; col++) { // B to K
  const colLetter = String.fromCharCode(col);
  const cell = kcSheet[`${colLetter}6`];
  if (cell && cell.v) {
    console.log(`  ${colLetter}: ${cell.v}`);
  }
}