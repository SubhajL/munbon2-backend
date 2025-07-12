#!/usr/bin/env ts-node

import * as XLSX from 'xlsx';
import * as path from 'path';

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