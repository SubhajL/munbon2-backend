#!/usr/bin/env ts-node

import XLSX from 'xlsx';
import chalk from 'chalk';
import { pool } from '../src/config/database';

interface EffectiveRainfallData {
  month: number;
  monthName: string;
  riceEffectiveRainfall: number;
  fieldCropEffectiveRainfall: number;
}

const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const thaiMonthNames = ['มค.', 'กพ.', 'มีค.', 'เมย.', 'พค.', 'มิย.', 'กค.', 'สค.', 'กย.', 'ตค.', 'พย.', 'ธค.'];

async function extractEffectiveRainfall() {
  console.log(chalk.blue('📊 Extracting Effective Rainfall Data from Excel'));
  
  const excelPath = '/Users/subhajlimanond/dev/munbon2-backend/คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm';
  const workbook = XLSX.readFile(excelPath);
  
  const sheet = workbook.Sheets['ฝนใช้การรายวัน'];
  if (!sheet) {
    console.error(chalk.red('❌ Sheet "ฝนใช้การรายวัน" not found!'));
    return;
  }
  
  const effectiveRainfall: EffectiveRainfallData[] = [];
  
  // Extract data from rows 2-13 (months 1-12)
  for (let row = 2; row <= 13; row++) {
    const monthCell = sheet[`A${row}`];
    const riceCell = sheet[`C${row}`];
    const fieldCropCell = sheet[`H${row}`];
    
    if (riceCell?.v !== undefined && fieldCropCell?.v !== undefined) {
      const monthIndex = row - 2; // 0-based month index
      effectiveRainfall.push({
        month: monthIndex + 1,
        monthName: monthNames[monthIndex],
        riceEffectiveRainfall: parseFloat(riceCell.v),
        fieldCropEffectiveRainfall: parseFloat(fieldCropCell.v)
      });
    }
  }
  
  console.log(chalk.green('\n✅ Extracted Effective Rainfall Data:'));
  console.table(effectiveRainfall);
  
  // Create SQL for inserting this data
  console.log(chalk.yellow('\n📝 Creating SQL for monthly effective rainfall table...'));
  
  const createTableSQL = `
-- Create monthly effective rainfall table
CREATE TABLE IF NOT EXISTS ros.effective_rainfall_monthly (
    id SERIAL PRIMARY KEY,
    aos_station VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    province VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา',
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    crop_type VARCHAR(50) NOT NULL, -- 'rice' or 'field_crop'
    effective_rainfall_mm DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(aos_station, province, month, crop_type)
);

-- Create index
CREATE INDEX idx_effective_rainfall_monthly ON ros.effective_rainfall_monthly(aos_station, province, month, crop_type);
`;

  console.log(createTableSQL);
  
  // Generate insert statements
  console.log(chalk.yellow('\n📝 Generating INSERT statements...'));
  
  const insertStatements: string[] = [];
  
  // Insert rice data
  effectiveRainfall.forEach(data => {
    insertStatements.push(`
INSERT INTO ros.effective_rainfall_monthly (aos_station, province, month, crop_type, effective_rainfall_mm)
VALUES ('นครราชสีมา', 'นครราชสีมา', ${data.month}, 'rice', ${data.riceEffectiveRainfall})
ON CONFLICT (aos_station, province, month, crop_type) 
DO UPDATE SET effective_rainfall_mm = EXCLUDED.effective_rainfall_mm, updated_at = NOW();`);
  });
  
  // Insert field crop data
  effectiveRainfall.forEach(data => {
    insertStatements.push(`
INSERT INTO ros.effective_rainfall_monthly (aos_station, province, month, crop_type, effective_rainfall_mm)
VALUES ('นครราชสีมา', 'นครราชสีมา', ${data.month}, 'field_crop', ${data.fieldCropEffectiveRainfall})
ON CONFLICT (aos_station, province, month, crop_type) 
DO UPDATE SET effective_rainfall_mm = EXCLUDED.effective_rainfall_mm, updated_at = NOW();`);
  });
  
  console.log(insertStatements.join('\n'));
  
  // Option to execute the SQL
  console.log(chalk.yellow('\n💾 Execute SQL? (uncomment the code below to run)'));
  
  /* Uncomment to execute
  try {
    await pool.query(createTableSQL);
    console.log(chalk.green('✅ Table created successfully'));
    
    for (const sql of insertStatements) {
      await pool.query(sql);
    }
    console.log(chalk.green('✅ Data inserted successfully'));
  } catch (error) {
    console.error(chalk.red('❌ Error executing SQL:'), error);
  }
  */
  
  // Calculate weekly effective rainfall from monthly
  console.log(chalk.blue('\n📊 Weekly Effective Rainfall Calculation:'));
  console.log('Monthly effective rainfall ÷ 4 = Weekly effective rainfall');
  
  effectiveRainfall.forEach(data => {
    console.log(`\n${data.monthName}:`);
    console.log(`  Rice: ${data.riceEffectiveRainfall} mm/month ÷ 4 = ${(data.riceEffectiveRainfall / 4).toFixed(2)} mm/week`);
    console.log(`  Field Crops: ${data.fieldCropEffectiveRainfall} mm/month ÷ 4 = ${(data.fieldCropEffectiveRainfall / 4).toFixed(2)} mm/week`);
  });
  
  await pool.end();
}

extractEffectiveRainfall().catch(console.error);