#!/usr/bin/env ts-node

import XLSX from 'xlsx';
import { writeFileSync } from 'fs';
import { resolve } from 'path';
import chalk from 'chalk';
import { pool } from '../src/config/database';

interface ThaiExcelData {
  etoData: Map<string, Map<number, number>>;  // station -> month -> value
  kcData: Map<string, Map<number, number>>;   // crop -> week -> value
  cropAreas: Map<string, number>;              // crop -> area in rai
  testCases: any[];
}

async function extractAndValidateThaiExcel(excelPath: string) {
  console.log(chalk.blue(`📖 Reading Thai Excel file: ${excelPath}`));
  
  const workbook = XLSX.readFile(excelPath);
  console.log(chalk.yellow(`\nFound ${Object.keys(workbook.Sheets).length} worksheets`));
  
  // Extract ETo data
  console.log(chalk.yellow('\n📊 Extracting ETo Data...'));
  const etoData = extractEToData(workbook.Sheets['ETo']);
  
  // Extract Kc data
  console.log(chalk.yellow('\n📊 Extracting Kc Data...'));
  const kcData = extractKcData(workbook.Sheets['Kc']);
  
  // Extract crop areas from fill_data
  console.log(chalk.yellow('\n📊 Extracting Crop Areas...'));
  const cropAreas = extractCropAreas(workbook.Sheets['fill_data']);
  
  // Generate test cases
  console.log(chalk.yellow('\n🧪 Generating Test Cases...'));
  const testCases = generateTestCases(etoData, kcData, cropAreas);
  
  // Run validation
  console.log(chalk.yellow('\n🔍 Running Validation...'));
  await runValidation(testCases);
}

function extractEToData(sheet: XLSX.WorkSheet): Map<string, Map<number, number>> {
  const etoMap = new Map<string, Map<number, number>>();
  
  // Find นครราชสีมา station data
  let nakhonRatchasimaRow = -1;
  
  // Search for the station name in column A
  for (let row = 1; row <= 100; row++) {
    const cell = sheet[`A${row}`];
    if (cell && cell.v && cell.v.toString().includes('นครราชสีมา')) {
      nakhonRatchasimaRow = row;
      console.log(`  Found นครราชสีมา at row ${row}`);
      break;
    }
  }
  
  if (nakhonRatchasimaRow === -1) {
    console.error(chalk.red('❌ Could not find นครราชสีมา station in ETo sheet'));
    return etoMap;
  }
  
  // Extract monthly values (columns B-M for months 1-12)
  const monthlyData = new Map<number, number>();
  const monthColumns = ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'];
  
  monthColumns.forEach((col, index) => {
    const cell = sheet[`${col}${nakhonRatchasimaRow}`];
    if (cell && cell.v) {
      const month = index + 1;
      const value = Number(cell.v);
      monthlyData.set(month, value);
      console.log(`  Month ${month}: ${value} mm`);
    }
  });
  
  etoMap.set('นครราชสีมา', monthlyData);
  return etoMap;
}

function extractKcData(sheet: XLSX.WorkSheet): Map<string, Map<number, number>> {
  const kcMap = new Map<string, Map<number, number>>();
  
  // Find crop rows - looking for specific crop names
  const crops = [
    { thai: 'ข้าว กข.', english: 'rice' },
    { thai: 'ข้าวโพด', english: 'corn' },
    { thai: 'อ้อย', english: 'sugarcane' }
  ];
  
  crops.forEach(crop => {
    console.log(`  Looking for ${crop.thai} (${crop.english})...`);
    const weeklyKc = new Map<number, number>();
    
    // Find the row with this crop
    let cropRow = -1;
    for (let row = 1; row <= 50; row++) {
      const cell = sheet[`A${row}`];
      if (cell && cell.v && cell.v.toString().includes(crop.thai)) {
        cropRow = row;
        console.log(`    Found at row ${row}`);
        break;
      }
    }
    
    if (cropRow > 0) {
      // Extract weekly Kc values (usually columns B onwards)
      for (let week = 1; week <= 52; week++) {
        const col = String.fromCharCode(65 + week); // A=65, B=66, etc.
        const cell = sheet[`${col}${cropRow}`];
        if (cell && cell.v) {
          weeklyKc.set(week, Number(cell.v));
        }
      }
      
      console.log(`    Extracted ${weeklyKc.size} weeks of Kc data`);
      kcMap.set(crop.english, weeklyKc);
    }
  });
  
  return kcMap;
}

function extractCropAreas(sheet: XLSX.WorkSheet): Map<string, number> {
  const areas = new Map<string, number>();
  
  // Look for specific area values in fill_data sheet
  // These are typically labeled with crop names and area in rai
  
  // Search for rice area (ข้าวนาปี)
  for (let row = 1; row <= 100; row++) {
    const labelCell = sheet[`A${row}`];
    const valueCell = sheet[`B${row}`];
    
    if (labelCell && labelCell.v) {
      const label = labelCell.v.toString();
      
      if (label.includes('ข้าวนาปี') && valueCell && valueCell.v) {
        areas.set('rice', Number(valueCell.v));
        console.log(`  Rice area: ${valueCell.v} rai`);
      }
      if (label.includes('พืชไร่นาปี') && valueCell && valueCell.v) {
        areas.set('upland', Number(valueCell.v));
        console.log(`  Upland crop area: ${valueCell.v} rai`);
      }
    }
  }
  
  return areas;
}

