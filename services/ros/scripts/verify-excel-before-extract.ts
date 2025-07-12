#!/usr/bin/env ts-node

import * as XLSX from 'xlsx';
import * as path from 'path';
import chalk from 'chalk';

const excelPath = path.resolve(__dirname, '../../../คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm');
const workbook = XLSX.readFile(excelPath);

console.log(chalk.blue('=== Verifying Excel Structure Before Extraction ==='));

// Verify ETo sheet - Row 38 should be นครราชสีมา
console.log(chalk.yellow('\n📊 ETo Worksheet Verification:'));
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
console.log(chalk.yellow('\n📊 Kc Worksheet Verification:'));
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

console.log(chalk.green('\n✅ Verification complete!'));