#!/usr/bin/env ts-node

import * as XLSX from 'xlsx';
import * as path from 'path';

const excelPath = path.resolve(__dirname, '../../../คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm');
const workbook = XLSX.readFile(excelPath);

console.log('=== Searching for Land Preparation Data (น้ำเตรียมแปลง) ===\n');

// Search all worksheets
const sheetNames = workbook.SheetNames;
console.log(`Total worksheets: ${sheetNames.length}`);
console.log('Sheet names:', sheetNames.join(', '));
console.log('\n');

// Keywords to search for
const keywords = ['เตรียมแปลง', 'เตรียม', 'แปลง', 'preparation', 'land prep', 'initial', 'น้ำเตรียม'];

sheetNames.forEach(sheetName => {
  const sheet = workbook.Sheets[sheetName];
  const range = XLSX.utils.decode_range(sheet['!ref'] || 'A1:Z100');
  
  let foundInSheet = false;
  
  // Search through all cells
  for (let row = range.s.r; row <= Math.min(range.e.r, 200); row++) {
    for (let col = range.s.c; col <= Math.min(range.e.c, 50); col++) {
      const cellAddress = XLSX.utils.encode_cell({ r: row, c: col });
      const cell = sheet[cellAddress];
      
      if (cell && cell.v) {
        const cellValue = String(cell.v).toLowerCase();
        
        // Check for any keyword
        for (const keyword of keywords) {
          if (cellValue.includes(keyword.toLowerCase())) {
            if (!foundInSheet) {
              console.log(`\n=== Found in worksheet: ${sheetName} ===`);
              foundInSheet = true;
            }
            
            const colLetter = XLSX.utils.encode_col(col);
            console.log(`Cell ${colLetter}${row + 1}: ${cell.v}`);
            
            // Also check nearby cells for related values
            for (let nearCol = col - 2; nearCol <= col + 5; nearCol++) {
              if (nearCol !== col && nearCol >= 0) {
                const nearCellAddr = XLSX.utils.encode_cell({ r: row, c: nearCol });
                const nearCell = sheet[nearCellAddr];
                if (nearCell && nearCell.v) {
                  const nearColLetter = XLSX.utils.encode_col(nearCol);
                  console.log(`  - Nearby ${nearColLetter}${row + 1}: ${nearCell.v}`);
                }
              }
            }
            break;
          }
        }
      }
    }
  }
});

console.log('\n=== Checking fill_data worksheet in detail ===');
const fillSheet = workbook.Sheets['fill_data'];
if (fillSheet) {
  // Look for specific patterns in fill_data
  for (let row = 1; row <= 100; row++) {
    for (let col = 65; col <= 90; col++) { // A to Z
      const colLetter = String.fromCharCode(col);
      const cell = fillSheet[`${colLetter}${row}`];
      
      if (cell && cell.v) {
        const value = String(cell.v);
        // Look for water-related terms
        if (value.includes('น้ำ') || value.includes('water') || value.includes('ม.ม.') || value.includes('มม.')) {
          console.log(`${colLetter}${row}: ${value}`);
        }
      }
    }
  }
}

console.log('\n=== Checking ROS worksheet ===');
const rosSheet = workbook.Sheets['ROS'];
if (rosSheet) {
  // Check specific areas where land prep might be
  console.log('Checking rows 60-70 (around percolation data):');
  for (let row = 60; row <= 70; row++) {
    const labelCell = rosSheet[`B${row}`];
    const valueCell = rosSheet[`C${row}`];
    
    if (labelCell && labelCell.v) {
      console.log(`Row ${row}: ${labelCell.v}${valueCell && valueCell.v ? ' = ' + valueCell.v : ''}`);
    }
  }
}