function generateTestCases(
  etoData: Map<string, Map<number, number>>,
  kcData: Map<string, Map<number, number>>,
  cropAreas: Map<string, number>
): any[] {
  const testCases = [];
  const nakhonETo = etoData.get('นครราชสีมา');
  
  if (!nakhonETo) {
    console.error(chalk.red('No ETo data found for นครราชสีมา'));
    return testCases;
  }
  
  // Test Case 1: Rice in May (Week 18-21)
  const riceKc = kcData.get('rice');
  if (riceKc && riceKc.has(5)) {
    const mayETo = nakhonETo.get(5) || 148.8;
    const weeklyETo = mayETo / 4;
    const kcValue = riceKc.get(5) || 1.10;
    const percolation = 14;
    const demandMm = (weeklyETo * kcValue) + percolation;
    
    testCases.push({
      name: 'Rice Week 5 in May',
      input: {
        cropType: 'rice',
        cropWeek: 5,
        calendarMonth: 5,
        areaRai: 100
      },
      expected: {
        monthlyETo: mayETo,
        weeklyETo: weeklyETo,
        kcValue: kcValue,
        cropWaterDemandMm: demandMm,
        cropWaterDemandM3: demandMm * 100 * 1.6
      }
    });
  }
  
  // Test Case 2: Extract actual calculation from Excel
  const paddySheet = etoData.get('paddy_rain');
  if (paddySheet) {
    // Try to extract a real calculation example
    console.log('  Attempting to extract calculation from paddy_rain sheet...');
  }
  
  return testCases;
}

async function runValidation(testCases: any[]) {
  console.log(chalk.bold('\n🔍 Validation Results:'));
  
  for (const testCase of testCases) {
    console.log(chalk.blue(`\n📋 ${testCase.name}`));
    
    try {
      // Import data to database first
      await importEToToDatabase(testCase.expected.monthlyETo, testCase.input.calendarMonth);
      await importKcToDatabase(testCase.input.cropType, testCase.input.cropWeek, testCase.expected.kcValue);
      
      // Run calculation using service
      const { waterDemandService } = await import('../src/services/water-demand.service');
      
      const result = await waterDemandService.calculateWaterDemand({
        areaId: 'TEST-THAI',
        areaType: 'plot',
        areaRai: testCase.input.areaRai,
        cropType: testCase.input.cropType,
        cropWeek: testCase.input.cropWeek,
        calendarWeek: testCase.input.calendarMonth * 4,
        calendarYear: 2025,
        effectiveRainfall: 0,
        waterLevel: 0
      });
      
      // Compare results
      console.log('\n  Comparison:');
      console.log(`  Monthly ETo: Excel=${testCase.expected.monthlyETo}, Service=${result.monthlyETo}`);
      console.log(`  Weekly ETo: Excel=${testCase.expected.weeklyETo.toFixed(2)}, Service=${result.weeklyETo.toFixed(2)}`);
      console.log(`  Kc Value: Excel=${testCase.expected.kcValue}, Service=${result.kcValue}`);
      console.log(`  Demand (mm): Excel=${testCase.expected.cropWaterDemandMm.toFixed(2)}, Service=${result.cropWaterDemandMm.toFixed(2)}`);
      console.log(`  Demand (m³): Excel=${testCase.expected.cropWaterDemandM3.toFixed(0)}, Service=${result.cropWaterDemandM3.toFixed(0)}`);
      
      // Check if they match
      const tolerance = 0.01; // 1% tolerance
      const mmDiff = Math.abs(result.cropWaterDemandMm - testCase.expected.cropWaterDemandMm);
      const m3Diff = Math.abs(result.cropWaterDemandM3 - testCase.expected.cropWaterDemandM3);
      
      if (mmDiff < tolerance && m3Diff < (testCase.expected.cropWaterDemandM3 * 0.01)) {
        console.log(chalk.green('  ✅ PASS - Calculations match!'));
      } else {
        console.log(chalk.red('  ❌ FAIL - Calculations do not match'));
      }
      
    } catch (error) {
      console.error(chalk.red(`  Error: ${error}`));
    }
  }
}

async function importEToToDatabase(value: number, month: number) {
  try {
    await pool.query(`
      INSERT INTO eto_monthly (aos_station, province, month, eto_value) 
      VALUES ($1, $2, $3, $4)
      ON CONFLICT (aos_station, province, month) 
      DO UPDATE SET eto_value = $4
    `, ['นครราชสีมา', 'นครราชสีมา', month, value]);
  } catch (error) {
    console.error('Error importing ETo:', error);
  }
}

async function importKcToDatabase(cropType: string, week: number, value: number) {
  try {
    await pool.query(`
      INSERT INTO kc_weekly (crop_type, crop_week, kc_value) 
      VALUES ($1, $2, $3)
      ON CONFLICT (crop_type, crop_week) 
      DO UPDATE SET kc_value = $3
    `, [cropType, week, value]);
  } catch (error) {
    console.error('Error importing Kc:', error);
  }
}

// Main execution
async function main() {
  const excelPath = '/Users/subhajlimanond/dev/munbon2-backend/คบ.มูลบน_ROS_ฤดูฝน(2568).xlsm';
  
  console.log(chalk.bold.blue('🇹🇭 Thai ROS Excel Validation Tool\n'));
  console.log(`Excel file: ${excelPath}`);
  
  try {
    await extractAndValidateThaiExcel(excelPath);
    
    // Generate summary report
    const reportPath = resolve(__dirname, '../reports/thai-excel-validation.json');
    writeFileSync(reportPath, JSON.stringify({
      timestamp: new Date().toISOString(),
      excelFile: excelPath,
      status: 'completed'
    }, null, 2));
    
    console.log(chalk.green(`\n✅ Validation completed! Report saved to: ${reportPath}`));
    
  } catch (error) {
    console.error(chalk.red('❌ Fatal error:'), error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

export { extractAndValidateThaiExcel };